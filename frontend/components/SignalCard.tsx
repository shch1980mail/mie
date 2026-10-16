import Link from "next/link";
import BiasBadge from "./BiasBadge";
import { fmtPct, fmtPrice, fmtR, timeAgo } from "@/lib/format";
import type { Signal } from "@/lib/types";

function Stat({ label, value, cls = "" }: { label: string; value: string; cls?: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-sm font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

export default function SignalCard({ sig }: { sig: Signal }) {
  const tp1 = sig.take_profits[0];
  const tp2 = sig.take_profits[1];
  const er = sig.expectancy_r;
  const heur = sig.probability_source === "heuristic";
  return (
    <Link
      href={`/chart/${sig.symbol}?tf=${sig.timeframe}`}
      className="card block transition hover:border-sky-700"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-base font-bold">{sig.symbol}</div>
          <div className="truncate text-xs text-slate-500">
            {sig.name} · {sig.timeframe}
          </div>
        </div>
        <BiasBadge bias={sig.bias} />
      </div>

      <div className="mt-2 text-xl font-semibold tabular-nums">{fmtPrice(sig.price)}</div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat label="P(TP1)" value={`${fmtPct(sig.probability)}${heur ? "*" : ""}`} />
        <Stat
          label="E[R]"
          value={fmtR(er)}
          cls={er == null ? "" : er > 0 ? "text-emerald-400" : "text-rose-400"}
        />
        <Stat label="RR TP1" value={tp1 ? tp1.rr.toFixed(2) : "—"} />
      </div>

      {sig.entry ? (
        <dl className="mt-3 space-y-0.5 text-xs tabular-nums text-slate-300">
          <div className="flex justify-between">
            <dt className="text-slate-500">Вход</dt>
            <dd>{fmtPrice(sig.entry.aggressive)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Стоп</dt>
            <dd className="text-rose-300">{fmtPrice(sig.stop_loss)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">TP1 / TP2</dt>
            <dd className="text-emerald-300">
              {fmtPrice(tp1?.price)} / {fmtPrice(tp2?.price)}
            </dd>
          </div>
        </dl>
      ) : (
        <p className="mt-3 text-xs text-slate-500">Входа нет: нейтральный bias или blackout по новостям.</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
        {sig.recommended && (
          <span className="rounded bg-emerald-900/60 px-1.5 py-0.5 text-emerald-300">✓ рекомендован</span>
        )}
        {sig.stale && <span className="rounded bg-amber-900/60 px-1.5 py-0.5 text-amber-300">устарело</span>}
        {heur && <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">* эвристика</span>}
        <span className="ml-auto text-slate-500">{timeAgo(sig.generated_at)}</span>
      </div>
    </Link>
  );
}
