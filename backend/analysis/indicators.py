import numpy as np
import pandas as pd


def _last(s, default=0.0) -> float:
    v = float(s.iloc[-1])
    return v if np.isfinite(v) else default


def sma(s, n):
    return s.rolling(n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def wma(s, n):
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: float(np.dot(x, w) / w.sum()), raw=True)


def hma(s, n):
    return wma(2 * wma(s, max(n // 2, 1)) - wma(s, n), max(int(np.sqrt(n)), 1))


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df, n=14):
    pc = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def macd(c, f=12, s=26, sig=9):
    m = ema(c, f) - ema(c, s)
    sg = ema(m, sig)
    return m, sg, m - sg


def bollinger(c, n=20, k=2.0):
    ma, sd = c.rolling(n).mean(), c.rolling(n).std()
    return ma - k * sd, ma, ma + k * sd


def adx(df, n=14):
    up, dn = df.high.diff(), -df.low.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, mdi


def stochastic(df, k=14, d=3):
    ll, hh = df.low.rolling(k).min(), df.high.rolling(k).max()
    kk = 100 * (df.close - ll) / (hh - ll).replace(0, np.nan)
    return kk, kk.rolling(d).mean()


def cci(df, n=20):
    tp = (df.high + df.low + df.close) / 3
    ma = tp.rolling(n).mean()
    md = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - ma) / (0.015 * md.replace(0, np.nan))


def williams_r(df, n=14):
    hh, ll = df.high.rolling(n).max(), df.low.rolling(n).min()
    return -100 * (hh - df.close) / (hh - ll).replace(0, np.nan)


def obv(df):
    return (np.sign(df.close.diff()).fillna(0) * df.volume).cumsum()


def vwap(df):
    day = df.index.normalize()
    tp = (df.high + df.low + df.close) / 3
    cv = df.volume.groupby(day).cumsum().replace(0, np.nan)
    return (tp * df.volume).groupby(day).cumsum() / cv


def ichimoku(df):
    """Положение цены относительно облака (без заглядывания вперёд)."""
    h, l, c = df.high, df.low, df.close
    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    sa = ((tenkan + kijun) / 2).shift(26)
    sb = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    a_, b_, px = float(sa.iloc[-1]), float(sb.iloc[-1]), float(c.iloc[-1])
    if not (np.isfinite(a_) and np.isfinite(b_)):
        return {"pos": 0, "label": "n/a"}
    if px > max(a_, b_):
        return {"pos": 1, "label": "above_cloud"}
    if px < min(a_, b_):
        return {"pos": -1, "label": "below_cloud"}
    return {"pos": 0, "label": "inside_cloud"}


def divergence(series, sw, n_bars, max_age=40):
    """Regular + hidden дивергенции по двум последним swing-точкам."""
    v = series.values
    lows = [s for s in sw if s["type"] == "L"][-2:]
    highs = [s for s in sw if s["type"] == "H"][-2:]
    if len(lows) == 2 and n_bars - lows[1]["idx"] <= max_age:
        a, b = lows
        ia, ib = v[a["idx"]], v[b["idx"]]
        if np.isfinite(ia) and np.isfinite(ib):
            if b["price"] < a["price"] and ib > ia:
                return "bullish_regular"
            if b["price"] > a["price"] and ib < ia:
                return "bullish_hidden"
    if len(highs) == 2 and n_bars - highs[1]["idx"] <= max_age:
        a, b = highs
        ia, ib = v[a["idx"]], v[b["idx"]]
        if np.isfinite(ia) and np.isfinite(ib):
            if b["price"] > a["price"] and ib < ia:
                return "bearish_regular"
            if b["price"] < a["price"] and ib > ia:
                return "bearish_hidden"
    return None


def tech_score(df, sw):
    c, a = df.close, atr(df)
    e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    r = rsi(c)
    _, _, hist = macd(c)
    adx_s, _, _ = adx(df)
    k, _ = stochastic(df)
    lo, mid, hi = bollinger(c)
    ich = ichimoku(df)
    price, av = _last(c), max(_last(a), 1e-12)

    trend = ((price > _last(e20)) + (_last(e20) > _last(e50)) + (_last(e50) > _last(e200)) - 1.5) / 1.5
    mom = float(np.tanh(3 * _last(hist) / av))
    rsi_v, adx_v, k_v = _last(r, 50.0), _last(adx_s), _last(k, 50.0)
    rs = float(np.clip((rsi_v - 50) / 25, -1, 1))
    rsi_s = 0.5 * rs if adx_v > 25 else -0.6 * rs
    st_s = float(np.clip((50 - k_v) / 50, -1, 1)) if adx_v < 20 else 0.0
    div = divergence(r, sw, len(df))
    div_s = {"bullish_regular": .25, "bullish_hidden": .15,
             "bearish_regular": -.25, "bearish_hidden": -.15}.get(div, 0.0)
    score = float(np.clip(.35 * trend + .25 * mom + .20 * rsi_s + .10 * ich["pos"] + .10 * st_s + div_s, -1, 1))

    bw = _last(hi) - _last(lo)
    det = dict(trend=round(float(trend), 2), macd_hist_atr=round(_last(hist) / av, 2),
               rsi=round(rsi_v, 1), adx=round(adx_v, 1), stoch_k=round(k_v, 1),
               cci=round(_last(cci(df)), 1), williams_r=round(_last(williams_r(df), -50.0), 1),
               bb_pos=round((price - _last(lo)) / bw, 2) if bw > 0 else None,
               ichimoku=ich["label"], divergence=div)
    return score, det
