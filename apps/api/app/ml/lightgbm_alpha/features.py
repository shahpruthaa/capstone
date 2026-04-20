from __future__ import annotations

from typing import Any

from app.ml.lightgbm_alpha.technical_indicators import compute_technical_features


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _safe_mean(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return var**0.5


def compute_total_return_index(adjusted_closes: list[tuple[Any, float]], total_return_returns: list[tuple[Any, float]]) -> list[float]:
    """
    Build a synthetic total-return "price index" series:
    idx[0] = adjusted_close[0]
    idx[i] = idx[i-1] * (1 + r_{i-1})
    where r_{i-1} comes from total-return series (dividends reinvested notion).
    """
    if not adjusted_closes:
        return []

    n = len(adjusted_closes)
    if len(total_return_returns) != n - 1:
        # Fallback to close-based index if we cannot align return series.
        return [p for _, p in adjusted_closes]

    idx: list[float] = [adjusted_closes[0][1]]
    for i in range(1, n):
        r = total_return_returns[i - 1][1]
        idx.append(idx[-1] * (1.0 + r))
    return idx


def trailing_return(idx: list[float], window: int) -> float | None:
    # Return over `window` trading days: idx[t] / idx[t-window] - 1.
    if len(idx) < window + 1 or idx[-window - 1] == 0:
        return None
    return idx[-1] / idx[-window - 1] - 1.0


def rolling_vol(returns: list[float], window: int) -> float | None:
    # Annualized volatility from rolling std of daily returns.
    if len(returns) < window:
        return None
    tail = returns[-window:]
    sd = _safe_std(tail)
    return sd * (252**0.5)


def rolling_downside_vol(returns: list[float], window: int) -> float | None:
    if len(returns) < window:
        return None
    tail = returns[-window:]
    downside = [r for r in tail if r < 0]
    if not downside:
        return 0.0
    sd = _safe_std(downside)
    return sd * (252**0.5)


def max_drawdown(idx: list[float], window: int) -> float | None:
    if len(idx) < window + 1:
        return None
    series = idx[-(window + 1) :]
    if not series:
        return None
    peak = series[0]
    mdd = 0.0
    for v in series:
        peak = max(peak, v)
        dd = (peak - v) / max(peak, 1e-12)
        mdd = max(mdd, dd)
    return mdd


def moving_average_ratio(idx: list[float], window: int) -> float | None:
    if len(idx) < window:
        return None
    ma = _safe_mean(idx[-window:])
    if ma == 0:
        return None
    return idx[-1] / ma - 1.0


def dist_from_high(idx: list[float], window: int) -> float | None:
    if len(idx) < window:
        return None
    hi = max(idx[-window:])
    if hi == 0:
        return None
    return idx[-1] / hi - 1.0


def compute_snapshot_features(snapshot: Any) -> dict[str, float | int]:
    """
    Build raw (unwinsorized, unscaled) LightGBM features from a Snapshot.

    The predictor will apply winsorize+zscore across the inference cross-section.
    """
    adjusted_closes = getattr(snapshot, "adjusted_closes", [])
    total_return_returns = getattr(snapshot, "returns", [])
    idx = compute_total_return_index(adjusted_closes, total_return_returns)
    if not idx:
        return {}

    # Daily total returns from the synthetic index.
    daily_returns: list[float] = []
    for i in range(1, len(idx)):
        prev = idx[i - 1]
        daily_returns.append((idx[i] / prev) - 1.0 if prev != 0 else 0.0)

    features: dict[str, float | int] = {}

    # Trailing returns.
    for w in (5, 21, 63, 126, 252):
        v = trailing_return(idx, w)
        if v is not None:
            features[f"ret_{w}d"] = float(v)

    # Rolling volatility.
    for w in (21, 63, 126):
        vol = rolling_vol(daily_returns, w)
        if vol is not None:
            features[f"vol_{w}d"] = float(vol)
        dvol = rolling_downside_vol(daily_returns, w)
        if dvol is not None:
            features[f"downside_vol_{w}d"] = float(dvol)

    # Tail risk.
    mdd = max_drawdown(idx, 252)
    if mdd is not None:
        features["max_drawdown_252d"] = float(mdd)

    # Moving-average & 52-week high distances.
    for w in (20, 50, 200):
        r = moving_average_ratio(idx, w)
        if r is not None:
            features[f"dma_ratio_{w}"] = float(r)
    dh = dist_from_high(idx, 252)
    if dh is not None:
        features["dist_to_52w_high"] = float(dh)

    # OHLC-ish proxies (best-effort). If open/high/low are not present in the snapshot,
    # we degrade to 0.0 so the caller can still use the model for partial feature sets.
    adj_opens = getattr(snapshot, "adjusted_opens", None)
    adj_highs = getattr(snapshot, "adjusted_highs", None)
    adj_lows = getattr(snapshot, "adjusted_lows", None)
    gap_proxy_set = False
    if isinstance(adj_opens, list) and len(adj_opens) >= 2:
        open_t = adj_opens[-1][1]
        close_prev = adjusted_closes[-2][1] if len(adjusted_closes) >= 2 else None
        if close_prev and close_prev != 0:
            features["gap_proxy"] = float(open_t / close_prev - 1.0)
            gap_proxy_set = True
    if isinstance(adj_highs, list) and isinstance(adj_lows, list) and adj_highs and adj_lows:
        high_t = adj_highs[-1][1]
        low_t = adj_lows[-1][1]
        if low_t and low_t != 0:
            features["range_proxy"] = float(high_t / low_t - 1.0)
    # Ensure stable presence if manifest expects them.
    if "gap_proxy" not in features:
        features["gap_proxy"] = 0.0
    if "range_proxy" not in features:
        features["range_proxy"] = 0.0

    # Liquidity / liquidity percentile will be computed across snapshots.
    avg_tov = getattr(snapshot, "avg_traded_value", None)
    if avg_tov is not None:
        features["avg_traded_value_20d"] = float(avg_tov)

    # Beta to market proxy (already computed in Snapshot).
    beta = getattr(snapshot, "beta_proxy", None)
    if beta is not None:
        features["beta_proxy"] = float(beta)

    # Sector-relative momentum proxy (use existing sector_strength factor zscore).
    sector_strength = getattr(snapshot, "factor_scores", {}).get("sector_strength", 0.0)
    features["sector_relative_momentum"] = float(sector_strength)

    # Rule-engine factor scores (z-scored).
    factor_scores = getattr(snapshot, "factor_scores", {}) or {}
    for k in ("momentum", "quality", "low_vol", "liquidity", "sector_strength", "size", "beta"):
        features[f"factor_{k}"] = float(factor_scores.get(k, 0.0))


    # Technical indicators (RSI, MACD, EMA, Bollinger, ATR, ADX, candlestick patterns)
    opens_list = [float(v) for _, v in adj_opens] if isinstance(adj_opens, list) and adj_opens else []
    highs_list = [float(v) for _, v in adj_highs] if isinstance(adj_highs, list) and adj_highs else []
    lows_list = [float(v) for _, v in adj_lows] if isinstance(adj_lows, list) and adj_lows else []
    closes_list = [float(v) for _, v in adjusted_closes] if adjusted_closes else []
    if closes_list:
        tech = compute_technical_features(opens_list, highs_list, lows_list, closes_list)
        features.update(tech)

    return features

