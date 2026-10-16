import { fmtNum, fmtPrice, prettyPattern } from "@/lib/format";
import type { Signal } from "@/lib/types";

function ScoreBar({ label, value, weight }: { label: string; value: number; weight?: number }) {
  const w = Math.min(Math.abs(value), 1) * 50;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-slate-300">
          {label}
          {weight != null && <span className="text-slate-500"> · вес {Math.round(weight * 100)}%</span>}
        </span>
        <span className={value > 0 ? "text-emerald-400" : value < 0 ? "text-rose-400" : "text-slate-400"}>
          {value > 0 ? "+" : ""}
          {value.toFixed(2)}
        </span>
      </div>
      <div className="relative h-2 rounded bg-slate-800">
        <div className="absolute left-1/2 top-0 h-2 w-px bg-slate-600" />
        <div
          className={`absolute top-0 h-2 rounded ${value >= 0 ? "bg-emerald-500" : "bg-rose-500"}`}
          style={value >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
        />
      </div>
    </div>
  );
}

const DIVERGENCE: Record<string, string> = {
  bullish_regular: "бычья (regular)",
  bullish_hidden: "бычья (hidden)",
  bearish_regular: "медвежья (regular)",
  bearish_hidden: "медвежья (hidden)",
};

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-slate-800/60 py-1 text-xs">
      <span className="text-slate-500">{k}</span>
      <span className="text-right tabular-nums text-slate-200">{v}</span>
    </div>
  );
}

export default function SignalDetails({ sig }: { sig: Signal }) {
  const r = sig.rationale;
  const t = r.technical;
  const f = r.fundamental;
  const pats = r.candles?.patterns ?? [];
  const main = pats.filter((p) => !p.startsWith("ctx:"));
  const ctx = pats.filter((p) => p.startsWith("ctx:"));
  const ev = r.structure?.last_event;

  return (
    <div className="card space-y-5">
      <div>
        <h3 className="h2">Обоснование</h3>
        <div className="space-y-3">
          <ScoreBar label="Свечи (Price Action)" value={r.candles?.score ?? 0} weight={r.weights?.candles} />
          <ScoreBar label="Технический анализ" value={t?.score ?? 0} weight={r.weights?.technical} />
          <ScoreBar label="Фундамент" value={f?.score ?? 0} weight={r.weights?.fundamental} />
          <ScoreBar label="Итоговый score" value={sig.score} />
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-400">Свечные паттерны</h4>
          {main.length === 0 ? (
            <p className="text-xs text-slate-500">Значимых паттернов на последних трёх свечах нет.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {main.map((p, i) => (
                <span
                  key={i}
                  className={`rounded-md border px-2 py-0.5 text-xs ${
                    p.endsWith("_bull")
                      ? "border-emerald-800 text-emerald-300"
                      : p.endsWith("_bear")
                        ? "border-rose-800 text-rose-300"
                        : "border-slate-700 text-slate-300"
                  }`}
                >
                  {prettyPattern(p)}
                </span>
              ))}
            </div>
          )}
          {ctx.length > 0 && (
            <p className="mt-1.5 text-xs text-slate-500">Контекст: {ctx.map(prettyPattern).join(", ")}</p>
          )}
          <h4 className="mb-1 mt-4 text-xs font-semibold uppercase text-slate-400">Структура рынка</h4>
          <Row
            k="Тренд (HH/HL/LH/LL)"
            v={r.structure?.trend === 1 ? "восходящий" : r.structure?.trend === -1 ? "нисходящий" : "не определён"}
          />
          <Row
            k="Последнее событие"
            v={ev ? `${ev.type} ${ev.dir === "up" ? "вверх" : "вниз"} @ ${fmtPrice(ev.level)}` : "—"}
          />
        </div>

        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-400">Индикаторы</h4>
          <Row k="RSI(14)" v={fmtNum(t?.rsi, 1)} />
          <Row k="ADX(14)" v={fmtNum(t?.adx, 1)} />
          <Row k="Stochastic %K" v={fmtNum(t?.stoch_k, 1)} />
          <Row k="CCI(20)" v={fmtNum(t?.cci, 0)} />
          <Row k="Williams %R" v={fmtNum(t?.williams_r, 0)} />
          <Row k="MACD hist / ATR" v={fmtNum(t?.macd_hist_atr, 2)} />
          <Row k="Bollinger (0..1)" v={fmtNum(t?.bb_pos, 2)} />
          <Row k="Ichimoku" v={t?.ichimoku ?? "—"} />
          <Row k="Дивергенция" v={t?.divergence ? (DIVERGENCE[t.divergence] ?? t.divergence) : "нет"} />
          <Row k="ATR" v={fmtPrice(sig.atr)} />
        </div>
      </div>

      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase text-slate-400">Фундамент и sentiment</h4>
        {f?.notes?.length ? (
          <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-300">
            {f.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-500">Свежих релизов по валютам инструмента нет.</p>
        )}
        <div className="mt-1.5 grid gap-x-6 sm:grid-cols-2">
          <Row k="COT (перцентиль нетто-позиций, 3 года)" v={f?.cot_pct != null ? `${f.cot_pct.toFixed(0)}` : "—"} />
          <Row k="Fear & Greed (крипта)" v={f?.fear_greed != null ? String(f.fear_greed) : "—"} />
        </div>
      </div>

      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase text-slate-400">Вероятность</h4>
        <Row
          k="Источник"
          v={sig.probability_source === "ml_calibrated" ? "ML (XGBoost + калибровка)" : "эвристика (модель не обучена)"}
        />
        <Row k="P(TP1 раньше SL)" v={sig.probability != null ? `${(sig.probability * 100).toFixed(1)}%` : "—"} />
        <Row k="P(TP2 раньше SL)" v={sig.probability_tp2 != null ? `${(sig.probability_tp2 * 100).toFixed(1)}%` : "—"} />
        <Row k="Профиль анализа" v={sig.data?.profile ?? "—"} />
        <Row k="Свечей в расчёте / источник" v={`${sig.data?.bars ?? "—"} / ${sig.data?.source ?? "—"}`} />
      </div>

      {sig.risks.length > 0 && (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/30 p-3">
          <h4 className="mb-1 text-xs font-semibold uppercase text-amber-400">Что может пойти не так</h4>
          <ul className="list-disc space-y-0.5 pl-4 text-xs text-amber-100/90">
            {sig.risks.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
