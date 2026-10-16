"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import BiasBadge from "@/components/BiasBadge";
import ErrorBox from "@/components/ErrorBox";
import LevelsTable from "@/components/LevelsTable";
import MTFTable from "@/components/MTFTable";
import RiskCalculator from "@/components/RiskCalculator";
import SignalDetails from "@/components/SignalDetails";
import { Skeleton } from "@/components/Skeleton";
import { apiErrorMessage, getBest, getSignal } from "@/lib/api";
import { TIMEFRAMES, fmtPct, fmtPrice, fmtR, timeAgo } from "@/lib/format";
import { usePolling, useSignalFeed } from "@/lib/hooks";
import type { BestResponse, Signal, Timeframe } from "@/lib/types";

const CandleChart = dynamic(() => import("@/components/CandleChart"), {
  ssr: false,
  loading: () => <Skeleton className="h-[430px] w-full" />,
});

function Line({ k, v, cls = "" }: { k: string; v: string; cls?: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-slate-800/60 py-1.5 text-sm">
      <span className="text-slate-400">{k}</span>
      <span className={`tabular-nums ${cls}`}>{v}</span>
    </div>
  );
}

function TradePanel({ sig }: { sig: Signal }) {
  const tp1 = sig.take_profits[0];
  const tp2 = sig.take_profits[1];
  const er = sig.expectancy_r;
  return (
    <div className="card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <BiasBadge bias={sig.bias} className="text-sm" />
        {sig.recommended ? (
          <span className="rounded bg-emerald-900/60 px-2 py-0.5 text-xs text-emerald-300">✓ рекомендован</span>
        ) : (
          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">не рекомендован</span>
        )}
      </div>
      <div className="mb-3 text-2xl font-semibold tabular-nums">{fmtPrice(sig.price)}</div>

      {sig.entry ? (
        <>
          <Line k="Вход (по рынку)" v={fmtPrice(sig.entry.aggressive)} cls="text-sky-300" />
          <Line
            k="Вход (лимит у зоны)"
            v={sig.entry.conservative != null ? fmtPrice(sig.entry.conservative) : "нет зоны рядом"}
            cls="text-sky-300"
          />
          <Line k="Стоп-лосс" v={fmtPrice(sig.stop_loss)} cls="text-rose-300" />
          <Line k="TP1" v={tp1 ? `${fmtPrice(tp1.price)}  (${tp1.rr.toFixed(2)}R)` : "—"} cls="text-emerald-300" />
          <Line k="TP2" v={tp2 ? `${fmtPrice(tp2.price)}  (${tp2.rr.toFixed(2)}R)` : "—"} cls="text-emerald-300" />
          <Line
            k={`Вероятность TP1${sig.probability_source === "heuristic" ? " (эвристика)" : ""}`}
            v={fmtPct(sig.probability)}
          />
          <Line k="Вероятность TP2" v={fmtPct(sig.probability_tp2)} />
          <Line
            k="Матожидание E[R]"
            v={fmtR(er)}
            cls={er == null ? "" : er > 0 ? "text-emerald-400" : "text-rose-400"}
          />
        </>
      ) : (
        <p className="text-sm text-slate-400">
          Входа нет: bias нейтральный или действует blackout вокруг важной новости. Это осознанный сигнал «не торгуй».
        </p>
      )}
      <p className="mt-3 text-[11px] text-slate-500">
        Сигнал по закрытой свече {timeAgo(sig.candle_ts)} · ATR {fmtPrice(sig.atr)}
        {sig.stale && <span className="ml-1 text-amber-400">· данные устарели</span>}
      </p>
    </div>
  );
}

