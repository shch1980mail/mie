import axios, { AxiosError } from "axios";
import type {
  BestResponse,
  CalendarResponse,
  CandlesResponse,
  HealthResponse,
  Impact,
  ScanResponse,
  Signal,
  Timeframe,
} from "./types";

// Если NEXT_PUBLIC_API_URL не задан, идём через прокси Vercel (/backend -> BACKEND_URL)
const baseURL = (process.env.NEXT_PUBLIC_API_URL || "/backend").replace(/\/$/, "");

// Таймаут 30 с: Hugging Face Space может просыпаться
export const http = axios.create({ baseURL, timeout: 30000 });

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export function apiErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const ae = e as AxiosError<{ detail?: unknown }>;
    if (ae.response) {
      const d = ae.response.data?.detail;
      const detail = typeof d === "string" ? d : d ? JSON.stringify(d) : "";
      return `Ошибка ${ae.response.status}${detail ? ": " + detail : ""}`;
    }
    if (ae.code === "ECONNABORTED") {
      return "Бэкенд не ответил вовремя (возможно, просыпается). Повторите через минуту.";
    }
    return "Нет связи с бэкендом. Проверьте интернет, NEXT_PUBLIC_API_URL и CORS.";
  }
  return e instanceof Error ? e.message : "Неизвестная ошибка";
}

async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  let last: unknown;
  for (let i = 0; i < 2; i++) {
    try {
      const r = await http.get<T>(url, { params });
      return r.data;
    } catch (e) {
      last = e;
      if (axios.isAxiosError(e) && e.response && e.response.status < 500) break;
      if (i === 0) await sleep(1500);
    }
  }
  throw last;
}

export interface ScanParams {
  tf: Timeframe;
  asset_class?: string;
  min_prob?: number;
  actionable?: boolean;
  limit?: number;
}

export const getScan = (p: ScanParams) =>
  get<ScanResponse>("/scan", { ...p, asset_class: p.asset_class || undefined });

export const getSignal = (symbol: string, tf: Timeframe) =>
  get<Signal>(`/signals/${encodeURIComponent(symbol)}`, { tf });

export const getBest = (symbol: string) => get<BestResponse>(`/best/${encodeURIComponent(symbol)}`);

export const getCandles = (symbol: string, tf: Timeframe, limit = 300) =>
  get<CandlesResponse>(`/candles/${encodeURIComponent(symbol)}`, { tf, limit });

export const getCalendar = (p: { hours?: number; min_impact?: Impact; symbol?: string }) =>
  get<CalendarResponse>("/calendar", p);

export const getHealth = () => get<HealthResponse>("/health");
