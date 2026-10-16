"use client";

import { useState } from "react";
import ErrorBox from "@/components/ErrorBox";
import ScannerTable from "@/components/ScannerTable";
import { TableSkeleton } from "@/components/Skeleton";
import { getScan } from "@/lib/api";
import { ASSET_CLASSES } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import type { Timeframe } from "@/lib/types";

const TFS: Timeframe[] = ["M5", "M15", "M30", "H1", "H4", "D1"];
const PROBS = [
  { v: 0, label: "Любая P" },
  { v: 0.45, label: "P ≥ 45%" },
  { v: 0.5, label: "P ≥ 50%" },
  { v: 0.55, label: "P ≥ 55%" },
];

export default function ScannerPage() {
  const [tf, setTf] = useState<Timeframe>("M15");
  const [cls, setCls] = useState("");
  const [minProb, setMinProb] = useState(0);
  const [actionable, setActionable] = useState(false);

  const q = usePolling(
    () => getScan({ tf, asset_class: cls, min_prob: minProb, actionable, limit: 200 }),
    [tf, cls, minProb, actionable],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Сканер</h1>
          <p className="text-sm text-slate-500">
            Сортировка по E[R]; клик по заголовку меняет порядок. Обновление каждые 30 секунд.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          {q.updatedAt && <span>обновлено {q.updatedAt.toLocaleTimeString("ru-RU")}</span>}
          <button type="button" className="btn" onClick={q.reload}>
            Обновить
          </button>
        </div>
      </div>

      <div className="card grid grid-cols-2 gap-3 md:grid-cols-5">
        <div>
          <label className="label">Таймфрейм</label>
          <select className="input" value={tf} onChange={(e) => setTf(e.target.value as Timeframe)}>
            {TFS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Класс актива</label>
          <select className="input" value={cls} onChange={(e) => setCls(e.target.value)}>
            {ASSET_CLASSES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Мин. вероятность</label>
          <select className="input" value={minProb} onChange={(e) => setMinProb(Number(e.target.value))}>
            {PROBS.map((p) => (
              <option key={p.v} value={p.v}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <label className="col-span-2 flex items-end gap-2 pb-1.5 text-sm md:col-span-2">
          <input
            type="checkbox"
            className="h-4 w-4 accent-sky-500"
            checked={actionable}
            onChange={(e) => setActionable(e.target.checked)}
          />
          Только рекомендованные (E[R] &gt; 0, рынок открыт)
        </label>
      </div>

      {q.loading && <TableSkeleton rows={8} />}
      {q.error && !q.data && <ErrorBox message={q.error} onRetry={q.reload} />}
      {q.data && (
        <>
          {q.error && <p className="text-xs text-amber-400">Обновление не удалось, показаны прошлые данные: {q.error}</p>}
          <ScannerTable items={q.data.items} />
          {q.data.missing.length > 0 && (
            <p className="text-xs text-slate-500">
              Нет данных на {q.data.timeframe}: {q.data.missing.join(", ")}. Планировщик бесплатного плана Twelve Data
              загружает свечи по очереди и только в торговые часы; для не-крипты основной ТФ: M15 у 4 «быстрых»
              символов и H1 у остальных.
            </p>
          )}
        </>
      )}
    </div>
  );
}
