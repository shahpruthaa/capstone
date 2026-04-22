from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.features.position_sizer import calculate_position_size
from app.features.price_levels import calculate_price_levels
from app.ml.lightgbm_alpha.technical_indicators import compute_technical_features
from app.schemas.trade_idea import CheckResultModel, TenPointChecklistModel, TradeIdeaModel
from app.services.db_quant_engine import Snapshot, get_effective_trade_date, load_snapshots
from app.services.ensemble_scorer import get_shared_ensemble_scorer

_TRADE_IDEA_CACHE: dict[tuple[str, bool, int, int | None], tuple[datetime, list[TradeIdeaModel]]] = {}
_TRADE_IDEA_CACHE_TTL = timedelta(minutes=5)


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
    ) -> list[TradeIdeaModel]:
        as_of_date = get_effective_trade_date(self.db)
        cache_key = (str(as_of_date), regime_filter, min_checklist_score, max_ideas)
        cached = _TRADE_IDEA_CACHE.get(cache_key)
        now = datetime.utcnow()
        if cached is not None and now - cached[0] <= _TRADE_IDEA_CACHE_TTL:
            return cached[1]

        snapshots = load_snapshots(self.db, as_of_date=as_of_date, min_history=252)
        if len(snapshots) < 10:
            snapshots = load_snapshots(self.db, as_of_date=as_of_date, min_history=90)

        predictions, _ = self.ensemble_scorer.score(snapshots, self.db)
        regime = self._detect_market_regime(snapshots)
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
        final_ideas = ideas[:max_ideas] if max_ideas is not None else ideas
        _TRADE_IDEA_CACHE[cache_key] = (now, final_ideas)
        return final_ideas

    def build_trade_idea(self, symbol: str) -> TradeIdeaModel | None:
        ideas = self.generate_trade_ideas(regime_filter=False, min_checklist_score=0)
        return next((idea for idea in ideas if idea.symbol == symbol), None)

    def _detect_market_regime(self, snapshots: list[Snapshot]) -> dict[str, float | str]:
        benchmark = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
        reference = benchmark or max(snapshots, key=lambda snapshot: snapshot.avg_traded_value, default=None)
        if reference is None:
            return {"regime": "sideways", "confidence": 0.0}

        closes = [price for _, price in reference.adjusted_closes]
        latest = closes[-1]
        sma50 = self._sma(closes, 50)
        sma200 = self._sma(closes, 200)

        stocks_with_50 = 0
        stocks_with_200 = 0
        above_50 = 0
        above_200 = 0
        for snapshot in snapshots:
            series = [price for _, price in snapshot.adjusted_closes]
            if len(series) >= 50:
                stocks_with_50 += 1
                above_50 += int(series[-1] > self._sma(series, 50))
            if len(series) >= 200:
                stocks_with_200 += 1
                above_200 += int(series[-1] > self._sma(series, 200))

        breadth_50 = above_50 / stocks_with_50 if stocks_with_50 else 0.5
        breadth_200 = above_200 / stocks_with_200 if stocks_with_200 else 0.5

        bull_signals = sum([latest > sma200, sma50 > sma200, breadth_50 > 0.55, breadth_200 > 0.50])
        bear_signals = sum([latest < sma200, sma50 < sma200, breadth_50 < 0.45, breadth_200 < 0.45])

        if bull_signals >= 3:
            regime = "bull"
            confidence = bull_signals / 4.0
        elif bear_signals >= 3:
            regime = "bear"
            confidence = bear_signals / 4.0
        else:
            regime = "sideways"
            confidence = max(0.5, max(bull_signals, bear_signals) / 4.0)

        return {"regime": regime, "confidence": round(confidence, 2), "breadth_50": round(breadth_50, 2), "breadth_200": round(breadth_200, 2)}

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
        )

        flow_score = min(1.0, max(0.0, 0.45 + (0.30 if liquidity > 0 else 0.0) + (0.25 if snapshot.avg_traded_value > 50_000_000 else 0.0)))
        fii_dii_flow = CheckResultModel(
            passed=flow_score >= 0.65,
            score=round(flow_score, 2),
            reason="Liquidity and turnover are being used as an interim accumulation proxy until FII/DII flow feeds land.",
        )

        fundamentals_score = min(1.0, max(0.0, 0.45 + (0.30 if quality > 0 else 0.0) + (0.25 if snapshot.max_drawdown_pct < 45 else 0.0)))
        fundamental_health = CheckResultModel(
            passed=fundamentals_score >= 0.65,
            score=round(fundamentals_score, 2),
            reason="Quality and drawdown behavior look healthy; full fundamentals ingestion is still pending.",
        )

        driver_text = prediction.top_drivers[0] if prediction.top_drivers else "No dominant catalyst surfaced"
        catalyst_score = min(1.0, max(0.0, 0.35 + (0.35 if prediction.pred_21d_return > 0 else 0.0) + (0.30 if prediction.top_drivers else 0.0)))
        news_catalyst = CheckResultModel(
            passed=catalyst_score >= 0.65,
            score=round(catalyst_score, 2),
            reason=f"Bootstrap catalyst view uses model drivers until structured news/event ingestion is added: {driver_text}.",
        )

        levels_score = min(1.0, max(0.0, 0.45 + (0.35 if levels.rr_ratio >= 2.0 else 0.0) + (0.20 if levels.risk_pct <= 8.0 else 0.0)))
        entry_stop_target = CheckResultModel(
            passed=levels_score >= 0.7,
            score=round(levels_score, 2),
            reason=f"Entry {levels.entry:.2f}, stop {levels.stop:.2f}, target {levels.target:.2f}, R:R {levels.rr_ratio:.2f}.",
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

    @staticmethod
    def _sma(values: list[float], window: int) -> float:
        if len(values) < window:
            return sum(values) / len(values) if values else 0.0
        return sum(values[-window:]) / window
