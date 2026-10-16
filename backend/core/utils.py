import datetime as dt
import math

import numpy as np
import pandas as pd


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def sanitize(o):
    """Рекурсивно приводит к JSON-безопасному виду (NaN/inf -> None, numpy -> python)."""
    if o is None or isinstance(o, (str, bool)):
        return o
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [sanitize(v) for v in o]
    if isinstance(o, np.ndarray):
        return [sanitize(v) for v in o.tolist()]
    if hasattr(o, "model_dump"):
        return sanitize(o.model_dump())
    return str(o)


def rnd(x):
    """Округление цены с учётом порядка величины."""
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    a = abs(x)
    d = 6 if a < 1 else 5 if a < 10 else 4 if a < 100 else 3 if a < 10000 else 2
    return round(x, d)
