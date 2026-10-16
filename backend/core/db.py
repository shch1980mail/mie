import logging

import httpx

from core.utils import sanitize

log = logging.getLogger("mie.db")


class SupabaseError(Exception):
    pass


class Supabase:
    """Минимальный клиент PostgREST + Storage через httpx (без тяжёлых SDK)."""

    def __init__(self, url: str, key: str):
        self.url = (url or "").rstrip("/")
        self.key = key or ""
        self.enabled = bool(self.url and self.key)
        self._client = None

    def _c(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0))
        return self._client

    def _h(self, extra: dict | None = None) -> dict:
        h = {"apikey": self.key}
        if self.key.startswith("eyJ"):
            h["Authorization"] = f"Bearer {self.key}"
        if extra:
            h.update(extra)
        return h

    async def _req(self, method: str, path: str, ok404: bool = False, **kw):
        if not self.enabled:
            raise SupabaseError("Supabase не настроен (SUPABASE_URL / SUPABASE_SERVICE_KEY)")
        r = await self._c().request(method, f"{self.url}{path}", **kw)
        if r.status_code == 404 and ok404:
            return None
        if r.status_code >= 300:
            raise SupabaseError(f"{method} {path} -> {r.status_code}: {r.text[:200]}")
        return r

    async def select(self, table: str, params: dict | None = None) -> list:
        r = await self._req("GET", f"/rest/v1/{table}", params=params or {}, headers=self._h())
        return r.json()

    async def upsert(self, table: str, rows: list, on_conflict: str | None = None,
                     ignore_duplicates: bool = False):
        if not rows:
            return
        res = "ignore-duplicates" if ignore_duplicates else "merge-duplicates"
        params = {"on_conflict": on_conflict} if on_conflict else {}
        for i in range(0, len(rows), 200):
            await self._req(
                "POST", f"/rest/v1/{table}", params=params, json=sanitize(rows[i:i + 200]),
                headers=self._h({"Prefer": f"resolution={res},return=minimal"}))

    async def update(self, table: str, params: dict, body: dict):
        await self._req("PATCH", f"/rest/v1/{table}", params=params, json=sanitize(body),
                        headers=self._h({"Prefer": "return=minimal"}))

    async def delete(self, table: str, params: dict):
        await self._req("DELETE", f"/rest/v1/{table}", params=params,
                        headers=self._h({"Prefer": "return=minimal"}))

    async def storage_get(self, bucket: str, path: str):
        r = await self._req("GET", f"/storage/v1/object/authenticated/{bucket}/{path}",
                            ok404=True, headers=self._h())
        return None if r is None else r.content

    async def storage_put(self, bucket: str, path: str, data: bytes,
                          content_type: str = "application/json"):
        await self._req("POST", f"/storage/v1/object/{bucket}/{path}", content=data,
                        headers=self._h({"Content-Type": content_type, "x-upsert": "true"}))

    async def storage_list(self, bucket: str) -> list[str]:
        r = await self._req("POST", f"/storage/v1/object/list/{bucket}",
                            json={"prefix": "", "limit": 200}, headers=self._h())
        return [x["name"] for x in r.json() if x.get("name")]

    async def ping(self) -> dict:
        rows = await self.select("heartbeat", {"select": "id", "limit": "1"})
        return {"rows": len(rows)}

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
