import type { Timeframe } from "./types";

export const TIMEFRAMES: Timeframe[] = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"];

export const ASSET_CLASSES: { value: string; label: string }[] = [
  { value: "", label: "Все классы" },
  { value: "fx", label: "Forex" },
  { value: "metal", label: "Металлы" },
  { value: "energy", label: "Энергия" },
  { value: "agri", label: "Агро (ETF)" },
  { value: "stock", label: "Акции" },
  { value: "index", label: "Индексы" },
  { value: "etf", label: "ETF" },
  { value: "bond", label: "Облигации" },
  { value: "crypto", label: "Крипто" },
];

export function priceDigits(x: number): number {
  const a = Math.abs(x);
  return a < 1 ? 6 : a < 10 ? 5 : a < 100 ? 4 : a < 10000 ? 3 : 2;
}

export function fmtPrice(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return "—";
  const d = priceDigits(x);
  return x.toLocaleString("en-US", { minimumFractionDigits: Math.min(2, d), maximumFractionDigits: d });
}

export function fmtNum(x: number | null | undefined, d = 2): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return x.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: d });
}

export function fmtPct(p: number | null | undefined): string {
  if (p == null || !Number.isFinite(p)) return "—";
  return `${(p * 100).toFixed(0)}%`;
}

export function fmtR(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return `${x > 0 ? "+" : ""}${x.toFixed(2)}R`;
}

export function timeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "—";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "только что";
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч назад`;
  return `${Math.floor(s / 86400)} дн назад`;
}

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function fmtCountdown(min: number): string {
  if (min < 0) return `${Math.abs(min)} мин назад`;
  if (min < 60) return `через ${min} мин`;
  return `через ${Math.floor(min / 60)} ч ${min % 60} мин`;
}

export function isCryptoSymbol(symbol: string): boolean {
  return /USDT$/i.test(symbol);
}

const PAT: Record<string, string> = {
  pin: "Пин-бар",
  hammer: "Молот",
  shooting_star: "Падающая звезда",
  engulfing: "Поглощение",
  harami: "Харами",
  morning_star: "Утренняя звезда",
  evening_star: "Вечерняя звезда",
  three_soldiers: "Три солдата",
  three_crows: "Три вороны",
  tweezer_bottom: "Пинцет (дно)",
  tweezer_top: "Пинцет (вершина)",
  marubozu: "Марубозу",
  doji: "Доджи",
  inside_bar: "Внутренний бар",
  outside_bar: "Внешний бар",
};

export function prettyPattern(name: string): string {
  const raw = name.startsWith("ctx:") ? name.slice(4) : name;
  const m = raw.match(/^(.*?)(?:_(bull|bear))?$/);
  const base = m ? m[1] : raw;
  const dir = m && m[2] === "bull" ? " ↑" : m && m[2] === "bear" ? " ↓" : "";
  return (PAT[base] ?? base.replace(/_/g, " ")) + dir;
}
