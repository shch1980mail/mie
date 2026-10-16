import type { MtfInfo } from "@/lib/types";

function label(v: number): string {
  return v > 0.5 ? "бычий" : v > 0.15 ? "слабо бычий" : v < -0.5 ? "медвежий" : v < -0.15 ? "слабо медвежий" : "нейтрален";
}

export default function MTFTable({ mtf }: { mtf: MtfInfo | undefined }) {
  const entries = Object.entries(mtf?.per_tf ?? {});
  return (
    <div className="card">
      <h3 className="h2">Старшие таймфреймы</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">Данные старших ТФ недоступны: MTF-фильтр не применялся.</p>
      ) : (
        <>
          <ul className="space-y-2.5">
            {entries.map(([tf, v]) => {
              const w = Math.min(Math.abs(v), 1) * 50;
              return (
                <li key={tf}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-medium text-slate-200">{tf}</span>
                    <span className={v > 0.15 ? "text-emerald-400" : v < -0.15 ? "text-rose-400" : "text-slate-400"}>
                      {label(v)} ({v > 0 ? "+" : ""}
                      {v.toFixed(2)})
                    </span>
                  </div>
                  <div className="relative h-1.5 rounded bg-slate-800">
                    <div className="absolute left-1/2 top-0 h-1.5 w-px bg-slate-600" />
                    <div
                      className={`absolute top-0 h-1.5 rounded ${v >= 0 ? "bg-emerald-500" : "bg-rose-500"}`}
                      style={v >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 flex justify-between border-t border-slate-800 pt-2 text-xs">
            <span className="text-slate-400">Итоговый bias старших ТФ</span>
            <span
              className={
                (mtf?.bias ?? 0) > 0.15 ? "text-emerald-400" : (mtf?.bias ?? 0) < -0.15 ? "text-rose-400" : "text-slate-400"
              }
            >
              {label(mtf?.bias ?? 0)} ({(mtf?.bias ?? 0) > 0 ? "+" : ""}
              {(mtf?.bias ?? 0).toFixed(2)})
            </span>
          </div>
        </>
      )}
    </div>
  );
}
