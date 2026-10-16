import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from analysis.fundamentals import Fundamentals
from api.jobs import Runner, build_scheduler
from core.config import get_settings
from core.db import Supabase
from core.models import DataUnavailable
from core.timeframes import TF_SEC
from core.utils import rnd, sanitize, utc_now
from data.budget_scheduler import BudgetScheduler
from data.instruments import INSTRUMENTS, active_instruments
from data.providers import DataRouter
from ml.model_store import ModelStore
from signals.engine import analyze, best_timeframe
from signals.store import SignalStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mie.api")

settings = get_settings()
http = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0), follow_redirects=True,
                         headers={"User-Agent": "mie/1.0 (+personal project)"})
db = Supabase(settings.supabase_url, settings.supabase_service_key)
budget = BudgetScheduler(settings, db)
router = DataRouter(settings, db, budget, http)
fund = Fundamentals(settings, db, http)
models = ModelStore(db, settings.models_bucket)
store = SignalStore(db)
runner = Runner(settings, db, router, fund, models, store, budget)
scheduler = None
STARTED = time.time()


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(sanitize(content))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    try:
        await runner.init()
    except Exception as e:
        log.exception("init failed (сервис продолжит работу): %s", e)
    if settings.enable_scheduler:
        scheduler = build_scheduler(runner)
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
    await http.aclose()
    await db.close()


app = FastAPI(title="Market Intelligence Engine", lifespan=lifespan,
              default_response_class=SafeJSONResponse)
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings.allowed_origins),
    allow_origin_regex=settings.allowed_origin_regex or None,
    allow_methods=["GET", "HEAD", "OPTIONS"], allow_headers=["*"])


def _inst(symbol: str):
    i = INSTRUMENTS.get(symbol.upper())
    if i is None:
        raise HTTPException(404, f"неизвестный символ {symbol}")
    return i


def _tf(tf: str) -> str:
    tf = tf.upper()
    if tf not in TF_SEC:
        raise HTTPException(400, f"неверный таймфрейм {tf}; допустимо: {', '.join(TF_SEC)}")
    return tf


def _mode(inst) -> str:
    return "auto" if inst.provider == "binance" else "cache"


def _age(sig) -> float:
    return (utc_now() - datetime.fromisoformat(sig.generated_at)).total_seconds()


# ============================ служебные ============================
@app.get("/")
async def root():
    return {"name": "Market Intelligence Engine", "docs": "/docs", "health": "/health"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "uptime_s": int(time.time() - STARTED), "time": utc_now().isoformat()}


@app.api_route("/tick", methods=["GET", "HEAD"])
async def tick():
    return {"ok": True}


async def _probe(name: str, coro, timeout: float = 8.0) -> dict:
    t = time.time()
    try:
        detail = await asyncio.wait_for(coro, timeout)
        return {"name": name, "ok": True, "ms": int((time.time() - t) * 1000), "detail": detail}
    except Exception as e:
        return {"name": name, "ok": False, "error": f"{type(e).__name__}: {str(e)[:180]}"}


async def _get_status(url: str, **kw):
    r = await http.get(url, **kw)
    return {"http": r.status_code}


@app.get("/diagnostics")
async def diagnostics():
    probes = [
        _probe("supabase_db", db.ping()),
        _probe("supabase_storage", db.storage_list(settings.models_bucket)),
        _probe("binance_vision", _get_status("https://data-api.binance.vision/api/v3/ping")),
        _probe("kraken", _get_status("https://api.kraken.com/0/public/Time")),
        _probe("coinbase", _get_status("https://api.exchange.coinbase.com/time")),
    ]
    if settings.twelve_key:
        probes.append(_probe("twelvedata_usage", _get_status(
            "https://api.twelvedata.com/api_usage", params={"apikey": settings.twelve_key})))
    results = await asyncio.gather(*probes)
    await fund.events()
    return {
        "time": utc_now().isoformat(), "uptime_s": int(time.time() - STARTED),
        "config": {"supabase": db.enabled, "twelve_key": bool(settings.twelve_key),
                   "finnhub_key": bool(settings.finnhub_key), "scheduler": settings.enable_scheduler,
                   "origins": list(settings.allowed_origins), "origin_regex": settings.allowed_origin_regex},
        "probes": results,
        "models": models.status(),
        "budget": budget.snapshot(),
        "fundamentals": fund.status,
        "instruments": {"crypto": [i.symbol for i in runner.crypto], "twelvedata": list(runner.td)},
        "cache_items": router.cache.size(),
        "signals_in_memory": len(store.latest),
        "scheduler_last_run": runner.last_run,
        "provider_down_until": {k: int(v - time.time()) for k, v in router.down_until.items() if v > time.time()},
        "disabled_symbols": {k: int(v - time.time()) for k, v in router.disabled.items() if v > time.time()},
        "recent_errors": list(router.errors)[-10:] + runner.errors[-5:],
    }


