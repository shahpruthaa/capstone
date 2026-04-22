from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.features.position_sizer import calculate_position_size
from app.features.price_levels import calculate_price_levels
from app.ml.lightgbm_alpha.technical_indicators import compute_technical_features
from app.schemas.portfolio import PortfolioFitSummaryModel
from app.schemas.trade_idea import CheckResultModel, TenPointChecklistModel, TradeIdeaContextModel, TradeIdeaListResponse, TradeIdeaModel
from app.services.db_quant_engine import Snapshot, build_portfolio_fit_summary, build_runtime_descriptor, detect_market_regime, get_effective_trade_date, load_snapshots
from app.services.ensemble_scorer import get_shared_ensemble_scorer
from app.services.model_runtime import get_model_runtime_status

_TRADE_IDEA_CACHE: "OrderedDict[tuple[str, bool, int, int | None], tuple[datetime, list[TradeIdeaModel]]]" = OrderedDict()
_TRADE_IDEA_CACHE_TTL = timedelta(minutes=5)
_TRADE_IDEA_CACHE_MAXSIZE = 64


def _prune_trade_idea_cache(now: datetime) -> None:
    expired_keys = [
        cache_key
        for cache_key, (cached_at, _) in list(_TRADE_IDEA_CACHE.items())
        if now - cached_at > _TRADE_IDEA_CACHE_TTL
    ]
    for cache_key in expired_keys:
        _TRADE_IDEA_CACHE.pop(cache_key, None)
    while len(_TRADE_IDEA_CACHE) > _TRADE_IDEA_CACHE_MAXSIZE:
        _TRADE_IDEA_CACHE.popitem(last=False)


