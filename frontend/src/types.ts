export type Role = "admin" | "vip" | "user";

export type User = {
  id: number;
  username: string;
  email?: string | null;
  role: Role;
  status?: string | null;
};

export type Strategy = {
  id: number;
  owner_id: number;
  owner_name?: string | null;
  name: string;
  description?: string | null;
  benchmark?: string | null;
  tags?: string[] | null;
  status?: string | null;
  created_at: string;
  updated_at: string;
};

export type StrategyListResponse = {
  total: number;
  items: Strategy[];
};

export type Batch = {
  id: number;
  strategy_id: number;
  name: string;
  batch_date: string;
  description?: string | null;
  status?: string | null;
  created_at: string;
  updated_at: string;
};

export type BatchStock = {
  id: number;
  batch_id: number;
  stock_code: string;
  stock_name?: string | null;
  remark?: string | null;
  added_date?: string | null;
  is_traded: boolean;
  is_held: boolean;
  added_at: string;
};

export type NewStock = {
  stock_code: string;
  stock_name: string;
  remark: string;
};

export type StockPerformance = {
  stock_code: string;
  stock_name?: string | null;
  batch_id: number;
  batch_name?: string | null;
  added_date?: string | null;
  hold_days: number;
  current_return: number;
  max_drawdown: number;
  max_gain: number;
  is_profitable: boolean;
};

export type StrategyOverview = {
  best_stock: StockPerformance | null;
  worst_stock: StockPerformance | null;
  win_rate: number;
  total_stocks: number;
  profitable_stocks: number;
  losing_stocks: number;
  average_return: number;
  max_drawdown: number;
  max_gain: number;
};

export type WinRateHistory = {
  dates: string[];
  win_rates: number[];
  total_stocks: number[];
};

export type StockKline = {
  stock_code: string;
  dates: string[];
  opens: (number | null)[];
  closes: number[];
  highs: (number | null)[];
  lows: (number | null)[];
  volumes: number[];
};

export type BatchDetail = Batch & {
  stocks: BatchStock[];
};

export type MetricsPoint = {
  trade_date: string;
  daily_return: number;
  cumulative_return: number;
};

export type MetricsResponse = {
  strategy_id?: number | null;
  batch_id?: number | null;
  stock_code?: string | null;
  start: string;
  end: string;
  daily: MetricsPoint[];
  summary: {
    total_return: number;
    max_drawdown: number;
    max_gain: number;
  };
};

export type SyncResult = {
  trade_date: string;
  success_count: number;
  fail_count: number;
  errors: string[];
  recalculated_metrics: number;
  provider?: string;
};

export type HoldReturnResponse = {
  scope: string;
  id: number;
  n: number;
  k: number;
  hold_return: number | null;
  status: string;
};

export type BatchComparisonItem = {
  batch_id: number;
  batch_name: string;
  total_return: number;
  max_drawdown: number;
  max_gain: number;
};

export type BatchComparisonResponse = {
  strategy_id: number;
  trade_date?: string | null;
  batch_comparison: BatchComparisonItem[];
};

export type SyncLog = {
  log_type?: string;
  level?: string;
  trade_date?: string | null;
  status: string;
  success_count: number;
  fail_count: number;
  error_detail?: string | null;
  source?: string;
  message?: string | null;
  created_at: string;
};

export type AppLog = {
  id: number;
  level: string;
  category: string;
  message: string;
  details?: Record<string, unknown> | null;
  source?: string | null;
  created_at: string;
};

export type AnyLog = SyncLog | AppLog;

export type MaintenanceStatus = {
  is_running: boolean;
  last_error?: string | null;
};

export type StockDetail = {
  stock_code: string;
  stock_name?: string | null;
  batch_id: number;
  batch_name?: string | null;
  added_date?: string | null;
  added_close_price?: number | null;
  current_price?: number | null;
  current_return: number;
  max_drawdown: number;
  max_gain: number;
  hold_days: number;
  return_history?: {
    date: string;
    return: number;
  }[];
};

export type BatchStockPerformance = {
  id: number;
  stock_code: string;
  stock_name?: string | null;
  added_date?: string | null;
  added_close_price?: number | null;
  current_price?: number | null;
  current_return: number;
  max_drawdown: number;
  max_gain: number;
  hold_days: number;
  remark?: string | null;
  is_traded: boolean;
  is_held: boolean;
};
