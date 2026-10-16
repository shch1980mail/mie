import numpy as np
import pandas as pd

W = {
    "pin_bull": .6, "pin_bear": .6, "hammer_bull": .55, "shooting_star_bear": .55,
    "engulfing_bull": .8, "engulfing_bear": .8, "harami_bull": .35, "harami_bear": .35,
    "morning_star_bull": .9, "evening_star_bear": .9,
    "three_soldiers_bull": .85, "three_crows_bear": .85,
    "tweezer_bottom_bull": .5, "tweezer_top_bear": .5,
    "marubozu_bull": .4, "marubozu_bear": .4,
}


def _sb(s, k=1):
    """Сдвиг булевой серии без появления NaN."""
    return s.shift(k, fill_value=False)


def detect_patterns(df: pd.DataFrame, atr_s: pd.Series) -> pd.DataFrame:
    o, h, l, c = df.open, df.high, df.low, df.close
    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    up_w = h - np.maximum(o, c)
    lo_w = np.minimum(o, c) - l
    bull, bear = c > o, c < o
    big = rng >= 0.8 * atr_s
    down = c.shift(1) < c.shift(6)
    up = c.shift(1) > c.shift(6)

    p = pd.DataFrame(index=df.index)
    p["doji"] = body <= 0.1 * rng
    p["inside_bar"] = (h < h.shift()) & (l > l.shift())
    p["outside_bar"] = (h > h.shift()) & (l < l.shift())
    p["marubozu_bull"] = bull & (body / rng >= .9) & big
    p["marubozu_bear"] = bear & (body / rng >= .9) & big

    pin_b = (lo_w >= 2 * body) & (lo_w >= .6 * rng) & (up_w <= .25 * rng) & big
    pin_s = (up_w >= 2 * body) & (up_w >= .6 * rng) & (lo_w <= .25 * rng) & big
    p["pin_bull"], p["pin_bear"] = pin_b, pin_s
    p["hammer_bull"] = pin_b & down
    p["shooting_star_bear"] = pin_s & up

    pbody = body.shift()
    p["engulfing_bull"] = _sb(bear) & bull & (c >= o.shift()) & (o <= c.shift()) & (body > pbody)
    p["engulfing_bear"] = _sb(bull) & bear & (c <= o.shift()) & (o >= c.shift()) & (body > pbody)
    p["harami_bull"] = _sb(bear) & bull & (o >= c.shift()) & (c <= o.shift()) & (body < pbody)
    p["harami_bear"] = _sb(bull) & bear & (o <= c.shift()) & (c >= o.shift()) & (body < pbody)

    mid2 = (o.shift(2) + c.shift(2)) / 2
    small1 = body.shift() <= 0.3 * body.shift(2)
    big2 = body.shift(2) >= .8 * atr_s.shift(2)
    p["morning_star_bull"] = _sb(bear, 2) & small1 & bull & (c > mid2) & big2
    p["evening_star_bear"] = _sb(bull, 2) & small1 & bear & (c < mid2) & big2

    seq_b = bull & _sb(bull) & _sb(bull, 2)
    prog_b = (c > c.shift()) & (c.shift() > c.shift(2))
    open_b = (o > o.shift()) & (o < c.shift()) & (o.shift() > o.shift(2)) & (o.shift() < c.shift(2))
    seq_s = bear & _sb(bear) & _sb(bear, 2)
    prog_s = (c < c.shift()) & (c.shift() < c.shift(2))
    open_s = (o < o.shift()) & (o > c.shift()) & (o.shift() < o.shift(2)) & (o.shift() > c.shift(2))
    p["three_soldiers_bull"] = seq_b & prog_b & open_b
    p["three_crows_bear"] = seq_s & prog_s & open_s

    tol = 0.05 * atr_s
    p["tweezer_bottom_bull"] = _sb(bear) & bull & ((l - l.shift()).abs() <= tol)
    p["tweezer_top_bear"] = _sb(bull) & bear & ((h - h.shift()).abs() <= tol)
    return p.fillna(False).astype(bool)


def candle_score(pat: pd.DataFrame, price: float, atr_v: float, supports, resistances):
    """Последние 3 свечи с затуханием; паттерн у уровня усиливается ×1.5."""
    near = lambda lv: any(abs(price - x) <= 0.75 * atr_v for x in lv)
    s, hits = 0.0, []
    for decay, (_, row) in zip((0.5, 0.75, 1.0), pat.iloc[-3:].iterrows()):
        for name, fired in row.items():
            if not fired or name not in W:
                continue
            w = W[name] * decay
            if name.endswith("_bull") and near(supports):
                w *= 1.5
            if name.endswith("_bear") and near(resistances):
                w *= 1.5
            s += w if name.endswith("_bull") else -w
            hits.append(name)
    ctx = [n for n in ("doji", "inside_bar", "outside_bar") if bool(pat.iloc[-1][n])]
    return float(np.tanh(s)), hits + [f"ctx:{x}" for x in ctx]