class DecisionEngine:
    def __init__(self, db: Session):
        self.db = db
        self.ensemble_scorer = get_shared_ensemble_scorer()

    def generate_trade_ideas(
        self,
        regime_filter: bool = True,
        min_checklist_score: int = 7,
        max_ideas: int | None = None,
        portfolio_value: float = 1_000_000.0,
        risk_per_trade_pct: float = 1.0,
        cash_available: float | None = None,
        sector_exposures: dict[str, float] | None = None,
        current_holdings: list[TradeIdeaContextModel] | None = None,
    ) -> TradeIdeaListResponse:
        as_of_date = get_effective_trade_date(self.db)
        cache_key = (str(as_of_date), regime_filter, min_checklist_score, max_ideas)
        now = datetime.utcnow()
        _prune_trade_idea_cache(now)
        cached = _TRADE_IDEA_CACHE.get(cache_key)
        if cached is not None and now - cached[0] <= _TRADE_IDEA_CACHE_TTL and not current_holdings and not sector_exposures and cash_available is None:
            _TRADE_IDEA_CACHE.move_to_end(cache_key)
            return TradeIdeaListResponse(
                runtime=build_runtime_descriptor(get_model_runtime_status()),
                portfolio_fit_summary=None,
                notes=["Returned from short-lived trade-idea cache."],
                ideas=cached[1],
            )

        snapshots = load_snapshots(self.db, as_of_date=as_of_date, min_history=252)
        if len(snapshots) < 10:
            snapshots = load_snapshots(self.db, as_of_date=as_of_date, min_history=90)

        predictions, _ = self.ensemble_scorer.score(snapshots, self.db)
        regime = detect_market_regime(snapshots)
        sector_ranks, sector_scores = self._rank_sectors(snapshots, predictions)
        sector_relative_strength = self._build_sector_relative_strength(snapshots)

        ideas: list[TradeIdeaModel] = []
        sector_cutoff = max(3, ceil(max(len(sector_ranks), 1) * 0.4))

        for snapshot in snapshots:
            if snapshot.instrument_type == "ETF":
                continue

            prediction = predictions.get(snapshot.symbol)
            if prediction is None:
                continue

            sector_rank = sector_ranks.get(snapshot.sector, len(sector_ranks) + 1)
            if regime_filter and sector_rank > sector_cutoff:
                continue

            levels = calculate_price_levels(snapshot, prediction.pred_annual_return)
            sizing = calculate_position_size(
                portfolio_value=portfolio_value,
                risk_per_trade_pct=risk_per_trade_pct,
                entry=levels.entry,
                stop=levels.stop,
            )

            technicals = self._technical_snapshot(snapshot)
            checklist = self._build_checklist(
                snapshot=snapshot,
                prediction=prediction,
                regime=regime,
                sector_rank=sector_rank,
                sector_cutoff=sector_cutoff,
                sector_score=sector_scores.get(snapshot.sector, 0.0),
                relative_strength_rank=sector_relative_strength.get(snapshot.symbol, 0.0),
                technicals=technicals,
                levels=levels,
                sizing=sizing,
            )
            checklist_items = [
                checklist.regime_check,
                checklist.sector_strength,
                checklist.relative_strength,
                checklist.technical_setup,
                checklist.options_positioning,
                checklist.fii_dii_flow,
                checklist.fundamental_health,
                checklist.news_catalyst,
                checklist.entry_stop_target,
                checklist.position_sizing,
            ]
            checklist_score = sum(1 for item in checklist_items if item.passed)
            if checklist_score < min_checklist_score:
                continue

            regime_alignment = "aligned" if checklist.regime_check.passed else ("neutral" if checklist.regime_check.score >= 0.45 else "contrarian")
            catalyst = prediction.top_drivers[0] if prediction.top_drivers else None
            ideas.append(
                TradeIdeaModel(
                    symbol=snapshot.symbol,
                    sector=snapshot.sector,
                    timestamp=datetime.utcnow(),
                    as_of_date=as_of_date,
                    ensemble_score=round(float(prediction.pred_21d_return), 4),
                    expected_return_annual=round(float(prediction.pred_annual_return), 4),
                    top_drivers=list(prediction.top_drivers),
                    checklist=checklist,
                    checklist_score=checklist_score,
                    entry_price=levels.entry,
                    stop_loss=levels.stop,
                    target_price=levels.target,
                    risk_reward_ratio=levels.rr_ratio,
                    suggested_allocation_pct=sizing.allocation_pct,
                    max_loss_per_unit=round(levels.entry - levels.stop, 2),
                    regime_alignment=regime_alignment,
                    sector_rank=sector_rank,
                    catalyst=catalyst,
                )
            )

        ideas.sort(
            key=lambda idea: (
                idea.checklist_score,
                idea.expected_return_annual,
                idea.risk_reward_ratio,
                -idea.sector_rank,
            ),
            reverse=True,
        )
        holdings = current_holdings or []
        sector_budget = sector_exposures or {}
        duplicate_count = 0
        hedge_count = 0
        for idea in ideas:
            overlap = [holding.symbol for holding in holdings if holding.symbol == idea.symbol]
            sector_weight = float(sector_budget.get(idea.sector, 0.0))
            duplicate_factor_bets = [driver for driver in idea.top_drivers if any(token in driver.lower() for token in ("momentum", "quality", "low_vol", "beta"))]
            hedge_factor_bets = [driver for driver in idea.top_drivers if "low_vol" in driver.lower() or "quality" in driver.lower()]
            if duplicate_factor_bets:
                duplicate_count += 1
            if hedge_factor_bets:
                hedge_count += 1
            cash_limited_value = min(
                idea.suggested_allocation_pct * portfolio_value / 100.0,
                cash_available if cash_available is not None else portfolio_value,
            )
            idea.suggested_allocation_value = round(max(0.0, cash_limited_value), 2)
            idea.suggested_units = int(cash_limited_value // max(idea.entry_price, 1.0))
            idea.expected_holding_period_days = 21 if idea.regime_alignment == "aligned" else 10
            idea.liquidity_slippage_bps = round(min(65.0, max(8.0, (sector_weight / 10.0) + (4.0 if idea.suggested_allocation_pct > 10 else 0.0))), 1)
            idea.liquidity_commentary = (
                "Sizing is being clipped by available cash and current sector exposure."
                if cash_available is not None and cash_limited_value < (idea.suggested_allocation_pct * portfolio_value / 100.0)
                else "Liquidity estimate is based on position size versus local turnover proxy."
            )
            idea.event_calendar = [
                "Next earnings date: feed pending",
                f"Sector catalyst watch: {idea.sector} momentum and macro regime",
                "RBI / macro calendar: check weekly ahead of entry",
            ]
            idea.overlap_with_holdings = overlap
            idea.duplicate_factor_bets = duplicate_factor_bets[:2]
            idea.hedge_factor_bets = hedge_factor_bets[:2]
            idea.marginal_risk_contribution_pct = round(max(0.5, min(18.0, idea.suggested_allocation_pct * (1.2 if sector_weight >= 25 else 0.8))), 2)
            fit_bits = []
            if overlap:
                fit_bits.append("duplicates an existing holding")
            if sector_weight >= 25:
                fit_bits.append(f"pushes {idea.sector} concentration higher")
            if hedge_factor_bets:
                fit_bits.append("adds some defensive factor balance")
            elif duplicate_factor_bets:
                fit_bits.append("leans into an existing factor bet")
            if not fit_bits:
                fit_bits.append("adds new exposure without obvious concentration stress")
            idea.portfolio_fit_summary = "; ".join(fit_bits).capitalize() + "."
            idea.realized_hit_rate_by_type_pct = None

        final_ideas = ideas[:max_ideas] if max_ideas is not None else ideas
        _TRADE_IDEA_CACHE[cache_key] = (now, final_ideas)
        _TRADE_IDEA_CACHE.move_to_end(cache_key)
        _prune_trade_idea_cache(now)
        portfolio_fit_summary: PortfolioFitSummaryModel | None = None
        if holdings:
            portfolio_fit_summary = build_portfolio_fit_summary(
                risk_level=f"{len(holdings)} live holdings with Rs {portfolio_value:,.0f} modeled capital",
                diversification=f"{len(sector_budget)} sectors in the current book" if sector_budget else "sector exposures not supplied",
                concentration=f"{duplicate_count} ideas overlap current bets and {hedge_count} ideas hedge them",
                next_action="Prefer ideas that diversify sector and factor exposure before adding more to crowded sleeves.",
            )
        return TradeIdeaListResponse(
            runtime=build_runtime_descriptor(get_model_runtime_status()),
            portfolio_fit_summary=portfolio_fit_summary,
            notes=[
                "Options, institutional-flow, and fundamentals checks are explicitly marked as proxies until those feeds are wired in.",
                "Sizing incorporates supplied cash and sector exposure when present.",
            ],
            ideas=final_ideas,
        )

    def build_trade_idea(self, symbol: str) -> TradeIdeaModel | None:
        response = self.generate_trade_ideas(regime_filter=False, min_checklist_score=0)
        return next((idea for idea in response.ideas if idea.symbol == symbol), None)

    def _rank_sectors(self, snapshots: list[Snapshot], predictions: dict[str, object]) -> tuple[dict[str, int], dict[str, float]]:
        sector_buckets: dict[str, list[float]] = defaultdict(list)
        for snapshot in snapshots:
            if snapshot.instrument_type == "ETF":
                continue
            prediction = predictions.get(snapshot.symbol)
            ml_score = float(prediction.pred_21d_return) if prediction is not None else 0.0
            blended = (
                0.45 * snapshot.factor_scores.get("sector_strength", 0.0)
                + 0.35 * snapshot.factor_scores.get("momentum", 0.0)
                + 0.20 * ml_score
            )
            sector_buckets[snapshot.sector].append(blended)

        sector_scores = {sector: sum(values) / len(values) for sector, values in sector_buckets.items() if values}
        ordered = sorted(sector_scores.items(), key=lambda item: item[1], reverse=True)
        return ({sector: index + 1 for index, (sector, _) in enumerate(ordered)}, sector_scores)

    def _build_sector_relative_strength(self, snapshots: list[Snapshot]) -> dict[str, float]:
        sector_groups: dict[str, list[Snapshot]] = defaultdict(list)
        for snapshot in snapshots:
            if snapshot.instrument_type != "ETF":
                sector_groups[snapshot.sector].append(snapshot)

        percentile_by_symbol: dict[str, float] = {}
        for sector, sector_snapshots in sector_groups.items():
            ranked = sorted(
                sector_snapshots,
                key=lambda snapshot: snapshot.factor_scores.get("momentum", 0.0),
                reverse=True,
            )
            total = len(ranked)
            for index, snapshot in enumerate(ranked):
                percentile = 100.0 if total == 1 else 100.0 * (total - index - 1) / (total - 1)
                percentile_by_symbol[snapshot.symbol] = round(percentile, 1)
        return percentile_by_symbol

    def _build_checklist(
        self,
        *,
        snapshot: Snapshot,
        prediction,
        regime: dict[str, float | str],
        sector_rank: int,
        sector_cutoff: int,
        sector_score: float,
        relative_strength_rank: float,
        technicals: dict[str, float],
        levels,
        sizing,
    ) -> TenPointChecklistModel:
        regime_name = str(regime["regime"])
        momentum = snapshot.factor_scores.get("momentum", 0.0)
        quality = snapshot.factor_scores.get("quality", 0.0)
        low_vol = snapshot.factor_scores.get("low_vol", 0.0)
        liquidity = snapshot.factor_scores.get("liquidity", 0.0)
        beta = snapshot.beta_proxy

        if regime_name == "bull":
            regime_score = min(1.0, 0.5 + (0.2 if momentum > 0 else 0.0) + (0.2 if technicals.get("ema_ratio_50", 0.0) > 0 else 0.0) + (0.1 if sector_rank <= sector_cutoff else 0.0))
            regime_passed = regime_score >= 0.7
            regime_reason = f"Bull regime with breadth {float(regime.get('breadth_50', 0.0)):.0%}; momentum-led setup fits current tape."
        elif regime_name == "bear":
            regime_score = min(1.0, 0.45 + (0.25 if low_vol > 0 else 0.0) + (0.2 if quality > 0 else 0.0) + (0.1 if beta < 1.0 else 0.0))
            regime_passed = regime_score >= 0.7
            regime_reason = "Bear regime favors resilient balance between quality and lower-volatility characteristics."
        else:
            regime_score = min(1.0, 0.45 + (0.2 if quality > 0 else 0.0) + (0.2 if momentum > 0 else 0.0) + (0.1 if beta < 1.2 else 0.0))
            regime_passed = regime_score >= 0.7
            regime_reason = "Sideways tape rewards selective momentum with quality support."

        sector_strength_score = min(1.0, max(0.0, 0.6 + (0.25 if sector_rank <= sector_cutoff else -0.15) + (0.15 if sector_score > 0 else 0.0)))
        sector_strength = CheckResultModel(
            passed=sector_strength_score >= 0.65,
            score=round(sector_strength_score, 2),
            reason=f"{snapshot.sector} ranks #{sector_rank} with blended relative-strength score {sector_score:+.2f}.",
        )

        rs_score = min(1.0, max(0.0, relative_strength_rank / 100.0))
        relative_strength = CheckResultModel(
            passed=relative_strength_rank >= 70.0,
            score=round(rs_score, 2),
            reason=f"{snapshot.symbol} sits at the {relative_strength_rank:.0f}th percentile within {snapshot.sector}.",
        )

        technical_score = min(
            1.0,
            (0.30 if 50.0 <= technicals.get("rsi_14", 0.0) <= 72.0 else 0.0)
            + (0.25 if technicals.get("macd_signal_normalized", 0.0) > 0 else 0.0)
            + (0.20 if technicals.get("ema_ratio_21", 0.0) > 0 else 0.0)
            + (0.25 if technicals.get("ema_ratio_50", 0.0) > 0 else 0.0),
        )
        technical_setup = CheckResultModel(
            passed=technical_score >= 0.6,
            score=round(technical_score, 2),
            reason=f"RSI {technicals.get('rsi_14', 0.0):.1f}, MACD {'positive' if technicals.get('macd_signal_normalized', 0.0) > 0 else 'flat'}, trend {'above' if technicals.get('ema_ratio_50', 0.0) > 0 else 'below'} medium-term EMA.",
        )

        options_proxy_score = min(
            1.0,
            0.35
            + (0.25 if technicals.get("bb_bandwidth", 1.0) < 0.18 else 0.0)
            + (0.20 if technicals.get("macd_signal_normalized", 0.0) > 0 else 0.0)
            + (0.20 if momentum > 0 else 0.0),
        )
        options_positioning = CheckResultModel(
            passed=options_proxy_score >= 0.6,
            score=round(options_proxy_score, 2),
            reason="Bootstrap proxy: volatility compression plus momentum confirmation while NSE options ingestion is still pending.",
            data_quality="proxy",
        )

        flow_score = min(1.0, max(0.0, 0.45 + (0.30 if liquidity > 0 else 0.0) + (0.25 if snapshot.avg_traded_value > 50_000_000 else 0.0)))
        fii_dii_flow = CheckResultModel(
            passed=flow_score >= 0.65,
            score=round(flow_score, 2),
            reason="Liquidity and turnover are being used as an interim accumulation proxy until FII/DII flow feeds land.",
            data_quality="proxy",
        )

        fundamentals_score = min(1.0, max(0.0, 0.45 + (0.30 if quality > 0 else 0.0) + (0.25 if snapshot.max_drawdown_pct < 45 else 0.0)))
        fundamental_health = CheckResultModel(
            passed=fundamentals_score >= 0.65,
            score=round(fundamentals_score, 2),
            reason="Quality and drawdown behavior look healthy; full fundamentals ingestion is still pending.",
            data_quality="proxy",
        )

        driver_text = prediction.top_drivers[0] if prediction.top_drivers else "No dominant catalyst surfaced"
        catalyst_score = min(1.0, max(0.0, 0.35 + (0.35 if prediction.pred_21d_return > 0 else 0.0) + (0.30 if prediction.top_drivers else 0.0)))
        news_catalyst = CheckResultModel(
            passed=catalyst_score >= 0.65,
            score=round(catalyst_score, 2),
            reason=f"Bootstrap catalyst view uses model drivers until structured news/event ingestion is added: {driver_text}.",
            data_quality="proxy",
        )

        levels_score = min(
            1.0,
            max(
                0.0,
                0.20
                + (0.30 if levels.stop_basis == "atr" else 0.0)
                + (0.30 if levels.rr_ratio >= 2.0 else 0.0)
                + (0.20 if levels.risk_pct <= 8.0 else 0.0),
            ),
        )
        levels_passed = levels.stop_basis == "atr" and levels.rr_ratio >= 2.0 and levels.risk_pct <= 12.0
        level_bits = [f"Entry {levels.entry:.2f}, stop {levels.stop:.2f}, target {levels.target:.2f}, R:R {levels.rr_ratio:.2f}."]
        if levels.stop_basis == "risk_cap":
            level_bits.append("ATR stop breached the max-risk cap, so the setup is not being credited as a clean ATR-defined trade.")
        elif levels.target_basis == "rr_guardrail":
            level_bits.append("Target was lifted by the minimum reward-to-risk guardrail.")
        entry_stop_target = CheckResultModel(
            passed=levels_passed,
            score=round(levels_score, 2),
            reason=" ".join(level_bits),
        )

        sizing_score = min(1.0, max(0.0, 0.35 + (0.35 if sizing.units > 0 else 0.0) + (0.30 if 0 < sizing.allocation_pct <= 20 else 0.0)))
        position_sizing = CheckResultModel(
            passed=sizing_score >= 0.65,
            score=round(sizing_score, 2),
            reason=f"{sizing.units} units fit a {sizing.max_loss_pct:.1f}% risk budget with {sizing.allocation_pct:.2f}% capital usage.",
        )

        return TenPointChecklistModel(
            regime_check=CheckResultModel(passed=regime_passed, score=round(regime_score, 2), reason=regime_reason),
            sector_strength=sector_strength,
            relative_strength=relative_strength,
            technical_setup=technical_setup,
            options_positioning=options_positioning,
            fii_dii_flow=fii_dii_flow,
            fundamental_health=fundamental_health,
            news_catalyst=news_catalyst,
            entry_stop_target=entry_stop_target,
            position_sizing=position_sizing,
        )

    @staticmethod
    def _technical_snapshot(snapshot: Snapshot) -> dict[str, float]:
        opens = [price for _, price in snapshot.adjusted_opens]
        highs = [price for _, price in snapshot.adjusted_highs]
        lows = [price for _, price in snapshot.adjusted_lows]
        closes = [price for _, price in snapshot.adjusted_closes]
        return compute_technical_features(opens, highs, lows, closes)
