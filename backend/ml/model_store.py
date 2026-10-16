import asyncio
import base64
import json
import logging

import numpy as np
import xgboost as xgb

from analysis.indicators import atr
from ml.features import make_features

log = logging.getLogger("mie.models")


class ModelStore:
    """Модели лежат в Supabase Storage (JSON: XGBoost + изотоническая калибровка).
    Нет модели или она без «skill» -> engine использует эвристику."""

    def __init__(self, db, bucket: str = "models"):
        self.db, self.bucket = db, bucket
        self.bundles: dict[tuple, dict] = {}
        self.error = ""

    @staticmethod
    def _parse(raw: bytes) -> dict:
        d = json.loads(raw)
        booster = xgb.Booster()
        booster.load_model(bytearray(base64.b64decode(d["xgb"])))
        return dict(booster=booster, cols=d["cols"], iso_x=np.array(d["iso"]["x"], dtype=float),
                    iso_y=np.array(d["iso"]["y"], dtype=float), skill=bool(d.get("skill")),
                    metrics=d.get("metrics", {}), trained_at=d.get("trained_at"),
                    group=d["group"], side=int(d["side"]))

    async def reload(self):
        if not self.db.enabled:
            self.error = "Supabase не настроен"
            return
        try:
            names = await self.db.storage_list(self.bucket)
            new = {}
            for n in names:
                if not n.endswith(".json"):
                    continue
                raw = await self.db.storage_get(self.bucket, n)
                if not raw:
                    continue
                try:
                    b = await asyncio.to_thread(self._parse, raw)
                    new[(b["group"], b["side"])] = b
                except Exception as e:
                    log.warning("модель %s не загружена: %s", n, e)
            self.bundles = new
            self.error = ""
            log.info("загружено моделей: %d", len(new))
        except Exception as e:
            self.error = str(e)[:200]
            log.warning("models reload failed: %s", e)

    def predict(self, group: str, side: int, df):
        """Возвращает (p_sym, info) либо (None, None). p_sym = P(+1 ATR раньше −1 ATR), калиброванная."""
        b = self.bundles.get((group, side))
        if not b or not b["skill"]:
            return None, None
        try:
            X = make_features(df, atr(df)).iloc[[-1]][b["cols"]]
            raw = float(b["booster"].predict(xgb.DMatrix(X.values, feature_names=b["cols"]))[0])
            p = float(np.interp(raw, b["iso_x"], b["iso_y"]))
            return float(np.clip(p, 0.05, 0.95)), dict(group=group, p_raw=round(raw, 3),
                                                       trained_at=b["trained_at"], metrics=b["metrics"])
        except Exception as e:
            log.warning("predict failed: %s", e)
            return None, None

    def status(self) -> dict:
        return {"error": self.error, "models": [
            dict(group=k[0], side=k[1], skill=v["skill"], trained_at=v["trained_at"],
                 n=v["metrics"].get("n"), brier_skill=v["metrics"].get("brier_skill"),
                 auc=v["metrics"].get("auc")) for k, v in sorted(self.bundles.items())]}
