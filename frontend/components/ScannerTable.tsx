"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import BiasBadge from "./BiasBadge";
import { fmtPct, fmtPrice, fmtR, timeAgo } from "@/lib/format";
import type { Signal } from "@/lib/types";

type SortKey = "symbol" | "score" | "probability" | "expectancy_r" | "rr";

function val(s: Signal, k: SortKey): number | string {
  switch (k) {
    case "symbol":
      return s.symbol;
    case "score":
      return s.score;
    case "probability":
      return s.probability ?? -1;
    case "expectancy_r":
      return s.expectancy_r ?? -99;
    case "rr":
      return s.take_profits[0]?.rr ?? -1;
  }
}

export default function ScannerTable({ items }: { items: Signal[] }) {
  const router = useRouter();
  const [sort, setSort] = useState<{ key: SortKey | null; dir: 1 | -1 }>({ key: null, dir: -1 });

  const rows = useMemo(() => {
    const k = sort.key;
    if (!k) return items;
    return [...items].sort((a, b) => {
      const va = val(a, k);
      const vb = val(b, k);
      if (typeof va === "string" && typeof vb === "string") return va.localeCompare(vb) * sort.dir;
      return (Number(va) - Number(vb)) * sort.dir;
    });
  }, [items, sort]);

  const toggle = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: key === "symbol" ? 1 : -1 }));

  const Th = ({ k, label, cls = "" }: { k?: SortKey; label: string; cls?: string }) => (
    <th
      className={`whitespace-nowrap px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-500 ${
        k ? "cursor-pointer select-none hover:text-slate-300" : ""
      } ${cls}`}
      onClick={k ? () => toggle(k) : undefined}
    >
      {label}
      {k && sort.key === k ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
    </th>
  );

  if (rows.length === 0) {
    return (
      <div className="card text-sm text-slate-400">
        Нет сигналов по выбранным фильтрам. Это нормальный результат: система не обязана находить сетап на каждом
        инструменте.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full min-w-[520px] text-sm">
        <thead className="bg-slate-900/80">
          <tr>
            <Th k="symbol" label="Символ" />
            <Th label="Bias" />
            <Th k="score" label="Score" cls="hidden sm:table-cell" />
            <Th k="probability" label="P" />
            <Th k="rr" label="RR" cls="hidden sm:table-cell" />
            <Th k="expectancy_r" label="E[R]" />
            <Th label="Вход" cls="hidden md:table-cell" />
            <Th label="Стоп" cls="hidden md:table-cell" />
            <Th label="TP1" cls="hidden md:table-cell" />
            <Th label="Возраст" cls="hidden lg:table-cell" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {rows.map((s) => {
            const er = s.expectancy_r;
            return (
              <tr
                key={`${s.symbol}-${s.timeframe}`}
                className="cursor-pointer bg-slate-900/30 transition hover:bg-slate-800/60"
                onClick={() => router.push(`/chart/${s.symbol}?tf=${s.timeframe}`)}
              >
                <td className="px-3 py-2">
                  <Link
                    href={`/chart/${s.symbol}?tf=${s.timeframe}`}
                    className="font-semibold hover:text-sky-400"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {s.symbol}
                  </Link>
                  <div className="text-[11px] text-slate-500">
                    {s.timeframe}
                    {s.recommended && <span className="ml-1 text-emerald-400">✓</span>}
                    {s.stale && <span className="ml-1 text-amber-400">устар.</span>}
                  </div>
                </td>
                <td className="px-3 py-2">
                  <BiasBadge bias={s.bias} />
                </td>
                <td className="hidden px-3 py-2 tabular-nums sm:table-cell">
                  {s.score > 0 ? "+" : ""}
                  {s.score.toFixed(2)}
                </td>
                <td className="px-3 py-2 tabular-nums">
                  {fmtPct(s.probability)}
                  {s.probability_source === "heuristic" && <span className="text-slate-500">*</span>}
                </td>
                <td className="hidden px-3 py-2 tabular-nums sm:table-cell">
                  {s.take_profits[0] ? s.take_profits[0].rr.toFixed(2) : "—"}
                </td>
                <td
                  className={`px-3 py-2 font-medium tabular-nums ${
                    er == null ? "text-slate-500" : er > 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {fmtR(er)}
                </td>
                <td className="hidden px-3 py-2 tabular-nums md:table-cell">{fmtPrice(s.entry?.aggressive)}</td>
                <td className="hidden px-3 py-2 tabular-nums text-rose-300 md:table-cell">{fmtPrice(s.stop_loss)}</td>
                <td className="hidden px-3 py-2 tabular-nums text-emerald-300 md:table-cell">
                  {fmtPrice(s.take_profits[0]?.price)}
                </td>
                <td className="hidden px-3 py-2 text-xs text-slate-500 lg:table-cell">{timeAgo(s.generated_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="border-t border-slate-800 px-3 py-2 text-[11px] text-slate-500">
        * вероятность по эвристике: ML-модель ещё не обучена или не прошла проверку. E[R] без спреда и комиссий.
      </div>
    </div>
  );
}
