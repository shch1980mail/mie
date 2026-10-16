import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { LiveStatus, SignalRow } from "./types";

// Переменные NEXT_PUBLIC_* должны читаться именно так (буквально), иначе Next не подставит их в сборку
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase: SupabaseClient | null =
  url && key
    ? createClient(url, key, {
        auth: { persistSession: false, autoRefreshToken: false },
        realtime: { params: { eventsPerSecond: 5 } },
      })
    : null;

export const supabaseEnabled = supabase !== null;

export async function fetchRecentSignals(limit = 40): Promise<SignalRow[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("signals")
    .select("id,symbol,timeframe,candle_ts,bias,probability,expectancy_r,recommended,payload,outcome,r_multiple,created_at")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) throw new Error(`Supabase: ${error.message}`);
  return (data ?? []) as unknown as SignalRow[];
}

// Подписка на INSERT (новые сигналы) и UPDATE (разметка исхода). Возвращает функцию отписки.
export function subscribeSignals(
  onInsert: (row: SignalRow) => void,
  onUpdate: (row: SignalRow) => void,
  onStatus: (s: LiveStatus) => void,
): () => void {
  if (!supabase) {
    onStatus("off");
    return () => undefined;
  }
  const client = supabase;
  onStatus("connecting");
  const channel = client
    .channel("signals-feed")
    .on("postgres_changes", { event: "INSERT", schema: "public", table: "signals" }, (p) =>
      onInsert(p.new as SignalRow),
    )
    .on("postgres_changes", { event: "UPDATE", schema: "public", table: "signals" }, (p) =>
      onUpdate(p.new as SignalRow),
    )
    .subscribe((status) => {
      const st = String(status);
      if (st === "SUBSCRIBED") onStatus("live");
      else if (st === "CLOSED") onStatus("off");
      else onStatus("error");
    });
  return () => {
    void client.removeChannel(channel);
  };
}
