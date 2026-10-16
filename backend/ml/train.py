"""Обучение моделей. Запускается в GitHub Actions: python -m ml.train
Нужны переменные: SUPABASE_URL, SUPABASE_SERVICE_KEY (обязательно), TWELVE_KEY (для fx/other).
Результат: файлы {group}_{fast|slow}_{long|short}.json в Supabase Storage (bucket models)."""
import asyncio
import base64
import json
import logging
import os
import sys

import httpx
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier

from analysis.indicators import atr
from core.config import get_settings
from core.db import Supabase
from core.utils import utc_now
from data.instruments import INSTRUMENTS
from data.providers import BN_TF, OHLC, TD_TF, clean
from ml.barrier import barrier_labels
from ml.features import class_group, horizon_for, make_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train")

WARMUP = 250
TRAIN_TF = {"fast": "M15", "slow": "H1"}
BARS = {"fast": int(os.getenv("TRAIN_BARS_FAST", "20000")), "slow": int(os.getenv("TRAIN_BARS_SLOW", "12000"))}
TD_MAX_REQ = int(os.getenv("TRAIN_TD_MAX", "30"))
GROUPS = [g for g in os.getenv("TRAIN_GROUPS", "crypto,fx,other").split(",") if g]


async def fetch_binance(client, symbol, tf, total):
    rows, end = [], None
    while len(rows) < total:
        params = {"symbol": symbol, "interval": BN_TF[tf], "limit": 1000}
        if end:
            params["endTime"] = end
        r = await client.get("https://data-api.binance.vision/api/v3/klines", params=params)
        r.raise_for_status()
        part = r.json()
        if not part:
            break
        rows = part + rows
        end = part[0][0] - 1
        if len(part) < 1000:
            break
        await asyncio.sleep(0.15)
    df = pd.DataFrame([k[:6] for k in rows], columns=["ts"] + OHLC)
    df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
    return clean(df, tf)


async def fetch_td(client, key, ticker, tf):
    r = await client.get("https://api.twelvedata.com/time_series", params={
        "symbol": ticker, "interval": TD_TF[tf], "outputsize": 5000, "order": "ASC",
        "timezone": "UTC", "apikey": key})
    j = r.json()
    if "values" not in j:
        raise RuntimeError(str(j.get("message", j))[:200])
    df = pd.DataFrame(j["values"])
    df.index = pd.to_datetime(df.pop("datetime"), utc=True)
    return clean(df, tf)


def train_one(frames: dict, side: int, horizon: int):
    Xs, ys = [], []
    for sym, df in frames.items():
        a = atr(df)
        X = make_features(df, a).iloc[WARMUP:]
        y = barrier_labels(df, a, side, horizon).iloc[WARMUP:]
        m = y.notna()
        Xs.append(X[m])
        ys.append(y[m])
    X, y = pd.concat(Xs), pd.concat(ys)
    order = np.argsort(X.index.values, kind="stable")
    X, y = X.iloc[order], y.iloc[order]
    if len(X) < 3000:
        log.warning("мало данных (%d), пропуск", len(X))
        return None

    def mk():
        return XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.05, subsample=0.8,
                             colsample_bytree=0.8, min_child_weight=20, reg_lambda=5.0,
                             tree_method="hist", n_jobs=2, eval_metric="logloss")

    gap = (horizon + 1) * len(frames)
    oof = pd.Series(np.nan, index=range(len(X)))
    Xv, yv = X.reset_index(drop=True), y.reset_index(drop=True)
    for tr, te in TimeSeriesSplit(n_splits=5, gap=gap).split(Xv):
        oof.iloc[te] = mk().fit(Xv.iloc[tr], yv.iloc[tr]).predict_proba(Xv.iloc[te])[:, 1]
    ok = oof.notna().values
    po, yo = oof[ok].values, yv[ok].values
    cut = int(len(po) * 0.7)
    iso_eval = IsotonicRegression(out_of_bounds="clip").fit(po[:cut], yo[:cut])
    pe, ye = iso_eval.predict(po[cut:]), yo[cut:]
    brier = float(np.mean((pe - ye) ** 2))
    base = float(np.mean((yo[:cut].mean() - ye) ** 2))
    skill = 1 - brier / base if base > 0 else 0.0
    auc = float(roc_auc_score(ye, po[cut:])) if len(set(ye)) == 2 else None
    edges = np.quantile(pe, [0, .2, .4, .6, .8, 1.0])
    idx = np.clip(np.searchsorted(edges, pe, side="right") - 1, 0, 4)
    rel = [dict(p_mean=float(pe[idx == k].mean()), freq=float(ye[idx == k].mean()), n=int((idx == k).sum()))
           for k in range(5) if (idx == k).any()]
    iso = IsotonicRegression(out_of_bounds="clip").fit(po, yo)
    clf = mk().fit(Xv, yv)
    raw = bytes(clf.get_booster().save_raw(raw_format="json"))
    metrics = dict(n=int(len(Xv)), base_rate=float(yv.mean()), brier=brier, brier_base=base,
                   brier_skill=float(skill), auc=auc, reliability=rel)
    log.info("n=%d base=%.3f brier_skill=%.4f auc=%s", len(Xv), yv.mean(), skill, auc)
    return dict(xgb=base64.b64encode(raw).decode(), cols=list(Xv.columns),
                iso=dict(x=iso.X_thresholds_.tolist(), y=iso.y_thresholds_.tolist()),
                skill=bool(skill > 0.003), metrics=metrics, trained_at=utc_now().isoformat())


async def main():
    s = get_settings()
    db = Supabase(s.supabase_url, s.supabase_service_key)
    if not db.enabled:
        log.error("SUPABASE_URL / SUPABASE_SERVICE_KEY не заданы")
        sys.exit(1)
    td_used = 0
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "mie-train/1.0"}) as client:
        for group in GROUPS:
            insts = [i for i in INSTRUMENTS.values()
                     if i.default_on and class_group(i.asset_class) == group]
            for tfg, tf in TRAIN_TF.items():
                frames = {}
                for inst in insts:
                    try:
                        if inst.provider == "binance":
                            df = await fetch_binance(client, inst.ticker, tf, BARS[tfg])
                        else:
                            if not s.twelve_key or td_used >= TD_MAX_REQ:
                                continue
                            td_used += 1
                            df = await fetch_td(client, s.twelve_key, inst.ticker, tf)
                            await asyncio.sleep(8)
                        if len(df) > WARMUP + 500:
                            frames[inst.symbol] = df
                    except Exception as e:
                        log.warning("%s %s: %s", inst.symbol, tf, e)
                log.info("группа %s/%s: %d инструментов", group, tfg, len(frames))
                if not frames:
                    continue
                for side, sname in ((1, "long"), (-1, "short")):
                    res = await asyncio.to_thread(train_one, frames, side, horizon_for(tfg))
                    if res is None:
                        continue
                    res.update(group=f"{group}_{tfg}", side=side)
                    await db.storage_put(s.models_bucket, f"{group}_{tfg}_{sname}.json",
                                         json.dumps(res).encode())
                    log.info("сохранено %s_%s_%s (skill=%s)", group, tfg, sname, res["skill"])
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
