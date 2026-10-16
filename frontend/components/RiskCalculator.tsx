"use client";

import { useEffect, useState } from "react";
import { fmtNum, fmtPrice } from "@/lib/format";
import type { Signal } from "@/lib/types";

const num = (s: string) => Number(s.replace(",", ".").trim());

export default function RiskCalculator({ signal }: { signal: Signal | null }) {
  const [deposit, setDeposit] = useState("10000");
  const [riskPct, setRiskPct] = useState("1");
  const [entry, setEntry] = useState("");
  const [sl, setSl] = useState("");

  const sigKey = signal ? `${signal.symbol}|${signal.timeframe}|${signal.candle_ts}` : "";
  useEffect(() => {
    if (signal?.entry && signal.stop_loss != null) {
      setEntry(String(signal.entry.aggressive));
      setSl(String(signal.stop_loss));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sigKey]);

  const dep = num(deposit);
  const rp = num(riskPct);
  const e = num(entry);
  const s = num(sl);
  const valid = [dep, rp, e, s].every(Number.isFinite) && dep > 0 && rp > 0 && e > 0 && s > 0 && e !== s;

  const riskAmt = valid ? (dep * rp) / 100 : 0;
  const dist = valid ? Math.abs(e - s) : 0;
  const units = valid ? riskAmt / dist : 0;
  const notional = units * e;
  const side = e > s ? 1 : -1;
  const isFx = signal?.asset_class === "fx";

  return (
    <div className="card">
      <h3 className="h2">Калькулятор риска</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Депозит</label>
          <input className="input" inputMode="decimal" value={deposit} onChange={(ev) => setDeposit(ev.target.value)} />
        </div>
        <div>
          <label className="label">Риск на сделку, %</label>
          <input className="input" inputMode="decimal" value={riskPct} onChange={(ev) => setRiskPct(ev.target.value)} />
        </div>
        <div>
          <label className="label">Цена входа</label>
          <input className="input" inputMode="decimal" value={entry} onChange={(ev) => setEntry(ev.target.value)} />
        </div>
        <div>
          <label className="label">Стоп-лосс</label>
          <input className="input" inputMode="decimal" value={sl} onChange={(ev) => setSl(ev.target.value)} />
        </div>
      </div>

      {valid ? (
        <div className="mt-4 space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Направление</span>
            <span className={side === 1 ? "text-emerald-400" : "text-rose-400"}>{side === 1 ? "LONG" : "SHORT"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Риск в деньгах</span>
            <span className="tabular-nums">{fmtNum(riskAmt, 2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Дистанция до стопа</span>
            <span className="tabular-nums">{fmtPrice(dist)}</span>
          </div>
          <div className="flex justify-between font-semibold">
            <span className="text-slate-300">Размер позиции</span>
            <span className="tabular-nums">
              {fmtNum(units, 4)} ед.{isFx ? ` ≈ ${fmtNum(units / 100000, 2)} лота` : ""}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Номинал позиции</span>
            <span className="tabular-nums">{fmtNum(notional, 2)}</span>
          </div>
          {signal?.take_profits.map((t, i) => {
            const ok = side * (t.price - e) > 0;
            return (
              <div key={i} className="flex justify-between">
                <span className="text-slate-400">Прибыль на TP{i + 1}</span>
                <span className={`tabular-nums ${ok ? "text-emerald-400" : "text-slate-500"}`}>
                  {ok ? `+${fmtNum(units * Math.abs(t.price - e), 2)}` : "цель не по направлению"}
                </span>
              </div>
            );
          })}
          {rp > 2 && (
            <p className="rounded bg-amber-950/40 p-2 text-xs text-amber-300">
              Риск выше 2% на сделку: серия из нескольких стопов быстро съедает депозит.
            </p>
          )}
        </div>
      ) : (
        <p className="mt-4 text-xs text-slate-500">Введите корректные значения (вход ≠ стоп, все числа больше нуля).</p>
      )}
      <p className="mt-3 text-[11px] leading-snug text-slate-500">
        Расчёт в единицах базового актива, в валюте котировки. Для пар без USD в котировке (например, EURGBP) и для
        контрактов с множителем пересчитайте стоимость пункта по спецификации брокера. Спред и комиссия не учтены.
      </p>
    </div>
  );
}
