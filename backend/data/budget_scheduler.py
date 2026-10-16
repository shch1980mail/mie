"""Планировщик кредитов Twelve Data.

Правила: <= 700 кредитов/сутки (резерв под ручные запросы), <= 8/мин, пейсинг по времени суток
(бюджет не сгорает утром), торговые часы инструмента, приоритет у символов со свежим сильным
сигналом, экспоненциальный откат, если новых свечей нет (выходные/праздники).
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.utils import utc_now
from data.instruments import is_open

log = logging.getLogger("mie.budget")

JOB_INTERVAL = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 21600, "W1": 86400}
HTF_TD = {"M5": ["M15", "H1", "H4"], "M15": ["H1", "H4", "D1"], "M30": ["H4", "D1"],
          "H1": ["H4", "D1"], "H4": ["D1", "W1"], "D1": ["W1"]}


@dataclass
class Job:
    symbol: str
    tf: str
    primary: bool
    weight: float
    interval: int
    last_ok: float = 0.0
    last_try: float = 0.0
    fails: int = 0
    empty: int = 0
    last_bar: float = 0.0


class BudgetScheduler:
    def __init__(self, s, db):
        self.limit = s.td_daily_limit
        self.per_min = s.td_per_minute
        self.reserve = s.td_reserve_on_demand
        self.burst = s.td_burst
        self.db = db
        self.day = utc_now().strftime("%Y-%m-%d")
        self.used = 0
        self.stamps: deque = deque()
        self.locked_until = 0.0
        self.spent: dict[str, int] = {}
        self.jobs: dict[tuple, Job] = {}
        self.log: deque = deque(maxlen=100)

    # ---------- учёт кредитов ----------
    def _roll(self):
        d = utc_now().strftime("%Y-%m-%d")
        if d != self.day:
            self.day, self.used, self.spent = d, 0, {}
            self.stamps.clear()

    async def load(self):
        if not self.db.enabled:
            return
        try:
            rows = await self.db.select("api_budget", {
                "select": "used", "day": f"eq.{self.day}", "provider": "eq.twelvedata"})
            if rows:
                self.used = max(self.used, int(rows[0]["used"]))
        except Exception as e:
            log.warning("budget load failed: %s", e)

    async def _persist(self):
        try:
            await self.db.upsert("api_budget", [{
                "day": self.day, "provider": "twelvedata", "used": self.used,
                "updated_at": utc_now().isoformat()}], on_conflict="day,provider")
        except Exception as e:
            log.debug("budget persist failed: %s", e)

    def acquire(self, symbol: str, tf: str, on_demand: bool = False) -> bool:
        self._roll()
        now = time.time()
        if now < self.locked_until:
            return False
        cap = self.limit if on_demand else self.limit - self.reserve
        per_min = self.per_min if on_demand else self.per_min - 1
        while self.stamps and now - self.stamps[0] > 60:
            self.stamps.popleft()
        if self.used >= cap or len(self.stamps) >= per_min:
            return False
        self.stamps.append(now)
        self.used += 1
        self.spent[symbol] = self.spent.get(symbol, 0) + 1
        self.log.append(f"{utc_now():%H:%M:%S} {symbol} {tf} {'on-demand' if on_demand else 'sched'}")
        log.info("TD credit: %s %s (%d/%d today)", symbol, tf, self.used, self.limit)
        try:
            asyncio.get_running_loop().create_task(self._persist())
        except RuntimeError:
            pass
        return True

    def hit_minute_limit(self, seconds: int = 65):
        self.locked_until = time.time() + seconds
        log.warning("Twelve Data 429: пауза %ss", seconds)

    def scheduler_allowed(self) -> bool:
        self._roll()
        now = time.time()
        if now < self.locked_until:
            return False
        cap = self.limit - self.reserve
        if self.used >= cap:
            return False
        frac = (now % 86400) / 86400
        allowed = self.burst + (cap - self.burst) * frac
        if self.used >= allowed:
            return False
        while self.stamps and now - self.stamps[0] > 60:
            self.stamps.popleft()
        return len(self.stamps) < self.per_min - 1

    # ---------- задания ----------
    def build_jobs(self, instruments: list, s):
        fast = set(s.td_fast_symbols)
        for inst in instruments:
            p = s.td_fast_tf if inst.symbol in fast else s.td_slow_tf
            if p not in JOB_INTERVAL:
                p = "H1"
            for tf in [p] + HTF_TD.get(p, []):
                key = (inst.symbol, tf)
                if key not in self.jobs:
                    self.jobs[key] = Job(inst.symbol, tf, tf == p,
                                         1.0 if tf == p else 0.6, JOB_INTERVAL[tf])

    def mark_warm(self, symbol: str, tf: str, ts: float):
        j = self.jobs.get((symbol, tf))
        if j:
            j.last_ok = max(j.last_ok, ts)

    def mark_ok(self, job: Job, bar_ts: float):
        job.last_ok = time.time()
        job.fails = 0
        if bar_ts != job.last_bar:
            job.empty = 0
        else:
            job.empty += 1
        job.last_bar = bar_ts

    def mark_fail(self, job: Job):
        job.fails += 1
        job.last_try = time.time()

    @staticmethod
    def _trading(inst, job: Job, now: float) -> bool:
        t = datetime.fromtimestamp(now, timezone.utc)
        if is_open(inst, t) or is_open(inst, t - timedelta(minutes=30)):
            return True
        return job.tf in ("D1", "W1") and (now - job.last_ok) > 3 * job.interval and t.weekday() < 5

    def next_job(self, by_symbol: dict, hint, disabled: dict):
        now = time.time()
        best, best_p = None, 0.0
        for j in self.jobs.values():
            inst = by_symbol.get(j.symbol)
            if inst is None or disabled.get(j.symbol, 0) > now:
                continue
            age = now - max(j.last_ok, j.last_try)
            interval = j.interval * (1 + min(j.empty, 4)) * (1 + min(j.fails, 3))
            if age < interval or not self._trading(inst, j, now):
                continue
            pr = (age / interval) * j.weight * (1.0 + hint(j.symbol))
            if pr > best_p:
                best, best_p = j, pr
        return best

    def snapshot(self) -> dict:
        self._roll()
        now = time.time()
        return {
            "day": self.day, "used": self.used, "limit": self.limit, "reserve": self.reserve,
            "per_minute_now": len([x for x in self.stamps if now - x <= 60]),
            "locked_for_s": max(0, int(self.locked_until - now)),
            "spent_by_symbol": dict(sorted(self.spent.items(), key=lambda kv: -kv[1])[:15]),
            "jobs": len(self.jobs), "recent": list(self.log)[-10:],
        }
