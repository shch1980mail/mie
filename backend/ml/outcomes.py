"""Разметка исходов сигналов (TP1 / SL / expired). Запуск в Actions: python -m ml.outcomes
Правила: вход по aggressive-цене, обход свечей после сигнала; SL и TP в одной свече = SL (пессимистично).
Не-крипта читается из candle_cache (кредиты Twelve Data не тратятся)."""
import asyncio
import logging
import sys
import time

import httpx
import pandas as pd

from core.config import get_settings
from core.db import Supabase
from core.timeframes import TF_SEC
from core.utils import utc_now
from data.budget_scheduler import BudgetScheduler
from data.instruments import INSTRUMENTS
from data.providers import DataRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("outcomes")

OUTCOME_BARS = {"M1": 120, "M5": 96, "M15": 64, "M30": 48, "H1": 48, "H4": 30, "D1": 20, "W1": 10, "MN": 6}


def simulate(side, entry, sl, tp1, tp2, fut: pd.DataFrame):
    risk = abs(entry - sl)
    if risk <= 0:
        return "no_data", 0.0
    for _, r in fut.iterrows():
        hit_sl = r.low <= sl if side == 1 else r.high >= sl
        hit_tp = r.high >= tp1 if side == 1 else r.low <= tp1
        if hit_sl:
            return "sl", -1.0
        if hit_tp:
            return "tp1", abs(tp1 - entry) / risk
    return None, (fut.close.iloc[-1] - entry) * side / risk


async def main():
    s = get_settings()
    db = Supabase(s.supabase_url, s.supabase_service_key)
    if not db.enabled:
        log.error("Supabase не настроен")
        sys.exit(1)
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "mie-outcomes/1.0"},
                                 follow_redirects=True) as http:
        router = DataRouter(s, db, BudgetScheduler(s, db), http)
        await router.warm()
        rows = await db.select("signals", {
            "select": "id,symbol,timeframe,candle_ts,payload", "outcome": "is.null",
            "order": "candle_ts.asc", "limit": "300"})
        log.info("неразмеченных сигналов: %d", len(rows))
        done = 0
        for r in rows:
            inst = INSTRUMENTS.get(r["symbol"])
            tf, p = r["timeframe"], r["payload"]
            try:
                t0 = pd.Timestamp(r["candle_ts"])
                entry, sl = float(p["entry"]["aggressive"]), float(p["stop_loss"])
                tps = p["take_profits"]
                side = 1 if p["bias"] == "bullish" else -1
                n_bars = OUTCOME_BARS[tf]
                age_s = time.time() - t0.timestamp()
                c = await router.candles(inst, tf, 500, "auto" if inst.provider == "binance" else "cache")
                df = c.df
                covered = df.index[0] <= t0
                fut = df[df.index > t0].head(n_bars)
                if not covered or fut.empty:
                    outcome, rm = ("no_data", 0.0) if age_s > 6 * 3600 else (None, 0.0)
                else:
                    outcome, rm = simulate(side, entry, sl, float(tps[0]["price"]), float(tps[1]["price"]), fut)
                    if outcome is None:
                        if len(fut) >= n_bars or age_s > 3 * n_bars * TF_SEC[tf]:
                            outcome = "expired"
                if outcome is None:
                    continue
                await db.update("signals", {"id": f"eq.{r['id']}"}, {
                    "outcome": outcome, "r_multiple": round(float(rm), 3),
                    "resolved_at": utc_now().isoformat()})
                done += 1
            except Exception as e:
                log.warning("сигнал %s: %s", r.get("id"), e)
        log.info("размечено: %d", done)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
