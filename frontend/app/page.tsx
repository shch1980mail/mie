"use client";

import Link from "next/link";
import { useState } from "react";
import BiasBadge from "@/components/BiasBadge";
import ErrorBox, { StatusPill } from "@/components/ErrorBox";
import SignalCard from "@/components/SignalCard";
import { CardGridSkeleton, Skeleton } from "@/components/Skeleton";
import { getCalendar, getHealth, getScan } from "@/lib/api";
import { fmtCountdown, fmtPct, fmtR, timeAgo } from "@/lib/format";
import { usePolling, useSignalFeed } from "@/lib/hooks";
import type { Outcome, Timeframe } from "@/lib/types";

const TFS: Timeframe[] = ["M5", "M15", "H1"];

function OutcomeBadge({ o, r }: { o: Outcome; r: number | null }) {
  if (o === "tp1") return <span className="text-emerald-400">TP1 {fmtR(r)}</span>;
  if (o === "sl") return <span className="text-rose-400">SL {fmtR(r)}</span>;
  if (o === "expired") return <span className="text-slate-400">истёк {fmtR(r)}</span>;
  if (o === "no_data") return <span className="text-slate-500">нет данных</span>;
  return <span className="text-sky-400">в работе</span>;
}

export default function DashboardPage() {
  const [tf, setTf] = useState<Timeframe>("M15");
  const scan = usePolling(() => getScan({ tf, actionable: true, limit: 6 }), [tf]);
  const cal = usePolling(() => getCalendar({ hours: 24, min_impact: "high" }), []);
  const health = usePolling(() => getHealth(), []);
  const feed = useSignalFeed(15);

  const rtState = feed.status === "live" ? "ok" : feed.status === "connecting" ? "idle" : feed.status === "off" ? "warn" : "bad";
  const rtLabel =
    feed.status === "live"
      ? "Realtime: онлайн"
      : feed.status === "connecting"
        ? "Realtime: подключение…"
        : feed.status === "off"
          ? "Realtime выключен"
          : "Realtime: ошибка";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Дашборд</h1>
          <p className="text-sm text-slate-500">Лучшие рекомендованные сетапы по ожидаемому E[R]</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill
            label={health.data ? "Бэкенд онлайн" : health.error ? "Бэкенд недоступен" : "Бэкенд: проверка…"}
            state={health.data ? "ok" : health.error ? "bad" : "idle"}
          />
          <StatusPill label={rtLabel} state={rtState} />
        </div>
      </div>

      {health.error && !health.data && (
        <ErrorBox
          message={`${health.error} Если Space только что запускался или спал, подождите 1–2 минуты.`}
          onRetry={health.reload}
        />
      )}

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="h2 mb-0">Топ сигналов</h2>
          <div className="flex items-center gap-1.5">
            {TFS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTf(t)}
                className={`rounded-md border px-2.5 py-1 text-xs transition ${
                  tf === t ? "border-sky-600 bg-sky-950/60 text-sky-300" : "border-slate-700 text-slate-400 hover:text-white"
                }`}
              >
                {t}
              </button>
            ))}
            <Link href="/scanner" className="ml-2 text-xs text-sky-400 hover:underline">
              Весь сканер →
            </Link>
          </div>
        </div>

        {scan.loading && <CardGridSkeleton count={3} />}
        {scan.error && !scan.data && <ErrorBox message={scan.error} onRetry={scan.reload} />}
        {scan.data && (
          <>
            {scan.data.items.length === 0 ? (
              <div className="card text-sm text-slate-400">
                На {tf} сейчас нет рекомендованных сетапов. Система показывает «не торгуй», если матожидание ≤ 0, рынок
                закрыт или рядом важная новость.
                {scan.data.missing.length > 0 && (
                  <span className="mt-1 block text-xs text-slate-500">
                    Нет данных: {scan.data.missing.join(", ")} (планировщик ещё не загрузил свечи этого ТФ).
                  </span>
                )}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {scan.data.items.map((s) => (
                  <SignalCard key={`${s.symbol}-${s.timeframe}`} sig={s} />
                ))}
              </div>
            )}
            {scan.error && <p className="mt-2 text-xs text-amber-400">Обновление не удалось: {scan.error}</p>}
          </>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="h2">Ближайшие важные события (24 ч)</h2>
          {cal.loading && <Skeleton className="h-40 w-full" />}
          {cal.error && !cal.data && <ErrorBox message={cal.error} onRetry={cal.reload} />}
          {cal.data && (
            <div className="card">
              {cal.data.events.length === 0 ? (
                <p className="text-sm text-slate-400">
                  Событий высокой важности нет. Если календарь не настроен, статус: {JSON.stringify(cal.data.source_status)}
                </p>
              ) : (
                <ul className="divide-y divide-slate-800">
                  {cal.data.events.slice(0, 6).map((e, i) => (
                    <li key={i} className="flex items-start justify-between gap-3 py-2 text-sm">
                      <div className="min-w-0">
                        <div className="truncate font-medium">
                          <span className="mr-2 rounded bg-slate-800 px-1.5 py-0.5 text-xs">{e.ccy ?? "—"}</span>
                          {e.event}
                        </div>
                        <div className="text-xs text-slate-500">
                          прогноз {e.estimate ?? "—"} · пред. {e.prev ?? "—"} · факт {e.actual ?? "—"}
                        </div>
                      </div>
                      <span
                        className={`shrink-0 text-xs ${Math.abs(e.minutes_to) <= 30 ? "text-amber-400" : "text-slate-400"}`}
                      >
                        {fmtCountdown(e.minutes_to)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <Link href="/calendar" className="mt-2 inline-block text-xs text-sky-400 hover:underline">
                Весь календарь →
              </Link>
            </div>
          )}
        </section>

        <section>
          <h2 className="h2">Лента сигналов (Realtime)</h2>
          {!feed.loaded && <Skeleton className="h-40 w-full" />}
          {feed.error && <ErrorBox message={feed.error} />}
          {feed.loaded && !feed.error && (
            <div className="card">
              {feed.status === "off" && (
                <p className="mb-2 text-xs text-amber-400">
                  Supabase не подключён (нет NEXT_PUBLIC_SUPABASE_URL / ANON_KEY): лента недоступна.
                </p>
              )}
              {feed.rows.length === 0 ? (
                <p className="text-sm text-slate-400">
                  Пока нет записанных сигналов. Они появятся, когда бэкенд найдёт сетап со входом.
                </p>
              ) : (
                <ul className="divide-y divide-slate-800">
                  {feed.rows.map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                      <div className="flex min-w-0 items-center gap-2">
                        <Link href={`/chart/${r.symbol}?tf=${r.timeframe}`} className="font-semibold hover:text-sky-400">
                          {r.symbol}
                        </Link>
                        <span className="text-xs text-slate-500">{r.timeframe}</span>
                        <BiasBadge bias={r.bias} className="hidden sm:inline-flex" />
                      </div>
                      <div className="flex shrink-0 items-center gap-3 text-xs">
                        <span className="tabular-nums text-slate-300">{fmtPct(r.probability)}</span>
                        <OutcomeBadge o={r.outcome} r={r.r_multiple} />
                        <span className="hidden text-slate-500 sm:inline">{timeAgo(r.created_at)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
