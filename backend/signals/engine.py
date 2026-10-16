import asyncio
import time

import numpy as np

from analysis.indicators import atr, tech_score
from analysis.mtf import mtf_bias
from analysis.patterns import candle_score, detect_patterns
from analysis.structure import (fair_value_gaps, liquidity_pools, market_structure, order_blocks,
                                sr_levels, swings)
from core.models import DataUnavailable, Signal, Target
from core.timeframes import TF_SEC
from core.utils import rnd, utc_now
from data.instruments import is_open
from ml.barrier import p_from_symmetric
from ml.features import class_group, tf_group

PROFILES = {
    "scalp": dict(w=(.50, .30, .20), sl_min=1.0, sl_max=2.5),
    "intraday": dict(w=(.40, .30, .30), sl_min=1.2, sl_max=3.0),
    "swing": dict(w=(.30, .30, .40), sl_min=1.5, sl_max=3.5),
}
BIAS_T = 0.20


def profile_for(tf: str) -> str:
    return "scalp" if tf in ("M1", "M5", "M15") else "intraday" if tf in ("M30", "H1", "H4") else "swing"


def _targets(side, entry, risk, lvls):
    beyond = sorted([x for x in lvls if side * (x - entry) >= 1.2 * risk], key=lambda x: side * x)
    tp1 = beyond[0] if beyond else entry + side * 1.5 * risk
    tp2c = beyond[1] if len(beyond) > 1 else None
    tp2 = tp2c if tp2c is not None and side * (tp2c - tp1) > 0 \
        else entry + side * max(2.5 * risk, 1.6 * abs(tp1 - entry))
    return tp1, tp2


