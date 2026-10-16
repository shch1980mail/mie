"use client";

import { useEffect, useRef, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import ErrorBox, { StatusPill } from "./ErrorBox";
import { Skeleton } from "./Skeleton";
import { getCandles } from "@/lib/api";
import { isCryptoSymbol, prettyPattern, priceDigits } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import type { CandleBar, LiveStatus, Signal, Timeframe } from "@/lib/types";
import { connectKline } from "@/lib/websocket";

interface Props {
  symbol: string;
  tf: Timeframe;
  signal: Signal | null;
}

const toBar = (c: CandleBar): CandlestickData => ({
  time: c.time as UTCTimestamp,
  open: c.open,
  high: c.high,
  low: c.low,
  close: c.close,
});

export default function CandleChart({ symbol, tf, signal }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const linesRef = useRef<IPriceLine[]>([]);
  const lastKey = useRef("");
  const fitKey = useRef("");
  const [layers, setLayers] = useState({ levels: true, trade: true, zones: true, markers: true });
  const [ws, setWs] = useState<LiveStatus>("off");
  const crypto = isCryptoSymbol(symbol);
  const sym = symbol.toUpperCase();

  const { data, error, loading, reload } = usePolling(
    () => getCandles(symbol, tf, 300),
    [symbol, tf],
    crypto ? 60000 : 30000,
  );

  useEffect(() => {
    if (!box.current) return;
    const chart = createChart(box.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { borderColor: "#334155", timeVisible: true, secondsVisible: false },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#f43f5e",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      linesRef.current = [];
      lastKey.current = "";
      fitKey.current = "";
    };
  }, []);

  useEffect(() => {
    const s = seriesRef.current;
    if (!s || !data || data.candles.length === 0) return;
    const cs = data.candles;
    const key = `${symbol}|${tf}|${cs.length}|${cs[cs.length - 1].time}`;
    if (key === lastKey.current) return;
    lastKey.current = key;
    s.setData(cs.map(toBar));
    const d = priceDigits(cs[cs.length - 1].close);
    s.applyOptions({ priceFormat: { type: "price", precision: d, minMove: 1 / 10 ** d } });
    const fk = `${symbol}|${tf}`;
    if (fitKey.current !== fk) {
      fitKey.current = fk;
      chartRef.current?.timeScale().fitContent();
    }
  }, [data, symbol, tf]);

  useEffect(() => {
    if (!crypto) {
      setWs("off");
      return;
    }
    return connectKline(
      symbol,
      tf,
      (k) => {
        try {
          seriesRef.current?.update({
            time: k.time as UTCTimestamp,
            open: k.open,
            high: k.high,
            low: k.low,
            close: k.close,
          });
        } catch {
          /* свеча старше последней в серии: игнорируем */
        }
      },
      setWs,
    );
  }, [symbol, tf, crypto]);

  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    linesRef.current.forEach((l) => {
      try {
        s.removePriceLine(l);
      } catch {
        /* линия уже удалена */
      }
    });
    linesRef.current = [];

    const ok = signal && signal.timeframe === tf && signal.symbol === sym;
    if (!ok || !signal) {
      s.setMarkers([]);
      return;
    }

    const add = (
      price: number | null | undefined,
      color: string,
      title: string,
      style: LineStyle,
      width: 1 | 2 | 3 | 4 = 1,
    ) => {
      if (price == null || !Number.isFinite(price)) return;
      linesRef.current.push(
        s.createPriceLine({ price, color, lineWidth: width, lineStyle: style, axisLabelVisible: true, title }),
      );
    };

    const lv = signal.levels;
    if (layers.levels) {
      (lv.support ?? []).forEach((x) =>
        add(x.price, "#34d399", `S×${x.touches}`, LineStyle.Solid, x.touches >= 4 ? 2 : 1),
      );
      (lv.resistance ?? []).forEach((x) =>
        add(x.price, "#fb7185", `R×${x.touches}`, LineStyle.Solid, x.touches >= 4 ? 2 : 1),
      );
      (lv.liquidity ?? []).forEach((x) =>
        add(x.price, "#a78bfa", x.type === "H" ? "EQH" : "EQL", LineStyle.Dotted),
      );
    }
    if (layers.zones) {
      (lv.fvg ?? []).forEach((z) => {
        const c = z.dir === "bull" ? "#22c55e" : "#ef4444";
        add(z.lo, c, `FVG${z.dir === "bull" ? "↑" : "↓"}`, LineStyle.Dashed);
        add(z.hi, c, "", LineStyle.Dashed);
      });
      (lv.order_blocks ?? []).forEach((z) => {
        const c = z.dir === "bull" ? "#38bdf8" : "#f59e0b";
        add(z.lo, c, `OB${z.dir === "bull" ? "↑" : "↓"}`, LineStyle.LargeDashed);
        add(z.hi, c, "", LineStyle.LargeDashed);
      });
    }
    if (layers.trade && signal.entry) {
      add(signal.entry.aggressive, "#38bdf8", "ВХОД", LineStyle.Solid, 2);
      add(signal.entry.conservative, "#38bdf8", "вход (лимит)", LineStyle.Dashed);
      add(signal.stop_loss, "#f43f5e", "SL", LineStyle.Solid, 2);
      signal.take_profits.forEach((t, i) =>
        add(t.price, "#10b981", `TP${i + 1} (${t.rr.toFixed(1)}R)`, LineStyle.Solid, 2),
      );
    }

    const pats = (signal.rationale.candles?.patterns ?? []).filter((p) => !p.startsWith("ctx:"));
    const t0 = Math.floor(Date.parse(signal.candle_ts) / 1000);
    const hasBar = data?.candles.some((c) => c.time === t0) ?? false;
    if (layers.markers && pats.length > 0 && hasBar) {
      const bulls = pats.filter((p) => p.endsWith("_bull")).length;
      const bears = pats.filter((p) => p.endsWith("_bear")).length;
      const bull = bulls >= bears;
      const m: SeriesMarker<Time>[] = [
        {
          time: t0 as UTCTimestamp,
          position: bull ? "belowBar" : "aboveBar",
          color: bull ? "#10b981" : "#f43f5e",
          shape: bull ? "arrowUp" : "arrowDown",
          text: prettyPattern(pats[0]),
        },
      ];
      s.setMarkers(m);
    } else {
      s.setMarkers([]);
    }
  }, [signal, layers, data, tf, sym]);

  const toggle = (k: keyof typeof layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const LAYERS: { k: keyof typeof layers; label: string }[] = [
    { k: "levels", label: "Уровни" },
    { k: "zones", label: "FVG / OB" },
    { k: "trade", label: "Вход / SL / TP" },
    { k: "markers", label: "Паттерн" },
  ];

  return (
    <div className="card p-3">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        {LAYERS.map((l) => (
          <button
            key={l.k}
            type="button"
            onClick={() => toggle(l.k)}
            className={`rounded-md border px-2 py-1 text-xs transition ${
              layers[l.k]
                ? "border-sky-700 bg-sky-950/60 text-sky-300"
                : "border-slate-700 text-slate-500 hover:text-slate-300"
            }`}
          >
            {l.label}
          </button>
        ))}
        <span className="ml-auto">
          {crypto ? (
            <StatusPill
              label={ws === "live" ? "Live (Binance WS)" : ws === "connecting" ? "WS: подключение…" : "WS: нет связи"}
              state={ws === "live" ? "ok" : ws === "connecting" ? "idle" : "bad"}
            />
          ) : (
            <StatusPill label="Обновление раз в 30 с" state="idle" />
          )}
        </span>
      </div>

      {error && !data && <ErrorBox message={error} onRetry={reload} />}

      <div className="relative">
        <div ref={box} className="h-[380px] w-full sm:h-[470px]" />
        {loading && <Skeleton className="absolute inset-0" />}
      </div>

      <div className="mt-2 flex flex-wrap justify-between gap-2 text-[11px] text-slate-500">
        <span>
          Источник: {data?.source ?? "…"}
          {data?.stale && <span className="ml-1 text-amber-400">· данные устарели</span>}
          {error && data && <span className="ml-1 text-amber-400">· обновление не удалось</span>}
        </span>
        <span>Линии зон = границы FVG / Order Block (прямоугольников в библиотеке нет)</span>
      </div>
    </div>
  );
}
