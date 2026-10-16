"use client";

import { useMemo, useState } from "react";
import ErrorBox from "@/components/ErrorBox";
import { TableSkeleton } from "@/components/Skeleton";
import { getCalendar } from "@/lib/api";
import { fmtCountdown, fmtDateTime } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import type { Impact } from "@/lib/types";

const IMPACT_CLS: Record<Impact, string> = {
  high: "border-rose-800 bg-rose-950/50 text-rose-300",
  medium: "border-amber-800 bg-amber-950/40 text-amber-300",
  low: "border-slate-700 bg-slate-800/60 text-slate-400",
};
const IMPACT_LABEL: Record<Impact, string> = { high: "Высокая", medium: "Средняя", low: "Низкая" };

const v = (x: number | null) => (x == null ? "—" : String(x));

export default function CalendarPage() {
  const [hours, setHours] = useState(48);
  const [impact, setImpact] = useState<Impact>("medium");
  const [ccy, setCcy] = useState("");

  const q = usePolling(() => getCalendar({ hours, min_impact: impact }), [hours, impact]);

  const events = useMemo(() => {
    const c = ccy.trim().toUpperCase();
    const list = q.data?.events ?? [];
    return c ? list.filter((e) => (e.ccy ?? "").includes(c)) : list;
  }, [q.data, ccy]);

  const status = q.data?.source_status ?? {};

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">Экономический календарь</h1>
        <p className="text-sm text-slate-500">
          За 20 минут до и 10 минут после события высокой важности вход по связанным инструментам блокируется (blackout).
        </p>
      </div>

      <div className="card grid grid-cols-2 gap-3 md:grid-cols-4">
        <div>
          <label className="label">Горизонт</label>
          <select className="input" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={12}>12 часов</option>
            <option value={24}>24 часа</option>
            <option value={48}>48 часов</option>
            <option value={72}>72 часа</option>
          </select>
        </div>
        <div>
          <label className="label">Мин. важность</label>
          <select className="input" value={impact} onChange={(e) => setImpact(e.target.value as Impact)}>
            <option value="low">Низкая и выше</option>
            <option value="medium">Средняя и выше</option>
            <option value="high">Только высокая</option>
          </select>
        </div>
        <div>
          <label className="label">Валюта (USD, EUR…)</label>
          <input className="input" value={ccy} onChange={(e) => setCcy(e.target.value)} placeholder="все" />
        </div>
        <div className="flex items-end">
          <button type="button" className="btn w-full" onClick={q.reload}>
            Обновить
          </button>
        </div>
      </div>

      {q.loading && <TableSkeleton rows={6} />}
      {q.error && !q.data && <ErrorBox message={q.error} onRetry={q.reload} />}

      {q.data && (
        <>
          {events.length === 0 ? (
            <div className="card space-y-2 text-sm text-slate-400">
              <p>Событий по выбранным фильтрам нет.</p>
              <p className="text-xs text-slate-500">
                Если события не появляются совсем: у Finnhub этот эндпоинт может быть платным. Тогда добавьте FOMC, CPI,
                NFP вручную в таблицу <code className="text-slate-300">manual_events</code> в Supabase (Table Editor →
                Insert row).
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Время (локальное)</th>
                    <th className="px-3 py-2">Валюта</th>
                    <th className="px-3 py-2">Событие</th>
                    <th className="px-3 py-2">Важность</th>
                    <th className="px-3 py-2 text-right">Пред.</th>
                    <th className="px-3 py-2 text-right">Прогноз</th>
                    <th className="px-3 py-2 text-right">Факт</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {events.map((e, i) => {
                    const soon = e.impact === "high" && e.minutes_to >= -10 && e.minutes_to <= 20;
                    return (
                      <tr key={`${e.ts}-${e.event}-${i}`} className={soon ? "bg-amber-950/30" : "bg-slate-900/30"}>
                        <td className="whitespace-nowrap px-3 py-2">
                          <div>{fmtDateTime(e.ts)}</div>
                          <div className={`text-[11px] ${soon ? "text-amber-400" : "text-slate-500"}`}>
                            {fmtCountdown(e.minutes_to)}
                            {soon && " · blackout"}
                          </div>
                        </td>
                        <td className="px-3 py-2 font-medium">{e.ccy ?? "—"}</td>
                        <td className="px-3 py-2">
                          {e.event}
                          {e.source === "manual" && <span className="ml-1.5 text-[10px] text-slate-500">вручную</span>}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`rounded-full border px-2 py-0.5 text-xs ${IMPACT_CLS[e.impact]}`}>
                            {IMPACT_LABEL[e.impact]}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-400">{v(e.prev)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{v(e.estimate)}</td>
                        <td className="px-3 py-2 text-right font-semibold tabular-nums">{v(e.actual)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="card text-xs text-slate-500">
            <div className="mb-1 font-semibold uppercase text-slate-400">Статус источников</div>
            {Object.keys(status).length === 0 ? (
              <span>нет данных о статусе</span>
            ) : (
              <ul className="space-y-0.5">
                {Object.entries(status).map(([k, val]) => (
                  <li key={k}>
                    <span className="text-slate-300">{k}</span>: {val}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
