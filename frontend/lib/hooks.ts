"use client";

import { useEffect, useRef, useState } from "react";
import { apiErrorMessage } from "./api";
import { fetchRecentSignals, subscribeSignals, supabaseEnabled } from "./supabase";
import type { LiveStatus, SignalRow } from "./types";

/**
 * Поллинг REST. Данные привязаны к ключу deps: при смене параметров устаревшие данные
 * не возвращаются (data = null, пока не придёт ответ на новые параметры).
 * Пока вкладка скрыта, запросы не делаются.
 */
export function usePolling<T>(fetcher: () => Promise<T>, deps: ReadonlyArray<unknown>, intervalMs = 30000) {
  const key = JSON.stringify(deps);
  const fref = useRef(fetcher);
  fref.current = fetcher;
  const [snap, setSnap] = useState<{ key: string; data: T; at: number } | null>(null);
  const [err, setErr] = useState<{ key: string; msg: string } | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = async () => {
      if (document.visibilityState === "visible") {
        try {
          const d = await fref.current();
          if (alive) {
            setSnap({ key, data: d, at: Date.now() });
            setErr(null);
          }
        } catch (e) {
          if (alive) setErr({ key, msg: apiErrorMessage(e) });
        }
      }
      if (alive) timer = setTimeout(run, intervalMs);
    };
    void run();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [key, tick, intervalMs]);

  const data = snap && snap.key === key ? snap.data : null;
  const error = err && err.key === key ? err.msg : null;
  return {
    data,
    error,
    loading: data === null && error === null,
    updatedAt: snap && snap.key === key ? new Date(snap.at) : null,
    reload: () => setTick((t) => t + 1),
  };
}

/** Лента сигналов: первичная загрузка из Supabase + Realtime (INSERT/UPDATE). */
export function useSignalFeed(limit = 40) {
  const [rows, setRows] = useState<SignalRow[]>([]);
  const [status, setStatus] = useState<LiveStatus>(supabaseEnabled ? "connecting" : "off");
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(!supabaseEnabled);

  useEffect(() => {
    let alive = true;
    fetchRecentSignals(limit)
      .then((r) => {
        if (!alive) return;
        setRows((prev) => {
          const ids = new Set(prev.map((x) => x.id));
          return [...prev, ...r.filter((x) => !ids.has(x.id))]
            .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
            .slice(0, limit);
        });
        setLoaded(true);
      })
      .catch((e) => {
        if (!alive) return;
        setError(apiErrorMessage(e));
        setLoaded(true);
      });

    const unsub = subscribeSignals(
      (row) => setRows((prev) => [row, ...prev.filter((r) => r.id !== row.id)].slice(0, limit)),
      (row) =>
        setRows((prev) =>
          prev.map((r) => (r.id === row.id ? { ...r, ...row, payload: row.payload ?? r.payload } : r)),
        ),
      setStatus,
    );
    return () => {
      alive = false;
      unsub();
    };
  }, [limit]);

  return { rows, status, error, loaded };
}
