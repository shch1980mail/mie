import numpy as np
import pandas as pd


def barrier_labels(df: pd.DataFrame, a: pd.Series, side: int, horizon: int = 30, k: float = 1.0) -> pd.Series:
    """Triple-barrier на чистом numpy. Симметричные барьеры ±k·ATR от закрытия сигнальной свечи.
    1 = нужная сторона достигнута первой; 0 = противоположная (или обе в одной свече: пессимистично);
    NaN = за horizon баров ничего не достигнуто / нет будущего."""
    h, l, c, av = df.high.values, df.low.values, df.close.values, a.values
    n = len(c)
    up, dn = c + k * av, c - k * av
    big = horizon + 1
    t_up = np.full(n, big)
    t_dn = np.full(n, big)
    for s in range(1, horizon + 1):
        hs = np.full(n, -np.inf)
        ls = np.full(n, np.inf)
        hs[:n - s] = h[s:]
        ls[:n - s] = l[s:]
        t_up = np.where((t_up == big) & (hs >= up), s, t_up)
        t_dn = np.where((t_dn == big) & (ls <= dn), s, t_dn)
    if side == 1:
        win, loss = t_up < t_dn, t_dn <= t_up
    else:
        win, loss = t_dn < t_up, t_up <= t_dn
    resolved = (t_up < big) | (t_dn < big)
    y = np.where(win & resolved, 1.0, np.where(loss & resolved, 0.0, np.nan))
    y[n - horizon:] = np.nan
    y[~np.isfinite(av)] = np.nan
    return pd.Series(y, index=df.index)


def p_from_symmetric(p_sym: float, a: float, b: float) -> float:
    """Перевод вероятности «+1 ATR раньше −1 ATR» в вероятность «+a раньше −b» (в ATR).
    Диффузионная модель с дрейфом: φ = logit(p_sym), P = (1 − e^{φb}) / (e^{−φa} − e^{φb}).
    Без дрейфа (φ=0) формула даёт b/(a+b)."""
    p_sym = float(np.clip(p_sym, 0.02, 0.98))
    phi = float(np.log(p_sym / (1 - p_sym)))
    if abs(phi) < 1e-6:
        return b / (a + b)
    num = 1 - np.exp(phi * b)
    den = np.exp(-phi * a) - np.exp(phi * b)
    return float(np.clip(num / den, 0.01, 0.99))
