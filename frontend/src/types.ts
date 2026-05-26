export interface KlineData {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover?: number;
  pct_chg?: number;
}

export interface SignalData {
  id: number;
  ts_code: string;
  name?: string;
  trade_date: string;
  composite_score: number;
  rule_signals: string;
  confidence: number;
  up_5d_prob: number;
  up_20d_prob: number;
  market_regime: string;
  risk_flags: string;
  // 从 rule_signals 解析出的字段（前端用）
  _parsed?: {
    vp_score: number;
    char_score: number;
    limit_up_year: number;
    limit_up_month: number;
    vol_ratio: number;
  };
}

export interface SummaryData {
  date: string;
  avg_score: number;
  high_signal_count: number;
  total_signals: number;
  active_alerts: number;
}

export interface AlertData {
  id: number;
  ts_code: string;
  name?: string;
  alert_type: string;
  severity: "warning" | "danger" | "info";
  message: string;
  suggestion: string;
  triggered_at: string;
  resolved: number;
}

export interface BacktestMetrics {
  annual_return: number;
  max_drawdown: number;
  max_dd_days: number;
  sharpe_ratio: number;
  calmar_ratio: number;
  win_rate: number;
  profit_loss_ratio: number;
  total_trades: number;
  total_return: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface Trade {
  ts_code: string;
  name?: string;
  date: string;
  type: "buy" | "sell";
  reason?: string;
  shares: number;
  price: number;
  pnl_pct: number;
  pnl: number;
}

export interface BacktestResult {
  metrics: BacktestMetrics;
  trades: Trade[];
  equity_curve: EquityPoint[];
}

export interface StockInfo {
  ts_code: string;
  name: string;
  industry?: string;
}

export interface GainerRow {
  ts_code: string;
  name: string;
  ret_1y?: number | null;
  ret_1m?: number | null;
  ret_mtd?: number | null;
  ret_ytd?: number | null;
  pct_chg?: number | null;
  ipo_ret?: number | null;
  lu_year: number;
  lu_month: number;
  close: number;
  ipo_date?: string;
}

export interface TopData {
  date: string;
  year_top: GainerRow[];
  month_top: GainerRow[];
  new_listings: GainerRow[];
  available_dates: string[];
  rank_change_month: Record<string, number>;
  rank_change_year: Record<string, number>;
}
