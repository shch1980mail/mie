import logging
from datetime import timedelta

from core.models import Signal
from core.utils import utc_now

log = logging.getLogger("mie.store")


class SignalStore:
    """Последние сигналы в памяти + журнал в Supabase (таблица signals, Realtime включается на ней)."""

    def __init__(self, db):
        self.db = db
        self.latest: dict[tuple, Signal] = {}
        self._persisted: set = set()

    def get(self, symbol: str, tf: str):
        return self.latest.get((symbol, tf))

    def all(self, tf: str | None = None) -> list[Signal]:
        return [s for (sym, t), s in self.latest.items() if tf is None or t == tf]

    def max_abs_score(self, symbol: str) -> float:
        v = [abs(s.score) for (sym, _), s in self.latest.items() if sym == symbol]
        return max(v) if v else 0.0

    async def load(self):
        if not self.db.enabled:
            return
        try:
            since = (utc_now() - timedelta(hours=12)).isoformat()
            rows = await self.db.select("signals", {
                "select": "payload", "created_at": f"gte.{since}", "order": "created_at.desc", "limit": "600"})
            for r in rows:
                try:
                    s = Signal(**r["payload"])
                except Exception:
                    continue
                key = (s.symbol, s.timeframe)
                if key not in self.latest:
                    self.latest[key] = s
                    self._persisted.add((s.symbol, s.timeframe, s.candle_ts))
            log.info("store: загружено %d сигналов", len(self.latest))
        except Exception as e:
            log.warning("store load failed: %s", e)

    async def put(self, sig: Signal):
        self.latest[(sig.symbol, sig.timeframe)] = sig
        if not sig.entry or not self.db.enabled:
            return
        pk = (sig.symbol, sig.timeframe, sig.candle_ts)
        if pk in self._persisted:
            return
        try:
            await self.db.upsert("signals", [dict(
                symbol=sig.symbol, asset_class=sig.asset_class, timeframe=sig.timeframe,
                candle_ts=sig.candle_ts, bias=sig.bias, score=sig.score, probability=sig.probability,
                probability_source=sig.probability_source, expectancy_r=sig.expectancy_r,
                recommended=sig.recommended, payload=sig.model_dump())],
                on_conflict="symbol,timeframe,candle_ts", ignore_duplicates=True)
            if len(self._persisted) > 5000:
                self._persisted.clear()
            self._persisted.add(pk)
        except Exception as e:
            log.warning("signal persist failed: %s", e)

    async def cleanup(self, retention_days: int):
        if not self.db.enabled:
            return
        try:
            cut = (utc_now() - timedelta(days=retention_days)).isoformat()
            await self.db.delete("signals", {"created_at": f"lt.{cut}"})
            await self.db.delete("candle_cache", {"updated_at": f"lt.{(utc_now() - timedelta(days=7)).isoformat()}"})
        except Exception as e:
            log.warning("cleanup failed: %s", e)
