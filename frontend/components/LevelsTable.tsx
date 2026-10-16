import { fmtPrice } from "@/lib/format";
import type { Levels } from "@/lib/types";

export default function LevelsTable({ levels, price }: { levels: Levels; price: number }) {
  const dist = (p: number) => {
    const d = ((p - price) / price) * 100;
    return `${d > 0 ? "+" : ""}${d.toFixed(2)}%`;
  };
  const res = [...(levels.resistance ?? [])].sort((a, b) => b.price - a.price);
  const sup = [...(levels.support ?? [])].sort((a, b) => b.price - a.price);
  const zones = [
    ...(levels.fvg ?? []).map((z) => ({ ...z, kind: "FVG" })),
    ...(levels.order_blocks ?? []).map((z) => ({ ...z, kind: "OB" })),
  ];
  const pools = levels.liquidity ?? [];

  return (
    <div className="card">
      <h3 className="h2">Уровни</h3>
      <table className="w-full text-sm tabular-nums">
        <tbody>
          {res.map((l) => (
            <tr key={`r${l.price}`} className="border-b border-slate-800/70">
              <td className="py-1.5 text-xs text-rose-300">Сопротивление</td>
              <td className="py-1.5 text-right">{fmtPrice(l.price)}</td>
              <td className="py-1.5 text-right text-xs text-slate-500">{dist(l.price)}</td>
              <td className="py-1.5 text-right text-xs text-slate-500">{"●".repeat(Math.min(l.touches, 5))}</td>
            </tr>
          ))}
          <tr className="bg-sky-950/40">
            <td className="py-1.5 pl-1 text-xs font-medium text-sky-300">Цена</td>
            <td className="py-1.5 text-right font-semibold text-sky-300">{fmtPrice(price)}</td>
            <td />
            <td />
          </tr>
          {sup.map((l) => (
            <tr key={`s${l.price}`} className="border-b border-slate-800/70">
              <td className="py-1.5 text-xs text-emerald-300">Поддержка</td>
              <td className="py-1.5 text-right">{fmtPrice(l.price)}</td>
              <td className="py-1.5 text-right text-xs text-slate-500">{dist(l.price)}</td>
              <td className="py-1.5 text-right text-xs text-slate-500">{"●".repeat(Math.min(l.touches, 5))}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-slate-500">● = число касаний уровня</p>

      {zones.length > 0 && (
        <>
          <h3 className="h2 mt-4">Зоны спроса / предложения</h3>
          <ul className="space-y-1 text-sm tabular-nums">
            {zones.map((z, i) => (
              <li key={`${z.kind}${i}`} className="flex items-center justify-between gap-2">
                <span className={z.dir === "bull" ? "text-emerald-300" : "text-rose-300"}>
                  {z.kind} {z.dir === "bull" ? "бычья" : "медвежья"}
                </span>
                <span className="text-slate-300">
                  {fmtPrice(z.lo)} – {fmtPrice(z.hi)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {pools.length > 0 && (
        <>
          <h3 className="h2 mt-4">Ликвидность (equal highs / lows)</h3>
          <ul className="space-y-1 text-sm tabular-nums">
            {pools.map((p, i) => (
              <li key={i} className="flex justify-between">
                <span className="text-violet-300">{p.type === "H" ? "Equal highs" : "Equal lows"}</span>
                <span className="text-slate-300">{fmtPrice(p.price)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
