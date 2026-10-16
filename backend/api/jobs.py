import asyncio
import logging
import time
from datetime import timedelta

import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.models import BudgetExceeded, DataUnavailable
from core.timeframes import TF_SEC, expected_last_open
from core.utils import utc_now
from data.instruments import active_instruments
from signals.engine import analyze

log = logging.getLogger("mie.jobs")


class Runner:
    def __init__(self, s, db, router, fund, models, store, budget):
        self.s, self.db, self.router, self.fund = s, db, router, fund
        self.models, self.store, self.budget = models, store, budget
        act = active_instruments(s)
        self.crypto = [i for i in act if i.provider == "binance"]
        self.td = {i.symbol: i for i in act if i.provider == "twelvedata"}
        self.crypto_tfs = [t for t in s.crypto_tfs if t in TF_SEC]
        self.done: dict = {}
        self.tries: dict = {}
        self.sem = asyncio.Semaphore(4)
        self.last_run: dict = {}
        self.errors: list = []

    def _err(self, where, e):
        msg = f"{utc_now():%H:%M:%S} {where}: {type(e).__name__}: {str(e)[:160]}"
        self.errors = (self.errors + [msg])[-20:]
        log.warning(msg)

    async def init(self):
        await self.budget.load()
        self.budget.build_jobs(list(self.td.values()), self.s)
        for sym, tf, ts in await self.router.warm():
            self.budget.mark_warm(sym, tf, ts)
        await self.models.reload()
        await self.store.load()
        asyncio.get_running_loop().create_task(self._initial())

    async def _initial(self):
        """Первый расчёт по прогретому кэшу (без трат кредитов)."""
        for j in self.budget.jobs.values():
            if j.primary:
                await self.analyze_store(self.td[j.symbol], j.tf, "cache")

    async def analyze_store(self, inst, tf, mode):
        try:
            sig = await analyze(self.router, self.fund, self.models, inst, tf, mode)
            await self.store.put(sig)
            return sig
        except DataUnavailable as e:
            log.debug("analyze %s %s: %s", inst.symbol, tf, e)
        except Exception as e:
            self._err(f"analyze {inst.symbol} {tf}", e)
        return None

    # ---------- крипта: анализ при закрытии каждой свечи ----------
    async def _crypto_one(self, inst, tf, exp):
        async with self.sem:
            sig = await self.analyze_store(inst, tf, "auto")
        k = (inst.symbol, tf)
        if sig and pd.Timestamp(sig.candle_ts).timestamp() >= exp - 1:
            self.done[k] = exp
            self.tries.pop(k, None)
        else:
            self.tries[k] = self.tries.get(k, 0) + 1
            if self.tries[k] >= 6:
                self.done[k] = exp

    async def crypto_cycle(self):
        self.last_run["crypto_cycle"] = utc_now().isoformat(timespec="seconds")
        now = time.time()
        tasks = []
        for inst in self.crypto:
            for tf in self.crypto_tfs:
                exp = expected_last_open(tf, now)
                if exp is None or self.done.get((inst.symbol, tf), 0) >= exp:
                    continue
                if now < exp + TF_SEC[tf] + 2:
                    continue
                tasks.append(self._crypto_one(inst, tf, exp))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ---------- Twelve Data: по бюджету ----------
    async def td_cycle(self):
        self.last_run["td_cycle"] = utc_now().isoformat(timespec="seconds")
        if not self.td or not self.budget.scheduler_allowed():
            return
        job = self.budget.next_job(self.td, self.store.max_abs_score, self.router.disabled)
        if not job:
            return
        inst = self.td[job.symbol]
        try:
            c = await self.router.refresh(inst, job.tf, 500, "scheduler")
            self.budget.mark_ok(job, c.df.index[-1].timestamp())
            if job.primary and job.empty == 0:
                await self.analyze_store(inst, job.tf, "cache")
        except BudgetExceeded:
            pass
        except Exception as e:
            self.budget.mark_fail(job)
            self.router._note(job.symbol, job.tf, e)

    # ---------- обслуживание ----------
    async def housekeeping(self):
        self.last_run["housekeeping"] = utc_now().isoformat(timespec="seconds")
        for name, coro in (("calendar", self.fund.events()),
                           ("cleanup", self.store.cleanup(self.s.retention_days)),
                           ("heartbeat", self.db.upsert("heartbeat", [{"id": 1, "ts": utc_now().isoformat()}],
                                                        on_conflict="id") if self.db.enabled else asyncio.sleep(0))):
            try:
                await coro
            except Exception as e:
                self._err(name, e)

    async def reload_models(self):
        self.last_run["reload_models"] = utc_now().isoformat(timespec="seconds")
        await self.models.reload()


def build_scheduler(r: Runner) -> AsyncIOScheduler:
    sch = AsyncIOScheduler(timezone="UTC")
    start = utc_now() + timedelta(seconds=8)
    opts = dict(max_instances=1, coalesce=True, misfire_grace_time=30)
    sch.add_job(r.crypto_cycle, "interval", seconds=10, id="crypto", next_run_time=start, **opts)
    sch.add_job(r.td_cycle, "interval", seconds=9, id="td", next_run_time=start, **opts)
    sch.add_job(r.housekeeping, "interval", minutes=30, id="house", next_run_time=start, **opts)
    sch.add_job(r.reload_models, "interval", hours=3, id="models", **opts)
    return sch
