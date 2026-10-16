import pandas as pd

TF_SEC = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600,
          "H4": 14400, "D1": 86400, "W1": 604800, "MN": 2592000}
TF_ORDER = list(TF_SEC)


def expected_last_open(tf: str, now: float):
    """Время открытия последней ЗАКРЫТОЙ свечи (epoch, сек). Для W1/MN не определено."""
    if tf in ("W1", "MN"):
        return None
    s = TF_SEC[tf]
    return (int(now) // s) * s - s


def candle_ends(index: pd.DatetimeIndex, tf: str):
    """Время закрытия каждой свечи по её времени открытия."""
    if tf == "MN":
        return index + pd.offsets.MonthBegin(1)
    return index + pd.Timedelta(seconds=TF_SEC[tf])
