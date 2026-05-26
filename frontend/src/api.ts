import type {
  AppLog,
  AnyLog,
  Batch,
  BatchComparisonResponse,
  BatchDetail,
  BatchStock,
  BatchStockPerformance,
  HoldReturnResponse,
  MaintenanceStatus,
  MetricsResponse,
  StockDetail,
  Strategy,
  StrategyListResponse,
  StrategyOverview,
  StockKline,
  SyncLog,
  SyncResult,
  User,
  WinRateHistory,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const errorBody = await response.json();
      message = errorBody.detail || errorBody.message || message;
    } catch {
      message = response.statusText;
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  login(username: string, password: string) {
    return request<{ access_token: string; token_type: string; user: User }>(
      "/api/auth/login",
      {
        method: "POST",
        body: { username, password },
      },
    );
  },
  register(username: string, password: string, email?: string) {
    return request<User>("/api/auth/register", {
      method: "POST",
      body: { username, password, email },
    });
  },
  me(token: string) {
    return request<User>("/api/auth/me", { token });
  },
  createUser(
    token: string,
    payload: {
      username: string;
      password: string;
      email?: string;
      role: string;
    },
  ) {
    return request<User>("/api/users/", {
      method: "POST",
      token,
      body: payload,
    });
  },
  listStrategies(token: string, keyword = "", page = 1, pageSize = 50) {
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(pageSize),
    });
    if (keyword) params.set("keyword", keyword);
    return request<StrategyListResponse>(
      `/api/strategies/?${params.toString()}`,
      { token },
    );
  },
  createStrategy(
    token: string,
    payload: {
      name: string;
      description?: string;
      benchmark?: string;
      tags?: string[];
    },
  ) {
    return request<Strategy>("/api/strategies/", {
      method: "POST",
      token,
      body: payload,
    });
  },
  updateStrategy(
    token: string,
    strategyId: number,
    payload: Partial<Strategy>,
  ) {
    return request<Strategy>(`/api/strategies/${strategyId}`, {
      method: "PUT",
      token,
      body: payload,
    });
  },
  deleteStrategy(token: string, strategyId: number) {
    return request<{ ok: boolean }>(`/api/strategies/${strategyId}`, {
      method: "DELETE",
      token,
    });
  },
  listBatches(token: string, strategyId: number) {
    return request<Batch[]>(`/api/strategies/${strategyId}/batches`, { token });
  },
  getStrategyOverview(token: string, strategyId: number) {
    return request<StrategyOverview>(`/api/strategies/${strategyId}/overview`, {
      token,
    });
  },
  getWinRateHistory(token: string, strategyId: number) {
    return request<WinRateHistory>(
      `/api/strategies/${strategyId}/win-rate-history`,
      { token },
    );
  },
  getStockKline(token: string, stockCode: string, start: string, end: string) {
    return request<StockKline>(
      `/api/stocks/${stockCode}/kline?start=${start}&end=${end}`,
      { token },
    );
  },
  getStockDetail(token: string, batchId: number, stockId: number) {
    return request<StockDetail>(
      `/api/batches/${batchId}/stocks/${stockId}/detail`,
      { token },
    );
  },
  getBatchStocksPerformance(token: string, batchId: number) {
    return request<BatchStockPerformance[]>(
      `/api/batches/${batchId}/stocks/performance`,
      { token },
    );
  },
  getBatch(token: string, batchId: number) {
    return request<BatchDetail>(`/api/batches/${batchId}`, { token });
  },
  createBatch(
    token: string,
    strategyId: number,
    payload: {
      name: string;
      batch_date: string;
      description?: string;
      status?: string;
      stocks?: Array<{
        stock_code: string;
        stock_name?: string;
        remark?: string;
      }>;
    },
  ) {
    return request<Batch>(`/api/strategies/${strategyId}/batches`, {
      method: "POST",
      token,
      body: payload,
    });
  },
  updateBatch(token: string, batchId: number, payload: Partial<Batch>) {
    return request<Batch>(`/api/batches/${batchId}`, {
      method: "PUT",
      token,
      body: payload,
    });
  },
  deleteBatch(token: string, batchId: number) {
    return request<{ ok: boolean }>(`/api/batches/${batchId}`, {
      method: "DELETE",
      token,
    });
  },
  addStocks(
    token: string,
    batchId: number,
    stocks: Array<{
      stock_code: string;
      stock_name?: string;
      remark?: string;
      is_held?: boolean;
      is_traded?: boolean;
    }>,
  ) {
    return request<BatchStock[]>(`/api/batches/${batchId}/stocks/bulk`, {
      method: "POST",
      token,
      body: { stocks },
    });
  },
  updateStock(
    token: string,
    batchId: number,
    stockId: number,
    payload: Partial<BatchStock>,
  ) {
    return request<BatchStock>(`/api/batches/${batchId}/stocks/${stockId}`, {
      method: "PUT",
      token,
      body: payload,
    });
  },
  deleteStock(token: string, batchId: number, stockId: number) {
    return request<{ ok: boolean }>(
      `/api/batches/${batchId}/stocks/${stockId}`,
      { method: "DELETE", token },
    );
  },
  sync(
    token: string,
    payload: {
      trade_date: string;
      stock_codes: string[];
      index_codes: string[];
      recalculate_metrics?: boolean;
    },
  ) {
    return request<SyncResult>("/api/data/sync", {
      method: "POST",
      token,
      body: payload,
    });
  },
  getStrategyMetrics(
    token: string,
    strategyId: number,
    start: string,
    end: string,
  ) {
    return request<MetricsResponse>(
      `/api/strategies/${strategyId}/metrics?start=${start}&end=${end}`,
      { token },
    );
  },
  getBatchMetrics(token: string, batchId: number, start: string, end: string) {
    return request<MetricsResponse>(
      `/api/batches/${batchId}/metrics?start=${start}&end=${end}`,
      { token },
    );
  },
  getStockMetrics(
    token: string,
    stockCode: string,
    batchId: number,
    start: string,
    end: string,
  ) {
    return request<MetricsResponse>(
      `/api/stocks/${stockCode}/metrics?batch_id=${batchId}&start=${start}&end=${end}`,
      { token },
    );
  },
  holdReturn(
    token: string,
    scope: "strategy" | "batch" | "stock",
    id: number,
    n: number,
    k: number,
  ) {
    return request<HoldReturnResponse>(
      `/api/metrics/hold-return?scope=${scope}&id=${id}&n=${n}&k=${k}`,
      { token },
    );
  },
  compareBatches(token: string, strategyId: number) {
    return request<BatchComparisonResponse>(
      `/api/strategies/${strategyId}/compare-batches`,
      { token },
    );
  },
  getMaintenanceStatus(token: string) {
    return request<MaintenanceStatus>("/api/maintenance/status", { token });
  },
  getMaintenanceLogs(
    token: string,
    params?: {
      start?: string;
      end?: string;
      source?: string;
      log_type?: string;
      level?: string;
      category?: string;
      limit?: number;
    },
  ) {
    const searchParams = new URLSearchParams();
    if (params?.start) searchParams.set("start", params.start);
    if (params?.end) searchParams.set("end", params.end);
    if (params?.source) searchParams.set("source", params.source);
    if (params?.log_type) searchParams.set("log_type", params.log_type);
    if (params?.level) searchParams.set("level", params.level);
    if (params?.category) searchParams.set("category", params.category);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    return request<AnyLog[]>(
      `/api/maintenance/logs?${searchParams.toString()}`,
      { token },
    );
  },
  getSyncLogs(
    token: string,
    params?: {
      start?: string;
      end?: string;
      source?: string;
      log_type?: string;
      limit?: number;
    },
  ) {
    const searchParams = new URLSearchParams();
    if (params?.start) searchParams.set("start", params.start);
    if (params?.end) searchParams.set("end", params.end);
    if (params?.source) searchParams.set("source", params.source);
    if (params?.log_type) searchParams.set("log_type", params.log_type);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    return request<SyncLog[]>(
      `/api/maintenance/logs/sync?${searchParams.toString()}`,
      { token },
    );
  },
  getAppLogs(
    token: string,
    params?: {
      level?: string;
      category?: string;
      source?: string;
      start?: string;
      end?: string;
      limit?: number;
    },
  ) {
    const searchParams = new URLSearchParams();
    if (params?.level) searchParams.set("level", params.level);
    if (params?.category) searchParams.set("category", params.category);
    if (params?.source) searchParams.set("source", params.source);
    if (params?.start) searchParams.set("start", params.start);
    if (params?.end) searchParams.set("end", params.end);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    return request<AppLog[]>(
      `/api/maintenance/logs/app?${searchParams.toString()}`,
      { token },
    );
  },
  startMaintenance(
    token: string,
    intervalHours?: number,
    lookbackDays?: number,
  ) {
    return request<{ status: string }>("/api/maintenance/start", {
      method: "POST",
      token,
      body:
        intervalHours !== undefined ?
          { interval_hours: intervalHours, lookback_days: lookbackDays || 60 }
        : undefined,
    });
  },
  stopMaintenance(token: string) {
    return request<{ status: string }>("/api/maintenance/stop", {
      method: "POST",
      token,
    });
  },
  searchStockByCode(token: string, stockCode: string) {
    return request<{ stock_code: string; stock_name?: string | null }>(
      `/api/stocks/search?stock_code=${stockCode}`,
      { token },
    );
  },
};
