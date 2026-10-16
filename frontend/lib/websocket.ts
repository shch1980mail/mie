import type { LiveStatus, Timeframe } from "./types";

// Прямое подключение браузера к Binance (минуя наш бэкенд).
// Первый хост: зеркало публичных данных, второй: основной.
const HOSTS = ["wss://data-stream.binance.vision/ws", "wss://stream.binance.com:9443/ws"];

const INTERVAL: Record<Timeframe, string> = {
  M1: "1m",
  M5: "5m",
  M15: "15m",
  M30: "30m",
  H1: "1h",
  H4: "4h",
  D1: "1d",
  W1: "1w",
  MN: "1M",
};

export interface LiveKline {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
}

interface KlineRaw {
  k?: { t: number; o: string; h: string; l: string; c: string; v: string; x: boolean };
}

export function connectKline(
  symbol: string,
  tf: Timeframe,
  onKline: (k: LiveKline) => void,
  onState: (s: LiveStatus) => void,
): () => void {
  let ws: WebSocket | null = null;
  let stopped = false;
  let hostIdx = 0;
  let fails = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const schedule = () => {
    if (stopped) return;
    onState("error");
    const delay = Math.min(30000, 1000 * 2 ** Math.min(fails, 5));
    fails += 1;
    timer = setTimeout(open, delay);
  };

  const open = () => {
    if (stopped) return;
    onState("connecting");
    let gotData = false;
    try {
      ws = new WebSocket(`${HOSTS[hostIdx % HOSTS.length]}/${symbol.toLowerCase()}@kline_${INTERVAL[tf]}`);
    } catch {
      hostIdx += 1;
      schedule();
      return;
    }
    ws.onopen = () => onState("live");
    ws.onmessage = (ev: MessageEvent) => {
      try {
        const m = JSON.parse(String(ev.data)) as KlineRaw;
        if (!m.k) return;
        gotData = true;
        fails = 0;
        onKline({
          time: Math.floor(m.k.t / 1000),
          open: Number(m.k.o),
          high: Number(m.k.h),
          low: Number(m.k.l),
          close: Number(m.k.c),
          volume: Number(m.k.v),
          closed: m.k.x,
        });
      } catch {
        /* битое сообщение пропускаем */
      }
    };
    ws.onerror = () => {
      /* закрытие обработает onclose */
    };
    ws.onclose = () => {
      if (stopped) return;
      if (!gotData) hostIdx += 1;
      schedule();
    };
  };

  open();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    if (ws) {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      try {
        ws.close();
      } catch {
        /* уже закрыт */
      }
    }
    onState("off");
  };
}
