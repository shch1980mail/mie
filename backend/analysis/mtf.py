import asyncio

import numpy as np

from analysis.indicators import ema
from analysis.structure import market_structure, swings

HTF = {"M1": ["M5", "M15", "H1"], "M5": ["M15", "H1", "H4"], "M15": ["H1", "H4", "D1"],
       "M30": ["H4", "D1"], "H1": ["H4", "D1", "W1"], "H4": ["D1", "W1"],
       "D1": ["W1", "MN"], "W1": ["MN"], "MN": []}


def tf_bias(d) -> float:
    if len(d) < 60:
        return 0.0
    c = d.close
    e50, e200 = ema(c, 50), ema(c, 200)
    s = np.sign(c.iloc[-1] - e50.iloc[-1]) * .5 + np.sign(e50.iloc[-1] - e200.iloc[-1]) * .25
    trend, _ = market_structure(d, swings(d))
    return float(s + trend * .25)


async def mtf_bias(router, inst, tf, mode="cache") -> dict:
    """Взвешенный bias старших ТФ. Недоступные ТФ пропускаются, веса пересчитываются."""
    tfs = HTF.get(tf, [])
    if not tfs:
        return dict(bias=0.0, per_tf={})
    res = await asyncio.gather(*[router.candles(inst, t, 300, mode) for t in tfs], return_exceptions=True)
    base = [.2, .3, .5][-len(tfs):]
    per, w = {}, {}
    for t, r, wt in zip(tfs, res, base):
        if isinstance(r, Exception) or len(r.df) < 60:
            continue
        per[t], w[t] = tf_bias(r.df), wt
    if not per:
        return dict(bias=0.0, per_tf={})
    bias = sum(per[t] * w[t] for t in per) / sum(w.values())
    return dict(bias=float(np.clip(bias, -1, 1)), per_tf={k: round(v, 2) for k, v in per.items()})
