from __future__ import annotations
import math


def _ema(values: list[float], period: int) -> list[float]:
    if not values or period <= 0:
        return []
    k = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def ema_ratio(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    ema_series = _ema(closes, period)
    if not ema_series or ema_series[-1] == 0:
        return None
    return closes[-1] / ema_series[-1] - 1.0


def macd_signal(closes: list[float]) -> float | None:
    if len(closes) < 35:
        return None
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    if len(macd_line) < 9:
        return None
    signal_line = _ema(macd_line, 9)
    return macd_line[-1] - signal_line[-1]


def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    n = min(len(highs), len(lows), len(closes))
    if n < period * 2:
        return None
    highs, lows, closes = highs[-n:], lows[-n:], closes[-n:]
    tr_list, pdm_list, ndm_list = [], [], []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        up = highs[i] - highs[i-1]
        dn = lows[i-1] - lows[i]
        pdm_list.append(up if up > dn and up > 0 else 0.0)
        ndm_list.append(dn if dn > up and dn > 0 else 0.0)
        tr_list.append(tr)

    def wilder(lst):
        s = [sum(lst[:period])]
        for v in lst[period:]:
            s.append(s[-1] - s[-1] / period + v)
        return s

    atr_s = wilder(tr_list)
    pdm_s = wilder(pdm_list)
    ndm_s = wilder(ndm_list)
    if not atr_s or atr_s[-1] == 0:
        return None
    pdi = 100 * pdm_s[-1] / atr_s[-1]
    ndi = 100 * ndm_s[-1] / atr_s[-1]
    dx = 100 * abs(pdi - ndi) / (pdi + ndi) if (pdi + ndi) > 0 else 0.0
    return dx


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def atr_normalized(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return None
    trs = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    atr_val = sum(trs[-period:]) / period
    return atr_val / closes[-1] if closes[-1] != 0 else None


def bollinger_pct_b(closes: list[float], period: int = 20, num_std: float = 2.0) -> float | None:
    if len(closes) < period:
        return None
    window = closes[-period:]
    ma = sum(window) / period
    std = math.sqrt(sum((x - ma) ** 2 for x in window) / period)
    upper = ma + num_std * std
    lower = ma - num_std * std
    band_width = upper - lower
    if band_width == 0:
        return 0.5
    return (closes[-1] - lower) / band_width


def bollinger_bandwidth(closes: list[float], period: int = 20, num_std: float = 2.0) -> float | None:
    if len(closes) < period:
        return None
    window = closes[-period:]
    ma = sum(window) / period
    std = math.sqrt(sum((x - ma) ** 2 for x in window) / period)
    return (2 * num_std * std) / ma if ma != 0 else None


def _body(o, c): return abs(c - o)
def _upper_shadow(o, h, c): return h - max(o, c)
def _lower_shadow(o, l, c): return min(o, c) - l
def _range(h, l): return h - l if h != l else 1e-8


def pattern_hammer(opens, highs, lows, closes):
    if len(closes) < 2:
        return 0
    o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
    body = _body(o, c)
    lower = _lower_shadow(o, l, c)
    upper = _upper_shadow(o, h, c)
    rng = _range(h, l)
    if body < 0.3 * rng and lower > 2 * body and upper < 0.1 * rng:
        return 1 if closes[-1] < closes[-2] else -1
    return 0


def pattern_shooting_star(opens, highs, lows, closes):
    if not opens:
        return 0
    o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
    body = _body(o, c)
    upper = _upper_shadow(o, h, c)
    lower = _lower_shadow(o, l, c)
    rng = _range(h, l)
    if body < 0.3 * rng and upper > 2 * body and lower < 0.1 * rng:
        return -1
    return 0


def pattern_engulfing(opens, highs, lows, closes):
    if len(opens) < 2:
        return 0
    o1, c1 = opens[-2], closes[-2]
    o2, c2 = opens[-1], closes[-1]
    if c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1:
        return 1
    if c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1:
        return -1
    return 0


def pattern_marubozu(opens, highs, lows, closes):
    if not opens:
        return 0
    o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
    body = _body(o, c)
    rng = _range(h, l)
    if body > 0.95 * rng:
        return 1 if c > o else -1
    return 0


def pattern_three_candles(opens, highs, lows, closes):
    if len(closes) < 3:
        return 0
    last3_bull = all(closes[i] > opens[i] and closes[i] > closes[i-1] for i in range(-3, 0))
    last3_bear = all(closes[i] < opens[i] and closes[i] < closes[i-1] for i in range(-3, 0))
    if last3_bull:
        return 1
    if last3_bear:
        return -1
    return 0


def compute_technical_features(opens, highs, lows, closes):
    feats = {}
    v = rsi(closes)
    if v is not None:
        feats["rsi_14"] = v
        feats["rsi_14_normalized"] = (v - 50) / 50

    v = macd_signal(closes)
    if v is not None and closes[-1] != 0:
        feats["macd_signal_normalized"] = v / closes[-1]

    for period in (9, 21, 50, 200):
        v = ema_ratio(closes, period)
        if v is not None:
            feats[f"ema_ratio_{period}"] = v

    e9 = ema_ratio(closes, 9)
    e21 = ema_ratio(closes, 21)
    e50 = ema_ratio(closes, 50)
    if e9 is not None and e21 is not None:
        feats["ema_9_above_21"] = 1.0 if e9 > e21 else 0.0
    if e21 is not None and e50 is not None:
        feats["ema_21_above_50"] = 1.0 if e21 > e50 else 0.0

    v = bollinger_pct_b(closes)
    if v is not None:
        feats["bb_pct_b"] = v
    v = bollinger_bandwidth(closes)
    if v is not None:
        feats["bb_bandwidth"] = v

    if highs and lows:
        v = atr_normalized(highs, lows, closes)
        if v is not None:
            feats["atr_normalized"] = v
        v = adx(highs, lows, closes)
        if v is not None:
            feats["adx_14"] = v
            feats["adx_trending"] = 1.0 if v > 25 else 0.0

    if opens and highs and lows:
        feats["candle_hammer"] = float(pattern_hammer(opens, highs, lows, closes))
        feats["candle_shooting_star"] = float(pattern_shooting_star(opens, highs, lows, closes))
        feats["candle_engulfing"] = float(pattern_engulfing(opens, highs, lows, closes))
        feats["candle_marubozu"] = float(pattern_marubozu(opens, highs, lows, closes))
        feats["candle_three_candles"] = float(pattern_three_candles(opens, highs, lows, closes))

    return feats
