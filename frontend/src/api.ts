const BASE = "/api";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getTodaySummary: () => fetchJSON<import("./types").SummaryData>("/signals/summary/today"),

  getSignalDates: () => fetchJSON<string[]>("/signals/dates"),

  getTodaySignals: (limit = 50, minScore = 50, date?: string) =>
    fetchJSON<import("./types").SignalData[]>(
      `/signals/today?limit=${limit}&min_score=${minScore}${date ? `&date=${date}` : ""}`
    ),

  getKline: (tsCode: string, days = 120) =>
    fetchJSON<import("./types").KlineData[]>(`/signals/kline/${tsCode}?days=${days}`),

  getSignalStats: (horizon = 5) =>
    fetchJSON<any>(`/backtest/signal-stats?horizon=${horizon}`),

  runBacktest: (params: Record<string, any>) =>
    fetchJSON<import("./types").BacktestResult>(
      `/backtest/run`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params) }
    ),

  getWatchlist: () => fetchJSON<import("./types").StockInfo[]>("/monitor/watchlist"),

  addToWatchlist: (tsCode: string, name: string) =>
    fetchJSON<any>("/monitor/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ts_code: tsCode, name }),
    }),

  checkStock: (tsCode: string) =>
    fetchJSON<any>(`/monitor/check/${tsCode}`),

  getAlerts: (limit = 50) =>
    fetchJSON<import("./types").AlertData[]>(`/monitor/alerts?limit=${limit}`),

  clearAlerts: () =>
    fetchJSON<any>("/monitor/alerts", { method: "DELETE" }),

  searchStocks: (q: string) =>
    fetchJSON<import("./types").StockInfo[]>(`/data/stocks?search=${q}`),

  getTopGainers: (date?: string) =>
    fetchJSON<{ year_top: any[]; month_top: any[]; new_listings: any[]; date: string; available_dates: string[] }>(
      `/data/top-gainers${date ? `?date=${date}` : ""}`
    ) as Promise<import("./types").TopData>,

  getGainerAnalysis: (date?: string, topN = 30) =>
    fetchJSON<{ date: string; top_count: number; analyzed: number; summary: string; detail: any }>(
      `/data/top-gainers/analysis?top_n=${topN}${date ? `&date=${date}` : ""}`
    ),
};