def build_signal(inst, tf, candles, mtf, fund, models) -> Signal:
    df = candles.df
    if len(df) < 60:
        raise DataUnavailable("слишком мало свечей для анализа")
    a_s = atr(df)
    a, price = float(a_s.iloc[-1]), float(df.close.iloc[-1])
    if not np.isfinite(a) or a <= 0:
        raise DataUnavailable("ATR недоступен")
    prof = PROFILES[profile_for(tf)]
    now = time.time()

    sw = swings(df)
    trend, events = market_structure(df, sw)
    sup, res = sr_levels(sw, df, a, price)
    fvg, obs = fair_value_gaps(df, a), order_blocks(df, a_s)
    pools = liquidity_pools(sw, a)
    pat = detect_patterns(df, a_s)
    cs, hits = candle_score(pat, price, a, [x["price"] for x in sup], [x["price"] for x in res])
    ts_, tdet = tech_score(df, sw)

    wc, wt, wf = prof["w"]
    raw = wc * cs + wt * ts_ + wf * fund["score"]
    m = mtf["bias"]
    if abs(m) >= 0.05:
        raw *= (1 + .3 * min(abs(m), 1.0)) if raw * m > 0 else 0.5
    raw = float(np.clip(raw, -1, 1))
    bias = "bullish" if raw > BIAS_T else "bearish" if raw < -BIAS_T else "neutral"

    risks = list(fund["risks"])
    market_open = is_open(inst, __import__("datetime").datetime.fromtimestamp(now, __import__("datetime").timezone.utc))
    last_age = now - df.index[-1].timestamp() - TF_SEC[tf]
    if candles.stale:
        risks.append("Данные устарели: источник недоступен, сигнал построен по кэшу")
    elif inst.provider == "binance" and last_age > 3 * TF_SEC[tf]:
        risks.append("Последняя свеча старше трёх периодов: проверьте источник данных")
    if not market_open:
        risks.append("Рынок закрыт или вне основной сессии: сигнал по последним доступным свечам")
    if fund["blackout"]:
        risks.append("Blackout: вход заблокирован до стабилизации после новости")
    if tdet["adx"] < 15:
        risks.append("ADX<15: рынок во флэте, повышен риск ложных пробоев")
    if mtf["per_tf"] and raw * m < 0:
        risks.append("Контртрендовый сетап против старших ТФ")
    if not mtf["per_tf"]:
        risks.append("Старшие ТФ недоступны: MTF-фильтр не применён")
    if inst.asset_class == "crypto" and 0 <= time.gmtime(now).tm_wday <= 6 and time.gmtime(now).tm_wday >= 5:
        risks.append("Выходные: крипторынок работает, но ликвидность ниже")

    base = dict(
        symbol=inst.symbol, name=inst.name, asset_class=inst.asset_class, timeframe=tf,
        candle_ts=df.index[-1].isoformat(), generated_at=utc_now().isoformat(),
        price=rnd(price), atr=rnd(a), score=round(raw, 3), stale=candles.stale,
        levels=dict(support=sup, resistance=res, fvg=fvg[-4:], order_blocks=obs[-4:], liquidity=pools[-4:]),
        data=dict(source=candles.source, bars=len(df), profile=profile_for(tf)),
        rationale=dict(
            candles=dict(score=round(cs, 2), patterns=hits),
            technical=dict(score=round(ts_, 2), **tdet),
            fundamental=dict(score=round(fund["score"], 2), notes=fund["notes"],
                             cot_pct=fund["cot_pct"], fear_greed=fund.get("fear_greed")),
            structure=dict(trend=trend, last_event=events[-1] if events else None),
            mtf=mtf, weights=dict(candles=wc, technical=wt, fundamental=wf)))

    if bias == "neutral" or fund["blackout"]:
        return Signal(bias=bias, risks=risks, **base)

    side = 1 if bias == "bullish" else -1
    aggressive = price
    zones = [z for z in (fvg + obs) if z["dir"] == ("bull" if side == 1 else "bear")]
    near = [z for z in zones if (z["hi"] < price if side == 1 else z["lo"] > price)
            and abs(price - (z["hi"] if side == 1 else z["lo"])) <= 2 * a]
    zone = min(near, key=lambda z: abs(price - (z["lo"] + z["hi"]) / 2), default=None)
    conservative = (zone["lo"] + zone["hi"]) / 2 if zone else None

    pts = [s["price"] for s in sw if s["type"] == ("L" if side == 1 else "H")
           and (s["price"] < price if side == 1 else s["price"] > price)]
    structural = (pts[-1] - side * .25 * a) if pts else aggressive - side * prof["sl_max"] * a
    if side == 1:
        sl = min(structural, aggressive - prof["sl_min"] * a)
        sl = max(sl, aggressive - prof["sl_max"] * a)
    else:
        sl = max(structural, aggressive + prof["sl_min"] * a)
        sl = min(sl, aggressive + prof["sl_max"] * a)
    risk = abs(aggressive - sl)
    tp1, tp2 = _targets(side, aggressive, risk, [x["price"] for x in (res if side == 1 else sup)])
    rr1, rr2 = abs(tp1 - aggressive) / risk, abs(tp2 - aggressive) / risk

    group = f"{class_group(inst.asset_class)}_{tf_group(tf)}"
    p_sym, minfo = models.predict(group, side, df)
    source = "ml_calibrated"
    if p_sym is None:
        p_sym, source, minfo = float(np.clip(0.5 + 0.10 * abs(raw), 0.5, 0.56)), "heuristic", None
    p1 = p_from_symmetric(p_sym, abs(tp1 - aggressive) / a, risk / a)
    p2 = p_from_symmetric(p_sym, abs(tp2 - aggressive) / a, risk / a)
    exp_r = p1 * rr1 - (1 - p1)
    recommended = bool(exp_r > 0 and market_open and not candles.stale)
    if exp_r <= 0:
        risks.append("Отрицательное матожидание: сетап не рекомендован")
    risks.append("E[R] рассчитано без спреда и комиссий: вычтите издержки брокера")

    base["rationale"]["model"] = dict(group=group, p_symmetric=round(p_sym, 3), source=source, info=minfo)
    return Signal(
        bias=bias, recommended=recommended, probability=round(p1, 3), probability_tp2=round(p2, 3),
        probability_source=source, expectancy_r=round(exp_r, 2),
        entry=dict(aggressive=rnd(aggressive), conservative=rnd(conservative), conservative_zone=zone),
        stop_loss=rnd(sl),
        take_profits=[Target(price=rnd(tp1), rr=round(rr1, 2)), Target(price=rnd(tp2), rr=round(rr2, 2))],
        risks=risks, **base)


async def analyze(router, fund, models, inst, tf, mode="auto") -> Signal:
    c = await router.candles(inst, tf, 500, mode)
    htf_mode = "auto" if inst.provider == "binance" else "cache"
    mtf, f = await asyncio.gather(mtf_bias(router, inst, tf, htf_mode), fund.score_for(inst))
    return await asyncio.to_thread(build_signal, inst, tf, c, mtf, f, models)


async def best_timeframe(router, fund, models, inst, tfs=("M5", "M15", "H1"), mode="auto"):
    """Оптимальный ТФ = максимум E[R] среди рекомендованных сигналов."""
    res = await asyncio.gather(*[analyze(router, fund, models, inst, t, mode) for t in tfs],
                               return_exceptions=True)
    sigs = [r for r in res if not isinstance(r, Exception)]
    ok = [s for s in sigs if s.recommended and s.expectancy_r is not None]
    best = max(ok, key=lambda s: s.expectancy_r, default=None)
    return best, sigs
