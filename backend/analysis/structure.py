import numpy as np

from core.utils import rnd


def swings(df, left=3, right=3):
    """Фрактальные swing'и. confirmed = индекс бара, когда swing стал известен (без look-ahead)."""
    h, l, n = df.high.values, df.low.values, len(df)
    out = []
    for i in range(left, n - right):
        if h[i] > h[i - left:i].max() and h[i] >= h[i + 1:i + right + 1].max():
            out.append(dict(type="H", idx=i, price=float(h[i]), confirmed=i + right))
        if l[i] < l[i - left:i].min() and l[i] <= l[i + 1:i + right + 1].min():
            out.append(dict(type="L", idx=i, price=float(l[i]), confirmed=i + right))
    return sorted(out, key=lambda s: s["confirmed"])


def market_structure(df, sw):
    """BOS = пробой по тренду, CHoCH = пробой против тренда (по закрытию)."""
    events, trend, last_h, last_l, ptr = [], 0, None, None, 0
    closes, idx = df.close.values, df.index
    for i in range(len(df)):
        while ptr < len(sw) and sw[ptr]["confirmed"] <= i:
            if sw[ptr]["type"] == "H":
                last_h = sw[ptr]
            else:
                last_l = sw[ptr]
            ptr += 1
        if last_h and closes[i] > last_h["price"]:
            events.append(dict(type="BOS" if trend >= 0 else "CHoCH", dir="up",
                               level=rnd(last_h["price"]), ts=idx[i].isoformat()))
            trend, last_h = 1, None
        elif last_l and closes[i] < last_l["price"]:
            events.append(dict(type="BOS" if trend <= 0 else "CHoCH", dir="down",
                               level=rnd(last_l["price"]), ts=idx[i].isoformat()))
            trend, last_l = -1, None
    return trend, events


def sr_levels(sw, df, atr_v, price, tol_atr=0.5, top=3):
    """Кластеризация swing-цен (близкие < 0.5 ATR сливаются), сила = число касаний.
    Если кластеров мало, добираем экстремумы окон 50/100/200/всё."""
    prices = sorted(s["price"] for s in sw[-80:])
    clusters = []
    for p in prices:
        if clusters and p - np.mean(clusters[-1]) <= tol_atr * atr_v:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    lv = [(float(np.mean(c)), len(c)) for c in clusters]
    for w in (50, 100, 200, len(df)):
        seg = df.tail(w)
        for p in (float(seg.high.max()), float(seg.low.min())):
            if all(abs(p - q) > tol_atr * atr_v for q, _ in lv):
                lv.append((p, 1))
    sup = sorted([x for x in lv if x[0] < price], key=lambda x: -x[0])[:top]
    res = sorted([x for x in lv if x[0] > price], key=lambda x: x[0])[:top]
    f = lambda arr: [dict(price=rnd(p), touches=n) for p, n in arr]
    return f(sup), f(res)


def fair_value_gaps(df, atr_v, lookback=120, min_size=0.15):
    """Незакрытые FVG: bull = low[i] > high[i-2]; bear = high[i] < low[i-2]."""
    h, l, idx = df.high.values, df.low.values, df.index
    out = []
    for i in range(max(2, len(df) - lookback), len(df)):
        if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= min_size * atr_v:
            lo_, hi_ = h[i - 2], l[i]
            if (l[i + 1:] > lo_).all():
                out.append(dict(dir="bull", lo=rnd(lo_), hi=rnd(hi_), ts=idx[i - 1].isoformat()))
        elif h[i] < l[i - 2] and (l[i - 2] - h[i]) >= min_size * atr_v:
            lo_, hi_ = h[i], l[i - 2]
            if (h[i + 1:] < hi_).all():
                out.append(dict(dir="bear", lo=rnd(lo_), hi=rnd(hi_), ts=idx[i - 1].isoformat()))
    return out


def order_blocks(df, atr_s, lookback=120, disp=1.5):
    """OB = последняя противоположная свеча перед импульсом (тело > 1.5 ATR), ещё не тронутая."""
    o, c, h, l = df.open.values, df.close.values, df.high.values, df.low.values
    a, idx, n = atr_s.values, df.index, len(df)
    out, used = [], set()
    for i in range(max(6, n - lookback), n):
        if np.isnan(a[i]) or abs(c[i] - o[i]) < disp * a[i]:
            continue
        bull_imp = c[i] > o[i]
        for j in range(i - 1, max(i - 6, 0), -1):
            if (c[j] < o[j]) == bull_imp:
                if j in used:
                    break
                used.add(j)
                lo_, hi_ = float(l[j]), float(h[j])
                touched = (l[i + 1:] <= hi_).any() if bull_imp else (h[i + 1:] >= lo_).any()
                if not touched:
                    out.append(dict(dir="bull" if bull_imp else "bear", lo=rnd(lo_), hi=rnd(hi_),
                                    ts=idx[j].isoformat()))
                break
    return out


def liquidity_pools(sw, atr_v, tol=0.15):
    """Equal highs/lows: зоны стопов толпы."""
    pools, seen = [], set()
    for t in ("H", "L"):
        pts = [s["price"] for s in sw[-40:] if s["type"] == t]
        for i, p in enumerate(pts):
            if any(abs(p - q) <= tol * atr_v for q in pts[i + 1:]):
                key = (t, rnd(p))
                if key not in seen:
                    seen.add(key)
                    pools.append(dict(type=t, price=rnd(p)))
    return pools
