import numpy as np
import pandas as pd

from analysis.indicators import adx, bollinger, ema, macd, rsi, stochastic
from analysis.patterns import detect_patterns

FAST_TFS = {"M1", "M5", "M15"}


def class_group(asset_class: str) -> str:
    return "crypto" if asset_class == "crypto" else "fx" if asset_class == "fx" else "other"


def tf_group(tf: str) -> str:
    return "fast" if tf in FAST_TFS else "slow"


def horizon_for(tfg: str) -> int:
    return 30 if tfg == "fast" else 20


def make_features(df: pd.DataFrame, a: pd.Series) -> pd.DataFrame:
    c = df.close
    pat = detect_patterns(df, a)
    rng = (df.high - df.low).replace(0, np.nan)
    _, _, hist = macd(c)
    lo, _, hi = bollinger(c)
    X = pd.DataFrame(index=df.index)
    X["rsi"] = rsi(c)
    X["adx"] = adx(df)[0]
    X["stoch_k"] = stochastic(df)[0]
    X["macd_h"] = hist / a
    X["d_ema20"] = (c - ema(c, 20)) / a
    X["d_ema50"] = (c - ema(c, 50)) / a
    X["d_ema200"] = (c - ema(c, 200)) / a
    X["bb_pos"] = (c - lo) / (hi - lo).replace(0, np.nan)
    X["body"] = (c - df.open) / a
    X["up_wick"] = (df.high - np.maximum(df.open, c)) / rng
    X["lo_wick"] = (np.minimum(df.open, c) - df.low) / rng
    X["ret5"] = c.diff(5) / a
    X["ret20"] = c.diff(20) / a
    X["atr_pct"] = a / c
    X["vol_ratio"] = a / a.rolling(50).mean()
    X["bull_pat"] = pat.filter(regex="_bull$").sum(axis=1)
    X["bear_pat"] = pat.filter(regex="_bear$").sum(axis=1)
    hr = (df.index.hour + df.index.minute / 60).values
    X["h_sin"] = np.sin(2 * np.pi * hr / 24)
    X["h_cos"] = np.cos(2 * np.pi * hr / 24)
    return X.replace([np.inf, -np.inf], np.nan)
