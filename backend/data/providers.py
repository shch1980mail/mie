import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass

import httpx
import numpy as np
import pandas as pd

from core.cache import TTLCache
from core.models import BudgetExceeded, DataUnavailable
from core.timeframes import TF_SEC, candle_ends, expected_last_open
from core.utils import utc_now
from data.instruments import Instrument

log = logging.getLogger("mie.data")

OHLC = ["open", "high", "low", "close", "volume"]
TD_TF = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h",
         "H4": "4h", "D1": "1day", "W1": "1week", "MN": "1month"}
BN_TF = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h",
         "H4": "4h", "D1": "1d", "W1": "1w", "MN": "1M"}
KR_TF = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440, "W1": 10080}
CB_TF = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600, "D1": 86400}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
RESAMPLE = {"M30": "30min", "H4": "4h", "W1": "W-MON", "MN": "MS"}


@dataclass
class Candles:
    df: pd.DataFrame
    source: str
    fetched_at: float
    stale: bool = False


def clean(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Типы, дубли, сортировка и ТОЛЬКО закрытые свечи (против repainting)."""
    df = df.copy()
    for c in OHLC:
        if c not in df.columns:
            df[c] = 0.0
    df = df[OHLC].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df["volume"] = df["volume"].fillna(0.0)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df["high"] >= df["low"]]
    return df[candle_ends(df.index, tf) <= pd.Timestamp.now(tz="UTC")]


def resample_ohlc(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    r = df.resample(RESAMPLE[tf], label="left", closed="left").agg(AGG).dropna(subset=["open"])
    return r.iloc[1:]


# ============================ крипто-провайдеры ============================
class BinanceVision:
    name = "binance_vision"
    URL = "https://data-api.binance.vision/api/v3/klines"

    def supports(self, inst, tf):
        return bool(inst.ticker) and tf in BN_TF

    async def candles(self, client, inst, tf, n):
        r = await client.get(self.URL, params={"symbol": inst.ticker, "interval": BN_TF[tf],
                                               "limit": min(n + 1, 1000)})
        if r.status_code != 200:
            raise DataUnavailable(f"binance {r.status_code}", r.status_code)
        df = pd.DataFrame([k[:6] for k in r.json()], columns=["ts"] + OHLC)
        df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
        return clean(df, tf)


class Kraken:
    name = "kraken"
    URL = "https://api.kraken.com/0/public/OHLC"

    def supports(self, inst, tf):
        return bool(inst.kraken) and (tf in KR_TF or tf == "MN")

    async def candles(self, client, inst, tf, n):
        if tf == "MN":
            d = await self.candles(client, inst, "D1", 720)
            return clean(resample_ohlc(d, "MN"), "MN")
        r = await client.get(self.URL, params={"pair": inst.kraken, "interval": KR_TF[tf]})
        if r.status_code != 200:
            raise DataUnavailable(f"kraken {r.status_code}", r.status_code)
        j = r.json()
        if j.get("error"):
            raise DataUnavailable(f"kraken: {j['error']}", 400)
        res = j["result"]
        key = next(k for k in res if k != "last")
        df = pd.DataFrame(res[key], columns=["ts", "open", "high", "low", "close", "vwap", "volume", "count"])
        df.index = pd.to_datetime(df.pop("ts"), unit="s", utc=True)
        return clean(df, tf)


class Coinbase:
    name = "coinbase"
    URL = "https://api.exchange.coinbase.com/products/{}/candles"
    DERIVED = {"M30": ("M15", "M30"), "H4": ("H1", "H4"), "W1": ("D1", "W1"), "MN": ("D1", "MN")}

    def supports(self, inst, tf):
        return bool(inst.coinbase) and (tf in CB_TF or tf in self.DERIVED)

    async def candles(self, client, inst, tf, n):
        if tf in self.DERIVED:
            src, tgt = self.DERIVED[tf]
            d = await self.candles(client, inst, src, 300)
            return clean(resample_ohlc(d, tgt), tf)
        r = await client.get(self.URL.format(inst.coinbase), params={"granularity": CB_TF[tf]})
        if r.status_code != 200:
            raise DataUnavailable(f"coinbase {r.status_code}", r.status_code)
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            raise DataUnavailable("coinbase: пустой ответ", 400)
        df = pd.DataFrame(rows, columns=["ts", "low", "high", "open", "close", "volume"])
        df.index = pd.to_datetime(df.pop("ts"), unit="s", utc=True)
        return clean(df, tf)


# ============================ Twelve Data ============================
class TwelveData:
    URL = "https://api.twelvedata.com/time_series"

    def __init__(self, key: str, budget):
        self.key, self.budget = key, budget

    async def candles(self, client, inst, tf, n, on_demand=False):
        if not self.key:
            raise DataUnavailable("TWELVE_KEY не задан", 401)
        if not self.budget.acquire(inst.symbol, tf, on_demand):
            raise BudgetExceeded(f"бюджет Twelve Data исчерпан/пейсинг ({inst.symbol} {tf})")
        r = await client.get(self.URL, params={
            "symbol": inst.ticker, "interval": TD_TF[tf], "outputsize": n, "order": "ASC",
            "timezone": "UTC", "apikey": self.key})
        j = r.json()
        if j.get("status") == "error" or "values" not in j:
            code = j.get("code") or r.status_code
            if code == 429:
                self.budget.hit_minute_limit()
            raise DataUnavailable(f"twelvedata {code}: {str(j.get('message', ''))[:160]}", int(code))
        df = pd.DataFrame(j["values"])
        df.index = pd.to_datetime(df.pop("datetime"), utc=True)
        return clean(df, tf)


# ============================ роутер ============================
class DataRouter:
    def __init__(self, settings, db, budget, http: httpx.AsyncClient):
        self.s, self.db, self.budget, self.http = settings, db, budget, http
        self.cache = TTLCache(1500)
        self.chain = [BinanceVision(), Kraken(), Coinbase()]
        self.td = TwelveData(settings.twelve_key, budget)
        self.down_until: dict[str, float] = {}
        self.disabled: dict[str, float] = {}
        self.td_down_until = 0.0
        self.errors: deque = deque(maxlen=40)
        self._locks = defaultdict(asyncio.Lock)
        self._tasks: set = set()

    # ---------- служебное ----------
    def _note(self, symbol, tf, msg):
        self.errors.append({"t": utc_now().isoformat(timespec="seconds"),
                            "symbol": symbol, "tf": tf, "msg": str(msg)[:200]})
        log.warning("%s %s: %s", symbol, tf, msg)

    def _bg(self, coro):
        t = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    @staticmethod
    def _key(inst, tf):
        return f"c:{inst.symbol}:{tf}"

    def _fresh(self, inst, c: Candles, tf: str) -> bool:
        now = time.time()
        age = now - c.fetched_at
        if inst.provider == "binance":
            if age < 5:
                return True
            exp = expected_last_open(tf, now)
            if exp is None:
                return age < 600
            return c.df.index[-1].timestamp() >= exp - 1
        return age < TF_SEC[tf]

    # ---------- загрузка ----------
    async def _fetch_crypto(self, inst, tf, n):
        errs = []
        for p in self.chain:
            if self.down_until.get(p.name, 0) > time.time() or not p.supports(inst, tf):
                continue
            try:
                df = await p.candles(self.http, inst, tf, n)
                if len(df) >= 30:
                    return df, p.name
                errs.append(f"{p.name}: мало данных ({len(df)})")
            except DataUnavailable as e:
                errs.append(f"{p.name}: {e}")
                if e.status in (451, 403):
                    self.down_until[p.name] = time.time() + 3600
                elif e.status in (418, 429) or (e.status or 0) >= 500:
                    self.down_until[p.name] = time.time() + 300
            except Exception as e:
                errs.append(f"{p.name}: {type(e).__name__} {e}")
                self.down_until[p.name] = time.time() + 120
        raise DataUnavailable("все крипто-провайдеры недоступны: " + "; ".join(errs))

    async def _fetch(self, inst, tf, n, reason):
        if inst.provider == "binance":
            return await self._fetch_crypto(inst, tf, n)
        now = time.time()
        if self.disabled.get(inst.symbol, 0) > now:
            raise DataUnavailable(f"{inst.symbol} временно отключён (недоступен на плане/тикере)")
        if self.td_down_until > now:
            raise DataUnavailable("Twelve Data отключён (ошибка ключа)")
        try:
            return await self.td.candles(self.http, inst, tf, n, reason == "on_demand"), "twelvedata"
        except BudgetExceeded:
            raise
        except DataUnavailable as e:
            if e.status == 401:
                self.td_down_until = now + 3600
            elif e.status in (400, 403, 404):
                self.disabled[inst.symbol] = now + 86400
            raise

    async def refresh(self, inst: Instrument, tf: str, n: int = 500, reason: str = "scheduler") -> Candles:
        key = self._key(inst, tf)
        async with self._locks[key]:
            if reason == "on_demand":
                c, _ = self.cache.get(key)
                if c is not None and self._fresh(inst, c, tf):
                    return c
            df, source = await self._fetch(inst, tf, n, reason)
            if len(df) < 30:
                raise DataUnavailable(f"слишком мало свечей ({len(df)})")
            c = Candles(df.tail(n), source, time.time())
            self.cache.set(key, c, 7 * 86400)
            if inst.provider != "binance":
                self._bg(self._persist(inst, tf, c.df))
            return c

    async def candles(self, inst: Instrument, tf: str, n: int = 500, mode: str = "auto") -> Candles:
        """mode='auto': свежий кэш, иначе загрузка; при сбое — устаревший кэш.
        mode='cache': никакой сети, только то, что уже есть."""
        key = self._key(inst, tf)
        c, _ = self.cache.get(key)
        if mode == "cache":
            if c is None:
                raise DataUnavailable(f"нет кэша {inst.symbol} {tf}")
            return c if self._fresh(inst, c, tf) else Candles(c.df, c.source, c.fetched_at, True)
        if c is not None and self._fresh(inst, c, tf):
            return c
        try:
            return await self.refresh(inst, tf, n, "on_demand")
        except Exception as e:
            self._note(inst.symbol, tf, e)
            if c is not None:
                return Candles(c.df, c.source, c.fetched_at, True)
            if isinstance(e, DataUnavailable):
                raise
            raise DataUnavailable(f"{type(e).__name__}: {e}")

    # ---------- персистентный кэш в Supabase ----------
    async def _persist(self, inst, tf, df: pd.DataFrame):
        if not self.db.enabled:
            return
        try:
            t = df.tail(500)
            ms = (t.index.asi8 // 10**6).astype("int64")
            arr = np.column_stack([ms.astype(float), t[OHLC].values]).tolist()
            await self.db.upsert("candle_cache", [{
                "key": self._key(inst, tf), "symbol": inst.symbol, "timeframe": tf,
                "updated_at": utc_now().isoformat(), "data": arr}], on_conflict="key")
        except Exception as e:
            log.debug("persist candles failed: %s", e)

    async def warm(self) -> list[tuple]:
        """Подгрузка кэша свечей из Supabase при старте (чтобы не тратить кредиты)."""
        info = []
        if not self.db.enabled:
            return info
        try:
            rows = await self.db.select("candle_cache", {
                "select": "key,symbol,timeframe,updated_at,data", "limit": "500"})
        except Exception as e:
            log.warning("warm failed: %s", e)
            return info
        for r in rows:
            try:
                arr = np.array(r["data"], dtype=float)
                df = pd.DataFrame(arr[:, 1:], columns=OHLC,
                                  index=pd.to_datetime(arr[:, 0], unit="ms", utc=True))
                ts = pd.Timestamp(r["updated_at"]).timestamp()
                self.cache.set(r["key"], Candles(df, "db_cache", ts), 7 * 86400)
                info.append((r["symbol"], r["timeframe"], ts))
            except Exception as e:
                log.debug("warm row failed: %s", e)
        log.info("warm: %d наборов свечей из Supabase", len(info))
        return info