function ChartView({ symbol }: { symbol: string }) {
  const router = useRouter();
  const sp = useSearchParams();
  const raw = (sp?.get("tf") || "M15").toUpperCase();
  const tf: Timeframe = (TIMEFRAMES as string[]).includes(raw) ? (raw as Timeframe) : "M15";
  const setTf = (t: Timeframe) => router.replace(`/chart/${symbol}?tf=${t}`, { scroll: false });

  const sigQ = usePolling(() => getSignal(symbol, tf), [symbol, tf]);
  const feed = useSignalFeed(60);

  const live = feed.rows.find((r) => r.symbol === symbol && r.timeframe === tf)?.payload ?? null;
  const polled = sigQ.data;
  const signal: Signal | null =
    polled && live ? (Date.parse(live.generated_at) > Date.parse(polled.generated_at) ? live : polled) : (polled ?? live);

  const [best, setBest] = useState<BestResponse | null>(null);
  const [bestBusy, setBestBusy] = useState(false);
  const [bestErr, setBestErr] = useState<string | null>(null);

  const findBest = async () => {
    setBestBusy(true);
    setBestErr(null);
    try {
      const r = await getBest(symbol);
      setBest(r);
      if (r.best) setTf(r.best.timeframe);
    } catch (e) {
      setBestErr(apiErrorMessage(e));
    } finally {
      setBestBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link href="/scanner" className="text-xs text-slate-500 hover:text-sky-400">
            ← Сканер
          </Link>
          <h1 className="truncate text-xl font-bold">
            {symbol}
            {signal?.name && <span className="ml-2 text-sm font-normal text-slate-500">{signal.name}</span>}
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {TIMEFRAMES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTf(t)}
              className={`rounded-md border px-2 py-1 text-xs transition ${
                tf === t ? "border-sky-600 bg-sky-950/60 text-sky-300" : "border-slate-700 text-slate-400 hover:text-white"
              }`}
            >
              {t}
            </button>
          ))}
          <button type="button" className="btn ml-1" onClick={findBest} disabled={bestBusy}>
            {bestBusy ? "Считаю…" : "Лучший ТФ"}
          </button>
        </div>
      </div>

      {bestErr && <ErrorBox message={bestErr} />}
      {best && (
        <div className="card text-sm">
          {best.best ? (
            <p className="mb-2">
              Лучший ТФ по E[R]: <b>{best.best.timeframe}</b> ({fmtR(best.best.expectancy_r)}), график переключён.
            </p>
          ) : (
            <p className="mb-2 text-slate-300">Ни на одном из ТФ нет рекомендованного сетапа.</p>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
            {best.candidates.map((c) => (
              <span key={c.timeframe}>
                {c.timeframe}: {c.bias === "bullish" ? "▲" : c.bias === "bearish" ? "▼" : "●"} P {fmtPct(c.probability)} ·{" "}
                {fmtR(c.expectancy_r)}
                {c.recommended ? " ✓" : ""}
              </span>
            ))}
          </div>
        </div>
      )}

      {sigQ.error && !signal && <ErrorBox message={sigQ.error} onRetry={sigQ.reload} />}
      {sigQ.error && signal && (
        <p className="text-xs text-amber-400">Обновление сигнала не удалось, показаны прошлые данные: {sigQ.error}</p>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <CandleChart symbol={symbol} tf={tf} signal={signal} />
          {signal ? <SignalDetails sig={signal} /> : sigQ.loading ? <Skeleton className="h-72 w-full" /> : null}
        </div>
        <div className="space-y-4">
          {signal ? <TradePanel sig={signal} /> : sigQ.loading ? <Skeleton className="h-64 w-full" /> : null}
          {signal && <MTFTable mtf={signal.rationale.mtf} />}
          {signal && <LevelsTable levels={signal.levels} price={signal.price} />}
          <RiskCalculator signal={signal} />
        </div>
      </div>
    </div>
  );
}

export default function ChartPage({ params }: { params: { symbol: string } }) {
  const symbol = decodeURIComponent(params.symbol).toUpperCase();
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ChartView symbol={symbol} />
    </Suspense>
  );
}
