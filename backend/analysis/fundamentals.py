import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np

from core.cache import TTLCache
from core.utils import utc_now

log = logging.getLogger("mie.fund")

CTRY = {"US": "USD", "EU": "EUR", "DE": "EUR", "FR": "EUR", "IT": "EUR", "GB": "GBP", "JP": "JPY",
        "CH": "CHF", "AU": "AUD", "CA": "CAD", "NZ": "NZD", "CN": "CNY"}
POLARITY = {"core cpi": 1, "cpi": 1, "inflation": 1, "ppi": 1, "nonfarm": 1, "gdp": 1, "pmi": 1,
            "retail sales": 1, "interest rate": 1, "rate decision": 1,
            "unemployment": -1, "jobless": -1}
IMPACT_W = {"high": 1.0, "medium": 0.5, "low": 0.1}
COT_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
FNG_URL = "https://api.alternative.me/fng/?limit=1"


def _num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


class Fundamentals:
    def __init__(self, s, db, http):
        self.s, self.db, self.http = s, db, http
        self.cache = TTLCache(100)
        self.status: dict = {}

    # ---------- календарь ----------
    @staticmethod
    def _norm(e: dict):
        try:
            raw = str(e["time"])
            dt = (datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S") if " " in raw[:19]
                  else datetime.fromisoformat(raw)).replace(tzinfo=timezone.utc)
        except Exception:
            return None
        return dict(ts=dt.isoformat(), dt=dt, ccy=CTRY.get(e.get("country")), country=e.get("country"),
                    event=e.get("event", ""), impact=(e.get("impact") or "low").lower(),
                    actual=_num(e.get("actual")), estimate=_num(e.get("estimate")),
                    prev=_num(e.get("prev")), source="finnhub")

    async def events(self) -> list[dict]:
        val, fresh = self.cache.get("cal")
        if fresh:
            return val
        out = []
        if self.s.finnhub_key:
            try:
                d0 = utc_now().date()
                r = await self.http.get(
                    "https://finnhub.io/api/v1/calendar/economic",
                    params={"from": str(d0 - timedelta(days=1)), "to": str(d0 + timedelta(days=3))},
                    headers={"X-Finnhub-Token": self.s.finnhub_key})
                if r.status_code == 200:
                    out += [x for x in map(self._norm, r.json().get("economicCalendar") or []) if x]
                    self.status["finnhub"] = f"ok ({len(out)} событий)"
                else:
                    self.status["finnhub"] = f"http {r.status_code} (возможно, нужен платный план)"
            except Exception as e:
                self.status["finnhub"] = f"error: {e}"[:140]
        else:
            self.status["finnhub"] = "нет ключа FINNHUB_KEY"
        if self.db.enabled:
            try:
                since = (utc_now() - timedelta(days=1)).isoformat()
                rows = await self.db.select("manual_events", {
                    "select": "*", "ts": f"gte.{since}", "order": "ts.asc", "limit": "200"})
                for m in rows:
                    dt = datetime.fromisoformat(str(m["ts"]).replace("Z", "+00:00"))
                    out.append(dict(ts=dt.isoformat(), dt=dt, ccy=m.get("ccy"), country=None,
                                    event=m.get("event", ""), impact=(m.get("impact") or "high").lower(),
                                    actual=_num(m.get("actual")), estimate=_num(m.get("estimate")),
                                    prev=None, source="manual"))
                self.status["manual_events"] = f"ok ({len(rows)})"
            except Exception as e:
                self.status["manual_events"] = f"error: {e}"[:140]
        if not out and val:
            return val
        out.sort(key=lambda x: x["dt"])
        self.cache.set("cal", out, 600)
        return out

    async def upcoming(self, hours: int = 48, min_impact: str = "medium", ccys=None) -> list[dict]:
        order = {"low": 0, "medium": 1, "high": 2}
        now = utc_now()
        res = []
        for e in await self.events():
            if order.get(e["impact"], 0) < order.get(min_impact, 1):
                continue
            if ccys and e["ccy"] not in ccys:
                continue
            if now - timedelta(hours=3) <= e["dt"] <= now + timedelta(hours=hours):
                res.append({k: v for k, v in e.items() if k != "dt"} | {
                    "minutes_to": round((e["dt"] - now).total_seconds() / 60)})
        return res

    # ---------- COT ----------
    async def cot_percentile(self, market: str, weeks: int = 156):
        if not market:
            return None
        key = f"cot:{market}"
        val, fresh = self.cache.get(key)
        if fresh:
            return val
        try:
            q = market.replace("'", "''")
            r = await self.http.get(COT_URL, params={
                "$select": "market_and_exchange_names,report_date_as_yyyy_mm_dd,"
                           "noncomm_positions_long_all,noncomm_positions_short_all",
                "$where": f"market_and_exchange_names like '{q}%'",
                "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "600"})
            if r.status_code != 200:
                self.status["cot"] = f"http {r.status_code}"
                return val
            rows = [x for x in r.json() if "XRATE" not in x["market_and_exchange_names"]]
            if not rows:
                return val
            names: dict = {}
            for x in rows:
                names.setdefault(x["market_and_exchange_names"], []).append(x)
            main = max(names.values(), key=len)[:weeks]
            net = [float(x["noncomm_positions_long_all"]) - float(x["noncomm_positions_short_all"]) for x in main]
            pct = float((np.array(net) <= net[0]).mean() * 100) if len(net) > 20 else None
            self.status["cot"] = "ok"
            self.cache.set(key, pct, 12 * 3600)
            return pct
        except Exception as e:
            self.status["cot"] = f"error: {e}"[:140]
            return val

    # ---------- Fear & Greed (крипта) ----------
    async def fear_greed(self):
        val, fresh = self.cache.get("fng")
        if fresh:
            return val
        try:
            r = await self.http.get(FNG_URL)
            v = int(r.json()["data"][0]["value"])
            self.status["fear_greed"] = "ok"
            self.cache.set("fng", v, 3600)
            return v
        except Exception as e:
            self.status["fear_greed"] = f"error: {e}"[:100]
            return val

    # ---------- итоговый фундаментальный скор ----------
    async def score_for(self, inst, now=None) -> dict:
        now = now or utc_now()
        try:
            events = await self.events()
            cal_ok = True
        except Exception:
            events, cal_ok = [], False
        ccys = set(inst.currencies)
        score, notes, risks, blackout = 0.0, [], [], False
        b4, af = self.s.blackout_before_min, self.s.blackout_after_min
        for e in events:
            if e["ccy"] not in ccys or e["impact"] not in ("high", "medium"):
                continue
            dt = e["dt"]
            if e["impact"] == "high" and -af * 60 <= (dt - now).total_seconds() <= b4 * 60:
                blackout = True
                risks.append(f"Новость {e['event']} ({e['ccy']}) в {dt:%H:%M} UTC")
            elif e["impact"] == "high" and 0 < (dt - now).total_seconds() <= 4 * 3600:
                risks.append(f"Скоро: {e['event']} ({e['ccy']}) в {dt:%H:%M} UTC")
            a, est = e["actual"], e["estimate"]
            if a is None or est is None:
                continue
            age_h = (now - dt).total_seconds() / 3600
            if not 0 <= age_h <= 6:
                continue
            pol = next((v for k, v in POLARITY.items() if k in e["event"].lower()), 0)
            denom = max(abs(est), abs(e["prev"] or 0.0), 0.1)
            surprise = math.tanh(5 * (a - est) / denom) * pol
            if len(inst.currencies) < 2:
                side = 0
            else:
                side = 1 if e["ccy"] == inst.currencies[0] else -1
            score += surprise * side * IMPACT_W[e["impact"]] * math.exp(-age_h / 2)
            notes.append(f"{e['event']}: факт {a} vs прогноз {est}")
        cot = await self.cot_percentile(inst.cot_market) if inst.cot_market else None
        if cot is not None:
            sgn = -1 if inst.cot_invert else 1
            if cot > 90:
                score -= 0.3 * sgn
                risks.append(f"COT: экстремально длинные позиции спекулянтов ({cot:.0f} перц.)")
            elif cot < 10:
                score += 0.3 * sgn
                risks.append(f"COT: экстремально короткие позиции спекулянтов ({cot:.0f} перц.)")
        fng = None
        if inst.asset_class == "crypto":
            fng = await self.fear_greed()
            if fng is not None:
                if fng <= 20:
                    score += 0.2
                    notes.append(f"Fear&Greed {fng}: экстремальный страх (контрарно бычий фон)")
                elif fng >= 80:
                    score -= 0.2
                    notes.append(f"Fear&Greed {fng}: экстремальная жадность (контрарно медвежий фон)")
        if not cal_ok or (not self.s.finnhub_key and not events):
            risks.append("Календарь событий недоступен: защита от новостей не работает "
                         "(добавьте события в manual_events)")
        return dict(score=float(np.tanh(score)), blackout=blackout, notes=notes,
                    cot_pct=cot, fear_greed=fng, risks=risks)
