import type { Bias } from "@/lib/types";

const MAP: Record<Bias, { label: string; cls: string }> = {
  bullish: { label: "▲ Бычий", cls: "border-emerald-700 bg-emerald-950/60 text-emerald-300" },
  bearish: { label: "▼ Медвежий", cls: "border-rose-700 bg-rose-950/60 text-rose-300" },
  neutral: { label: "● Нейтральный", cls: "border-slate-700 bg-slate-800/60 text-slate-300" },
};

export default function BiasBadge({ bias, className = "" }: { bias: Bias; className?: string }) {
  const m = MAP[bias] ?? MAP.neutral;
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${m.cls} ${className}`}
    >
      {m.label}
    </span>
  );
}
