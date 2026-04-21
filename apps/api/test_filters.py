from app.db.session import SessionLocal
from app.services.db_quant_engine import (
    load_snapshots,
    filter_snapshots_for_mandate,
    compute_stock_news_signals,
    shortlist_candidates_for_mandate,
    align_return_matrix,
    estimate_expected_returns_for_mandate,
    build_shrunk_covariance,
    optimize_constrained_allocator_for_mandate,
    get_effective_trade_date
)
from app.schemas.portfolio import GeneratePortfolioRequest, UserMandate
from app.services.mandate import derive_mandate_config

payload = GeneratePortfolioRequest(
    capital_amount=500000.0,
    mandate=UserMandate(
        investment_horizon_weeks="4-8",
        max_portfolio_drawdown_pct=12.0,
        max_position_size_pct=12.5,
        preferred_num_positions=10,
        sector_inclusions=[],
        sector_exclusions=[],
        allow_small_caps=False,
        risk_attitude="balanced"
    ),
    model_variant="RULES"
)

with SessionLocal() as db:
    as_of_date = get_effective_trade_date(db)
    mandate_config = derive_mandate_config(payload.mandate)
    ml_min_history = max(84, mandate_config.lookback_days // 2)
    
    snapshots = load_snapshots(
        db,
        as_of_date=as_of_date,
        lookback_days=mandate_config.lookback_days,
        min_history=ml_min_history,
    )
    print(f"Total snapshots loaded: {len(snapshots)}")
    
    filtered = filter_snapshots_for_mandate(snapshots, mandate_config)
    print(f"After filter_snapshots_for_mandate: {len(filtered)}")
    
    if len(filtered) < max(4, mandate_config.target_positions):
        print(f"FAILED: length {len(filtered)} < {max(4, mandate_config.target_positions)}")
    
    news_signals = compute_stock_news_signals(filtered, payload.mandate)
    for snapshot in filtered:
        signal = news_signals.get(snapshot.symbol)
        if signal:
            snapshot.news_risk_score = signal.news_risk_score
            snapshot.news_opportunity_score = signal.news_opportunity_score
            snapshot.news_sentiment = signal.news_sentiment
            snapshot.news_impact = signal.news_impact
            snapshot.news_explanation = signal.news_explanation
    
    screened = shortlist_candidates_for_mandate(filtered, payload.mandate, mandate_config)
    print(f"After shortlist_candidates_for_mandate: {len(screened)}")
    
    if len(screened) < max(4, mandate_config.target_positions):
        print(f"FAILED: length {len(screened)} < {max(4, mandate_config.target_positions)}")
        
    aligned_snapshots, return_matrix = align_return_matrix(screened)
    print(f"After align_return_matrix: {len(aligned_snapshots)} snapshots, {len(return_matrix[0]) if return_matrix else 0} returns")
    
    expected_returns = estimate_expected_returns_for_mandate(
        db, as_of_date, aligned_snapshots, return_matrix, payload.mandate, mandate_config, "RULES"
    )
    covariance_matrix = build_shrunk_covariance(return_matrix, 0.40)
    
    try:
        optimized_weights = optimize_constrained_allocator_for_mandate(
            aligned_snapshots,
            expected_returns,
            covariance_matrix,
            payload.mandate,
            mandate_config,
        )
        print(f"Optimizer returned {len(optimized_weights) if optimized_weights else 0} weights")
    except Exception as e:
        print(f"Optimizer failed: {e}")
