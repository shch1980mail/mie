export default function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-rose-800 bg-rose-950/40 p-4 text-sm text-rose-200 sm:flex-row sm:items-center sm:justify-between">
      <span>⚠ {message}</span>
      {onRetry && (
        <button type="button" className="btn shrink-0" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

const TONE: Record<"ok" | "warn" | "bad" | "idle", { dot: string; cls: string }> = {
  ok: { dot: "bg-emerald-400", cls: "border-emerald-800 text-emerald-300" },
  warn: { dot: "bg-amber-400", cls: "border-amber-800 text-amber-300" },
  bad: { dot: "bg-rose-400", cls: "border-rose-800 text-rose-300" },
  idle: { dot: "bg-slate-500", cls: "border-slate-700 text-slate-400" },
};

export function StatusPill({ label, state }: { label: string; state: "ok" | "warn" | "bad" | "idle" }) {
  const t = TONE[state];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${t.cls}`}>
      <span className={`h-2 w-2 rounded-full ${t.dot}`} />
      {label}
    </span>
  );
}
