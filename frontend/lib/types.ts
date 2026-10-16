export type Bias = "bullish" | "bearish" | "neutral";
export type Timeframe = "M1" | "M5" | "M15" | "M30" | "H1" | "H4" | "D1" | "W1" | "MN";
export type Impact = "low" | "medium" | "high";
export type LiveStatus = "off" | "connecting" | "live" | "error";
export type Outcome = "tp1" | "sl" | "expired" | "no_data" | null;

export interface Level {
  price: number;
  touches: number;
}

export interface Zone {
  dir: "bull" | "bear";
  lo: number;
  hi: number;
  ts?: string;
}

export interface Pool {
  type: "H" | "L";
  price: number;
}

export interface Levels {
  support: Level[];
  resistance: Level[];
  fvg: Zone[];
  order_blocks: Zone[];
  liquidity: Pool[];
}

export interface Entry {
  aggressive: number;
  conservative: number | null;
  conservative_zone: Zone | null;
}

export interface Target {
  price: number;
  rr: number;
}

export interface StructureEvent {
  type: "BOS" | "CHoCH";
  dir: "up" | "down";
  level: number;
  ts: string;
}

export interface MtfInfo {
  bias: number;
  per_tf: Record<string, number>;
}

export interface TechDetails {
  score: number;
  trend: number;
  macd_hist_atr: number;
  rsi: number;
  adx: number;
  stoch_k: number;
  cci: number;
  williams_r: number;
  bb_pos: number | null;
  ichimoku: string;
  divergence: string | null;
}

export interface Rationale {
  candles: { score: number; patterns: string[] };
  technical: TechDetails;
  fundamental: {
    score: number;
    notes: string[];
    cot_pct: number | null;
    fear_greed: number | null;
  };
  structure: { trend: number; last_event: StructureEvent | null };
  mtf: MtfInfo;
  weights: { candles: number; technical: number; fundamental: number };
  model?: { group: string; p_symmetric: number; source: string; info: unknown };
}

export interface Signal {
  symbol: string;
  name: string;
  asset_class: string;
  timeframe: Timeframe;
  candle_ts: string;
  generated_at: string;
  price: number;
  atr: number;
  bias: Bias;
  score: number;
  recommended: boolean;
  probability: number | null;
  probability_tp2: number | null;
  probability_source: "ml_calibrated" | "heuristic" | "none" | string;
  expectancy_r: number | null;
  levels: Levels;
  entry: Entry | null;
  stop_loss: number | null;
  take_profits: Target[];
  rationale: Rationale;
  risks: string[];
  data: { source?: string; bars?: number; profile?: string };
  stale: boolean;
}

export interface ScanResponse {
  timeframe: Timeframe;
  count: number;
  missing: string[];
  generated_at: string;
  items: Signal[];
}

export interface CandleBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandlesResponse {
  symbol: string;
  timeframe: Timeframe;
  source: string;
  stale: boolean;
  candles: CandleBar[];
}

export interface BestCandidate {
  timeframe: Timeframe;
  bias: Bias;
  score: number;
  probability: number | null;
  expectancy_r: number | null;
  recommended: boolean;
}

export interface BestResponse {
  best: Signal | null;
  candidates: BestCandidate[];
}

export interface CalendarEvent {
  ts: string;
  ccy: string | null;
  country: string | null;
  event: string;
  impact: Impact;
  actual: number | null;
  estimate: number | null;
  prev: number | null;
  source: string;
  minutes_to: number;
}

export interface CalendarResponse {
  count: number;
  source_status: Record<string, string>;
  events: CalendarEvent[];
}

export interface HealthResponse {
  status: string;
  uptime_s: number;
  time: string;
}

export interface SignalRow {
  id: number;
  symbol: string;
  timeframe: Timeframe;
  candle_ts: string;
  bias: Bias;
  probability: number | null;
  expectancy_r: number | null;
  recommended: boolean;
  payload: Signal;
  outcome: Outcome;
  r_multiple: number | null;
  created_at: string;
}