# ============================ данные ============================
@app.get("/instruments")
async def instruments():
    act = {i.symbol for i in active_instruments(settings)}
    return [{"symbol": i.symbol, "name": i.name, "asset_class": i.asset_class, "provider": i.provider,
             "active": i.symbol in act} for i in INSTRUMENTS.values()]


@app.get("/candles/{symbol}")
async def candles(symbol: str, tf: str = "M5", limit: int = 300):
    inst, tf = _inst(symbol), _tf(tf)
    try:
        c = await router.candles(inst, tf, 500, "auto")
    except DataUnavailable as e:
        raise HTTPException(503, f"Данные недоступны: {e}")
    df = c.df.tail(max(10, min(limit, 500)))
    t = (df.index.asi8 // 10**9).tolist()
    rows = [{"time": t[i], "open": rnd(r.open), "high": rnd(r.high), "low": rnd(r.low),
             "close": rnd(r.close), "volume": float(r.volume)} for i, r in enumerate(df.itertuples())]
    return {"symbol": inst.symbol, "timeframe": tf, "source": c.source, "stale": c.stale, "candles": rows}


@app.get("/signals/{symbol}")
async def get_signal(symbol: str, tf: str = "M5"):
    inst, tf = _inst(symbol), _tf(tf)
    cached = store.get(inst.symbol, tf)
    if cached and _age(cached) < min(TF_SEC[tf] / 4, 60):
        return cached
    try:
        sig = await analyze(router, fund, models, inst, tf, "auto")
        await store.put(sig)
        return sig
    except DataUnavailable as e:
        if cached:
            return cached.model_copy(update={"stale": True})
        raise HTTPException(503, f"Данные недоступны: {e}")


@app.get("/scan")
async def scan(tf: str = "M5", asset_class: str | None = None, min_prob: float = 0.0,
               actionable: bool = False, limit: int = 200):
    tf = _tf(tf)
    sem = asyncio.Semaphore(6)
    missing: list[str] = []

    async def one(inst):
        sig = store.get(inst.symbol, tf)
        if sig and _age(sig) < max(min(TF_SEC[tf] * 2, 3600), 120):
            return sig
        async with sem:
            try:
                s = await analyze(router, fund, models, inst, tf, _mode(inst))
                await store.put(s)
                return s
            except DataUnavailable:
                missing.append(inst.symbol)
                return sig.model_copy(update={"stale": True}) if sig else None
            except Exception as e:
                log.warning("scan %s: %s", inst.symbol, e)
                missing.append(inst.symbol)
                return None

    items = [i for i in active_instruments(settings) if not asset_class or i.asset_class == asset_class]
    res = [s for s in await asyncio.gather(*[one(i) for i in items]) if s]
    if actionable:
        res = [s for s in res if s.recommended]
    res = [s for s in res if (s.probability or 0) >= min_prob or s.bias == "neutral" and min_prob == 0]
    res.sort(key=lambda s: (s.expectancy_r if s.expectancy_r is not None else -9, abs(s.score)), reverse=True)
    return {"timeframe": tf, "count": len(res[:limit]), "missing": sorted(set(missing)),
            "generated_at": utc_now().isoformat(), "items": res[:limit]}


@app.get("/best/{symbol}")
async def best(symbol: str):
    inst = _inst(symbol)
    best_sig, sigs = await best_timeframe(router, fund, models, inst, ("M5", "M15", "H1"), _mode(inst))
    return {"best": best_sig, "candidates": [
        {"timeframe": s.timeframe, "bias": s.bias, "score": s.score, "probability": s.probability,
         "expectancy_r": s.expectancy_r, "recommended": s.recommended} for s in sigs]}


@app.get("/calendar")
async def calendar(hours: int = 48, min_impact: str = "medium", symbol: str | None = None):
    ccys = set(_inst(symbol).currencies) if symbol else None
    events = await fund.upcoming(hours, min_impact, ccys)
    return {"count": len(events), "source_status": fund.status, "events": events}
