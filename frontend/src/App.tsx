import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  Circle,
  DatabaseZap,
  Edit,
  Layers,
  LineChart as LineChartIcon,
  List,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Trash2,
  Upload,
  UserPlus,
} from "lucide-react";
import { api, ApiError } from "./api";
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
  Strategy,
  StrategyOverview,
  StockDetail,
  StockKline,
  SyncLog,
  User,
  WinRateHistory,
  NewStock,
} from "./types";
import "./styles.css";
import { CandlestickChart } from "./components/CandlestickChart";

const storedToken = localStorage.getItem("stock_strategy_token");
const strategyPageSize = 12;
const tablePageSize = 10;
const logPageSize = 20;

type Page =
  | "strategies"
  | "strategy-detail"
  | "batch-detail"
  | "stock-detail"
  | "admin-logs";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgo(days: number) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

function formatPercent(value?: number | null) {
  if (value === undefined || value === null) return "0.00%";
  return `${(value * 100).toFixed(2)}%`;
}

function classForReturn(value?: number | null) {
  if (!value) return "muted";
  return value > 0 ? "positive" : "negative";
}

function parseStockRows(input: string) {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(/[\s,，]+/).filter(Boolean);
      return {
        stock_code: parts[0],
        stock_name: parts[1] || "",
        remark: parts.slice(2).join(" "),
        is_held: true,
      };
    })
    .filter((row) => row.stock_code);
}

function paginate<T>(items: T[], page: number, pageSize: number) {
  return items.slice((page - 1) * pageSize, page * pageSize);
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function StockCodeAutocomplete({
  token,
  stockCode,
  onStockCodeChange,
  onStockNameSelect,
  inputId,
  placeholder,
}: {
  token: string | null;
  stockCode: string;
  onStockCodeChange: (code: string) => void;
  onStockNameSelect: (name: string) => void;
  inputId: string;
  placeholder: string;
}) {
  const [suggestions, setSuggestions] = useState<
    { stock_code: string; stock_name?: string | null }[]
  >([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [foundStockName, setFoundStockName] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const searchStock = async () => {
      if (!stockCode.trim() || stockCode.length < 2) {
        setSuggestions([]);
        setShowSuggestions(false);
        setFoundStockName(null);
        return;
      }

      setLoading(true);
      try {
        const result = await api.searchStockByCode(token!, stockCode.trim());
        if (result.stock_name) {
          setSuggestions([result]);
          setShowSuggestions(true);
          setFoundStockName(result.stock_name);
          onStockNameSelect(result.stock_name);
        } else {
          setSuggestions([]);
          setShowSuggestions(false);
          setFoundStockName(null);
        }
      } catch (error) {
        setSuggestions([]);
        setShowSuggestions(false);
        setFoundStockName(null);
      } finally {
        setLoading(false);
      }
    };

    const timeoutId = setTimeout(() => {
      if (!controller.signal.aborted) {
        searchStock();
      }
    }, 300);

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [stockCode, token, onStockNameSelect]);

  const handleSuggestionClick = (suggestion: {
    stock_code: string;
    stock_name?: string | null;
  }) => {
    onStockCodeChange(suggestion.stock_code);
    if (suggestion.stock_name) {
      onStockNameSelect(suggestion.stock_name);
      setFoundStockName(suggestion.stock_name);
    }
    setShowSuggestions(false);
    setSuggestions([]);
  };

  return (
    <div style={{ position: "relative" }}>
      <input
        type="text"
        id={inputId}
        placeholder={placeholder}
        value={stockCode}
        onChange={(e) => onStockCodeChange(e.target.value)}
        onFocus={() => {
          if (suggestions.length > 0) {
            setShowSuggestions(true);
          }
        }}
        onBlur={() => {
          setTimeout(() => setShowSuggestions(false), 200);
        }}
        style={{ width: "100%", padding: "8px", boxSizing: "border-box" }}
      />
      {showSuggestions && suggestions.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            backgroundColor: "white",
            border: "1px solid #ddd",
            borderRadius: "4px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            zIndex: 1000,
            maxHeight: "200px",
            overflowY: "auto",
          }}
        >
          {suggestions.map((suggestion, index) => (
            <div
              key={index}
              onClick={() => handleSuggestionClick(suggestion)}
              style={{
                padding: "8px 12px",
                cursor: "pointer",
                borderBottom:
                  index < suggestions.length - 1 ? "1px solid #eee" : "none",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = "#f5f5f5";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "white";
              }}
            >
              <div style={{ fontWeight: "bold" }}>{suggestion.stock_code}</div>
              {suggestion.stock_name && (
                <div style={{ fontSize: "12px", color: "#666" }}>
                  {suggestion.stock_name}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {loading && (
        <div
          style={{
            position: "absolute",
            right: "8px",
            top: "50%",
            transform: "translateY(-50%)",
            color: "#999",
          }}
        >
          <Loader2 size={16} className="spin" />
        </div>
      )}
      {foundStockName && !loading && (
        <div
          style={{
            position: "absolute",
            right: "8px",
            top: "50%",
            transform: "translateY(-50%)",
            color: "#4CAF50",
            fontSize: "12px",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            maxWidth: "150px",
          }}
          title={foundStockName}
        >
          {foundStockName}
        </div>
      )}
    </div>
  );
}

function StockCard({
  title,
  stock,
  type,
}: {
  title: string;
  stock: import("./types").StockPerformance;
  type: "best" | "worst";
}) {
  const color = type === "best" ? "positive" : "negative";
  const displayValue = type === "best" ? stock.max_gain : stock.max_drawdown;
  return (
    <div className={`stock-card ${type}`}>
      <div className="stock-card-header">
        <span className={`stock-card-title ${color}`}>{title}</span>
        <span className={`stock-card-return ${color}`}>
          {formatPercent(displayValue)}
        </span>
      </div>
      <div className="stock-card-body">
        <div className="stock-card-row">
          <span className="label">股票</span>
          <span className="value">
            {stock.stock_name || stock.stock_code}
            <small>{stock.stock_code}</small>
          </span>
        </div>
        <div className="stock-card-row">
          <span className="label">加入日期</span>
          <span className="value">{stock.added_date || "-"}</span>
        </div>
        <div className="stock-card-row">
          <span className="label">持有天数</span>
          <span className="value">{stock.hold_days}天</span>
        </div>
        <div className="stock-card-row">
          <span className="label">最大回撤</span>
          <span className="value negative">
            {formatPercent(stock.max_drawdown)}
          </span>
        </div>
        <div className="stock-card-row">
          <span className="label">最大收益</span>
          <span className="value positive">
            {formatPercent(stock.max_gain)}
          </span>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ title }: { title: string }) {
  return (
    <div className="empty-state">
      <Circle size={18} />
      <span>{title}</span>
    </div>
  );
}

function Pagination({
  page,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination">
      <span>
        第 {page} / {totalPages} 页，共 {total} 条
      </span>
      <div>
        <button
          className="secondary-button slim"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          type="button"
        >
          上一页
        </button>
        <button
          className="secondary-button slim"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          type="button"
        >
          下一页
        </button>
      </div>
    </div>
  );
}

function AuthView({
  onAuthed,
}: {
  onAuthed: (token: string, user: User) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      if (mode === "register") {
        await api.register(username, password, email);
      }
      const login = await api.login(username, password);
      localStorage.setItem("stock_strategy_token", login.access_token);
      onAuthed(login.access_token, login.user);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand-lockup">
          <div className="brand-mark">
            <LineChartIcon size={24} />
          </div>
          <div>
            <h1>选股策略工作台</h1>
            <p>Strategy Research Console</p>
          </div>
        </div>
        <div className="segmented">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
            type="button"
          >
            登录
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
            type="button"
          >
            注册
          </button>
        </div>
        <form className="form-stack" onSubmit={submit}>
          <label>
            <span>账号</span>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          {mode === "register" && (
            <label>
              <span>邮箱</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
          )}
          <label>
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button className="primary-button" disabled={loading} type="submit">
            {loading ?
              <Loader2 className="spin" size={16} />
            : <ShieldCheck size={16} />}
            {mode === "login" ? "进入工作台" : "创建并登录"}
          </button>
          {message && <div className="notice error">{message}</div>}
        </form>
      </section>
    </main>
  );
}

function App() {
  const [token, setToken] = useState<string | null>(storedToken);
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState<Page>("strategies");
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategyTotal, setStrategyTotal] = useState(0);
  const [strategyPage, setStrategyPage] = useState(1);
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | null>(
    null,
  );
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchPage, setBatchPage] = useState(1);
  const [batchMetrics, setBatchMetrics] = useState<
    Record<number, MetricsResponse>
  >({});
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [batchDetail, setBatchDetail] = useState<BatchDetail | null>(null);
  const [stockPage, setStockPage] = useState(1);
  const [strategyMetrics, setStrategyMetrics] =
    useState<MetricsResponse | null>(null);
  const [selectedBatchMetrics, setSelectedBatchMetrics] =
    useState<MetricsResponse | null>(null);
  const [comparison, setComparison] = useState<BatchComparisonResponse | null>(
    null,
  );
  const [holdReturn, setHoldReturn] = useState<HoldReturnResponse | null>(null);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [metricStart, setMetricStart] = useState(daysAgo(90));
  const [metricEnd, setMetricEnd] = useState(today());
  const [syncDate, setSyncDate] = useState(today());
  const [syncIndexes, setSyncIndexes] = useState("CSI300");
  const [strategyForm, setStrategyForm] = useState({
    name: "",
    benchmark: "CSI300",
    tags: "",
    description: "",
  });
  const [batchForm, setBatchForm] = useState({
    name: "",
    batch_date: today(),
    description: "",
    stocks: [] as NewStock[],
  });
  const [batchStockCodeInput, setBatchStockCodeInput] = useState("");
  const [newBatchStockCodeInput, setNewBatchStockCodeInput] = useState("");
  const [stockInput, setStockInput] = useState("");
  const [userForm, setUserForm] = useState({
    username: "",
    password: "",
    email: "",
    role: "user",
  });
  const [holdParams, setHoldParams] = useState({ n: 0, k: 5 });
  const [maintenanceStatus, setMaintenanceStatus] =
    useState<MaintenanceStatus | null>(null);
  const [logs, setLogs] = useState<AnyLog[]>([]);
  const [logFilter, setLogFilter] = useState<{
    start?: string;
    end?: string;
    source?: string;
    log_type?: string;
    level?: string;
    category?: string;
  }>({ log_type: "all" });
  const [logPage, setLogPage] = useState(1);
  const [logTotal, setLogTotal] = useState(0);

  const [strategyOverview, setStrategyOverview] =
    useState<StrategyOverview | null>(null);
  const [winRateHistory, setWinRateHistory] = useState<WinRateHistory | null>(
    null,
  );
  const [selectedChartView, setSelectedChartView] = useState<
    "best" | "worst" | "winrate"
  >("winrate");
  const [chartData, setChartData] = useState<{ date: string; value: number }[]>(
    [],
  );
  const [bestStockKline, setBestStockKline] = useState<StockKline | null>(null);
  const [worstStockKline, setWorstStockKline] = useState<StockKline | null>(
    null,
  );
  const [klineLoading, setKlineLoading] = useState(false);
  const [selectedStockId, setSelectedStockId] = useState<number | null>(null);
  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null);
  const [stockKline, setStockKline] = useState<StockKline | null>(null);
  const [batchStocksPerformance, setBatchStocksPerformance] = useState<
    BatchStockPerformance[]
  >([]);

  const selectedStrategy = useMemo(
    () =>
      strategies.find((strategy) => strategy.id === selectedStrategyId) || null,
    [strategies, selectedStrategyId],
  );

  const selectedBatch = useMemo(
    () => batches.find((batch) => batch.id === selectedBatchId) || null,
    [batches, selectedBatchId],
  );

  const comparisonData =
    comparison?.batch_comparison.map((item) => ({
      name: item.batch_name,
      return: Number((item.total_return * 100).toFixed(2)),
      drawdown: Number((item.max_drawdown * 100).toFixed(2)),
    })) || [];

  function logout() {
    localStorage.removeItem("stock_strategy_token");
    setToken(null);
    setUser(null);
    setPage("strategies");
  }

  async function guarded(action: () => Promise<void>) {
    if (!token) return;
    setLoading(true);
    setMessage("");
    try {
      await action();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
      } else {
        setMessage(error instanceof Error ? error.message : "请求失败");
      }
    } finally {
      setLoading(false);
    }
  }

  async function refreshStrategies(
    nextPage = strategyPage,
    nextKeyword = keyword,
  ) {
    if (!token) return;
    const response = await api.listStrategies(
      token,
      nextKeyword,
      nextPage,
      strategyPageSize,
    );
    setStrategies(response.items);
    setStrategyTotal(response.total);
  }

  async function openStrategy(strategyId: number) {
    setSelectedStrategyId(strategyId);
    setSelectedBatchId(null);
    setBatchPage(1);
    setPage("strategy-detail");
  }

  async function openBatch(batchId: number) {
    const batch = batches.find((item) => item.id === batchId);
    setSelectedBatchId(batchId);
    setStockPage(1);
    if (batch) setMetricStart(batch.batch_date);
    setPage("batch-detail");
  }

  async function loadStrategyDetail(strategyId = selectedStrategyId) {
    if (!token || !strategyId) return;
    const loadedBatches = await api.listBatches(token, strategyId);
    setBatches(loadedBatches);
    const strategyMetric = await api.getStrategyMetrics(
      token,
      strategyId,
      metricStart,
      metricEnd,
    );
    const compared = await api.compareBatches(token, strategyId);
    const batchMetricEntries = await Promise.all(
      loadedBatches.map(async (batch) => {
        const metric = await api.getBatchMetrics(
          token,
          batch.id,
          batch.batch_date,
          metricEnd,
        );
        return [batch.id, metric] as const;
      }),
    );

    const [overview, winHistory] = await Promise.all([
      api.getStrategyOverview(token, strategyId),
      api.getWinRateHistory(token, strategyId),
    ]);
    setStrategyOverview(overview);
    setWinRateHistory(winHistory);
    updateChartData(overview, winHistory, "winrate");

    setStrategyMetrics(strategyMetric);
    setComparison(compared);
    setBatchMetrics(Object.fromEntries(batchMetricEntries));
  }

  async function loadKlineForStock(
    stockCode: string,
    addedDate: string,
    type: "best" | "worst",
  ) {
    if (!token || !stockCode || !addedDate) return;
    setKlineLoading(true);
    try {
      const startDate = new Date(addedDate);
      startDate.setFullYear(startDate.getFullYear() - 1);
      const start = startDate.toISOString().slice(0, 10);
      const end = today();
      const kline = await api.getStockKline(token, stockCode, start, end);
      if (type === "best") {
        setBestStockKline(kline);
      } else {
        setWorstStockKline(kline);
      }
    } catch (e) {
      console.error("Failed to load kline:", e);
    } finally {
      setKlineLoading(false);
    }
  }

  function updateChartData(
    overview: StrategyOverview | null,
    winHistory: WinRateHistory | null,
    view: "best" | "worst" | "winrate",
  ) {
    if (view === "winrate" && winHistory) {
      setBestStockKline(null);
      setWorstStockKline(null);
      const data = winHistory.dates.map((date, i) => ({
        date: date.slice(5),
        value: Math.round(winHistory.win_rates[i] * 100),
      }));
      setChartData(data);
    } else if (view === "best" && overview?.best_stock) {
      setWorstStockKline(null);
      const stock = overview.best_stock;
      setChartData([
        { date: stock.added_date?.slice(5) || "", value: stock.current_return },
      ]);
      if (stock.added_date) {
        loadKlineForStock(stock.stock_code, stock.added_date, "best");
      }
    } else if (view === "worst" && overview?.worst_stock) {
      setBestStockKline(null);
      const stock = overview.worst_stock;
      setChartData([
        { date: stock.added_date?.slice(5) || "", value: stock.current_return },
      ]);
      if (stock.added_date) {
        loadKlineForStock(stock.stock_code, stock.added_date, "worst");
      }
    } else {
      setChartData([]);
      setBestStockKline(null);
      setWorstStockKline(null);
    }
  }

  async function loadBatchDetail(batchId = selectedBatchId) {
    if (!token || !batchId) return;
    const detail = await api.getBatch(token, batchId);
    const metric = await api.getBatchMetrics(
      token,
      batchId,
      metricStart || detail.batch_date,
      metricEnd,
    );
    const stocksPerformance = await api.getBatchStocksPerformance(
      token,
      batchId,
    );
    setBatchDetail(detail);
    setSelectedBatchMetrics(metric);
    setBatchStocksPerformance(stocksPerformance);
  }

  async function openStockDetail(stockId: number) {
    if (!token || !selectedBatchId) return;
    setSelectedStockId(stockId);
    setPage("stock-detail");
  }

  async function loadStockDetail(stockId = selectedStockId) {
    if (!token || !stockId || !selectedBatchId) return;
    const detail = await api.getStockDetail(token, selectedBatchId, stockId);
    const stock = batchStocksPerformance.find((s) => s.id === stockId);
    if (stock?.added_date) {
      const startDate = new Date(stock.added_date);
      startDate.setFullYear(startDate.getFullYear() - 1);
      const start = startDate.toISOString().slice(0, 10);
      const end = today();
      const kline = await api.getStockKline(
        token,
        stock.stock_code,
        start,
        end,
      );
      setStockKline(kline);
    }
    setStockDetail(detail);
  }

  useEffect(() => {
    if (!token) return;
    guarded(async () => {
      const profile = await api.me(token);
      setUser(profile);
      await refreshStrategies(1);
    });
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const timeout = window.setTimeout(() => {
      setStrategyPage(1);
      guarded(async () => refreshStrategies(1, keyword));
    }, 220);
    return () => window.clearTimeout(timeout);
  }, [keyword]);

  useEffect(() => {
    if (!token) return;
    guarded(async () => refreshStrategies(strategyPage, keyword));
  }, [strategyPage]);

  useEffect(() => {
    if (!token || !selectedStrategyId || page === "strategies") return;
    guarded(async () => loadStrategyDetail(selectedStrategyId));
  }, [selectedStrategyId, metricStart, metricEnd]);

  useEffect(() => {
    if (!token || !selectedBatchId || page !== "batch-detail") return;
    guarded(async () => loadBatchDetail(selectedBatchId));
  }, [selectedBatchId, metricStart, metricEnd]);

  useEffect(() => {
    if (!token || !selectedStockId || page !== "stock-detail") return;
    guarded(async () => loadStockDetail(selectedStockId));
  }, [selectedStockId]);

  useEffect(() => {
    if (!token || user?.role !== "admin") return;
    guarded(async () => {
      await loadMaintenanceData();
      await loadSyncLogs();
    });
  }, [page, logFilter]);

  useEffect(() => {
    setLogPage(1);
  }, [logFilter]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (page === "admin-logs" && maintenanceStatus?.is_running) {
        loadSyncLogs();
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [page, maintenanceStatus]);

  async function createStrategy(event: FormEvent) {
    event.preventDefault();
    await guarded(async () => {
      if (!token) return;
      const created = await api.createStrategy(token, {
        name: strategyForm.name,
        benchmark: strategyForm.benchmark,
        description: strategyForm.description,
        tags: strategyForm.tags
          .split(/[,，\s]+/)
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
      setStrategyForm({
        name: "",
        benchmark: "CSI300",
        tags: "",
        description: "",
      });
      await refreshStrategies(strategyPage, keyword);
      await openStrategy(created.id);
    });
  }

  async function deleteStrategy(strategyId: number, strategyName: string) {
    if (!confirm(`确定要删除策略 "${strategyName}" 吗？此操作不可恢复。`)) {
      return;
    }
    await guarded(async () => {
      if (!token) return;
      await api.deleteStrategy(token, strategyId);
      if (selectedStrategyId === strategyId) {
        setSelectedStrategyId(null);
        setSelectedBatchId(null);
        setPage("strategies");
      }
      await refreshStrategies(strategyPage, keyword);
    });
  }

  async function editStrategy(strategyId: number) {
    const strategy = strategies.find((s) => s.id === strategyId);
    if (!strategy) return;

    const newName = prompt("请输入新的策略名称:", strategy.name);
    if (newName === null) return;
    if (!newName.trim()) {
      alert("策略名称不能为空");
      return;
    }

    const newDescription = prompt(
      "请输入新的策略描述:",
      strategy.description || "",
    );
    if (newDescription === null) return;

    const newBenchmark = prompt(
      "请输入新的基准指数:",
      strategy.benchmark || "CSI300",
    );
    if (newBenchmark === null) return;

    await guarded(async () => {
      if (!token) return;
      await api.updateStrategy(token, strategyId, {
        name: newName.trim(),
        description: newDescription.trim() || undefined,
        benchmark: newBenchmark.trim() || "CSI300",
      });
      await refreshStrategies(strategyPage, keyword);
      if (selectedStrategyId === strategyId) {
        await loadStrategyDetail(strategyId);
      }
    });
  }

  async function deleteBatch(batchId: number, batchName: string) {
    if (!confirm(`确定要删除批次 "${batchName}" 吗？此操作不可恢复。`)) {
      return;
    }
    await guarded(async () => {
      if (!token) return;
      await api.deleteBatch(token, batchId);
      if (selectedBatchId === batchId) {
        setSelectedBatchId(null);
        setPage("strategy-detail");
      }
      if (selectedStrategyId) {
        await loadStrategyDetail(selectedStrategyId);
      }
    });
  }

  async function editBatch(batchId: number) {
    const batch = batches.find((b) => b.id === batchId);
    if (!batch) return;

    const newName = prompt("请输入新的批次名称:", batch.name);
    if (newName === null) return;
    if (!newName.trim()) {
      alert("批次名称不能为空");
      return;
    }

    const newDescription = prompt(
      "请输入新的批次描述:",
      batch.description || "",
    );
    if (newDescription === null) return;

    const newStatus = prompt(
      "请输入新的批次状态 (进行中/已完成/失效):",
      batch.status || "进行中",
    );
    if (newStatus === null) return;

    await guarded(async () => {
      if (!token) return;
      await api.updateBatch(token, batchId, {
        name: newName.trim(),
        description: newDescription.trim() || undefined,
        status: newStatus.trim() || "进行中",
      });
      if (selectedStrategyId) {
        await loadStrategyDetail(selectedStrategyId);
      }
      if (selectedBatchId === batchId) {
        await loadBatchDetail(batchId);
      }
    });
  }

  async function createBatch(event: FormEvent) {
    event.preventDefault();
    await guarded(async () => {
      if (!token || !selectedStrategyId) return;
      const created = await api.createBatch(
        token,
        selectedStrategyId,
        batchForm,
      );
      setBatchForm({
        name: "",
        batch_date: today(),
        description: "",
        stocks: [],
      });
      await loadStrategyDetail(selectedStrategyId);
      await openBatch(created.id);
    });
  }

  async function addStocks(event: FormEvent) {
    event.preventDefault();
    await guarded(async () => {
      if (!token || !selectedBatchId) return;
      const stocks = parseStockRows(stockInput);
      if (!stocks.length) return;
      await api.addStocks(token, selectedBatchId, stocks);
      setStockInput("");
      await loadBatchDetail(selectedBatchId);
    });
  }

  async function toggleStock(
    stock: BatchStock,
    field: "is_traded" | "is_held",
  ) {
    await guarded(async () => {
      if (!token || !selectedBatchId) return;
      await api.updateStock(token, selectedBatchId, stock.id, {
        [field]: !stock[field],
      });
      await loadBatchDetail(selectedBatchId);
    });
  }

  async function syncSelectedBatch() {
    await guarded(async () => {
      if (!token || !batchDetail) return;
      const stockCodes = batchDetail.stocks.map((stock) => stock.stock_code);
      const indexCodes = syncIndexes
        .split(/[,，\s]+/)
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await api.sync(token, {
        trade_date: syncDate,
        stock_codes: stockCodes,
        index_codes: indexCodes,
        recalculate_metrics: true,
      });
      setMessage(
        `同步完成：${response.success_count} 成功，${response.fail_count} 失败，${response.provider || "demo"}`,
      );
      await loadBatchDetail(batchDetail.id);
      if (selectedStrategyId) await loadStrategyDetail(selectedStrategyId);
    });
  }

  async function queryHoldReturn() {
    await guarded(async () => {
      if (!token || !selectedBatchId) return;
      setHoldReturn(
        await api.holdReturn(
          token,
          "batch",
          selectedBatchId,
          holdParams.n,
          holdParams.k,
        ),
      );
    });
  }

  async function createManagedUser(event: FormEvent) {
    event.preventDefault();
    await guarded(async () => {
      if (!token) return;
      await api.createUser(token, userForm);
      setUserForm({ username: "", password: "", email: "", role: "user" });
      setMessage("账户已创建");
    });
  }

  async function loadMaintenanceData() {
    if (!token) return;
    const status = await api.getMaintenanceStatus(token);
    setMaintenanceStatus(status);
  }

  async function loadSyncLogs() {
    if (!token) return;
    const logs = await api.getMaintenanceLogs(token, {
      ...logFilter,
      limit: 1000,
    });
    setLogs(logs);
    setLogTotal(logs.length);
  }

  async function toggleMaintenance() {
    if (!token || !maintenanceStatus) return;
    if (maintenanceStatus.is_running) {
      await guarded(async () => {
        await api.stopMaintenance(token);
        setMessage("后台同步已停止");
        await loadMaintenanceData();
      });
    } else {
      await guarded(async () => {
        await api.startMaintenance(token);
        setMessage("后台同步已启动");
        await loadMaintenanceData();
      });
    }
  }

  if (!token || !user) {
    return (
      <AuthView
        onAuthed={(nextToken, nextUser) => {
          setToken(nextToken);
          setUser(nextUser);
        }}
      />
    );
  }

  const visibleBatches = paginate(batches, batchPage, tablePageSize);
  const visibleStocks = paginate(
    batchDetail?.stocks || [],
    stockPage,
    tablePageSize,
  );
  const activeMetrics = selectedBatchMetrics || strategyMetrics;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup compact">
          <div className="brand-mark">
            <LineChartIcon size={20} />
          </div>
          <div>
            <h1>策略工作台</h1>
            <p>
              {user.username} · {user.role}
            </p>
          </div>
        </div>

        <nav className="page-nav">
          <button
            className={page === "strategies" ? "active" : ""}
            onClick={() => setPage("strategies")}
            type="button"
          >
            <Layers size={16} />
            策略列表
          </button>
          <button
            className={page === "strategy-detail" ? "active" : ""}
            disabled={!selectedStrategyId}
            onClick={() => setPage("strategy-detail")}
            type="button"
          >
            <LineChartIcon size={16} />
            策略详情
          </button>
          <button
            className={page === "batch-detail" ? "active" : ""}
            disabled={!selectedBatchId}
            onClick={() => setPage("batch-detail")}
            type="button"
          >
            <CalendarDays size={16} />
            批次详情
          </button>
          <button
            className={page === "stock-detail" ? "active" : ""}
            disabled={!selectedStockId}
            onClick={() => setPage("stock-detail")}
            type="button"
          >
            <List size={16} />
            个股详情
          </button>
          {user.role === "admin" && (
            <button
              className={page === "admin-logs" ? "active" : ""}
              onClick={() => setPage("admin-logs")}
              type="button"
            >
              <Server size={16} />
              同步日志
            </button>
          )}
        </nav>

        <div className="side-scroll">
          <div className="section-title">
            <span>当前上下文</span>
          </div>
          <div className="context-card">
            <span>策略</span>
            <strong>{selectedStrategy?.name || "未选择"}</strong>
            <small>
              {selectedStrategy?.benchmark ?
                `基准: ${selectedStrategy.benchmark}`
              : ""}
              {selectedStrategy?.tags?.length ?
                ` | 标签: ${selectedStrategy.tags.join(", ")}`
              : ""}
            </small>
          </div>
          <div className="context-card">
            <span>批次</span>
            <strong>{selectedBatch?.name || "未选择"}</strong>
            <small>{selectedBatch?.batch_date || "-"}</small>
          </div>

          {user.role === "admin" && (
            <form className="compact-form" onSubmit={createManagedUser}>
              <div className="section-title">
                <span>创建账户</span>
                <UserPlus size={15} />
              </div>
              <input
                value={userForm.username}
                onChange={(event) =>
                  setUserForm({ ...userForm, username: event.target.value })
                }
                placeholder="账号"
                required
              />
              <input
                type="password"
                value={userForm.password}
                onChange={(event) =>
                  setUserForm({ ...userForm, password: event.target.value })
                }
                placeholder="密码"
                required
              />
              <select
                value={userForm.role}
                onChange={(event) =>
                  setUserForm({ ...userForm, role: event.target.value })
                }
              >
                <option value="user">普通用户</option>
                <option value="vip">VIP</option>
                <option value="admin">管理员</option>
              </select>
              <button className="secondary-button" type="submit">
                <UserPlus size={15} />
                创建
              </button>
            </form>
          )}
        </div>

        <button className="ghost-button logout" onClick={logout} type="button">
          <LogOut size={16} />
          退出
        </button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">
              {page === "strategies" ?
                "Strategies"
              : page === "strategy-detail" ?
                "Strategy Detail"
              : page === "batch-detail" ?
                "Batch Detail"
              : page === "stock-detail" ?
                "Stock Detail"
              : "Admin"}
            </span>
            <h2>
              {page === "strategies" ?
                "策略列表"
              : page === "strategy-detail" ?
                selectedStrategy?.name || "策略详情"
              : page === "batch-detail" ?
                selectedBatch?.name || "批次详情"
              : page === "stock-detail" ?
                stockDetail?.stock_name || stockDetail?.stock_code || "个股详情"
              : "数据同步管理"}
            </h2>
          </div>
          <div className="top-actions">
            {page !== "strategies" && (
              <button
                className="secondary-button"
                onClick={() =>
                  setPage(
                    page === "stock-detail" ? "batch-detail"
                    : page === "batch-detail" ? "strategy-detail"
                    : "strategies",
                  )
                }
                type="button"
              >
                <ArrowLeft size={16} />
                返回
              </button>
            )}
            <button
              className="icon-button"
              onClick={() =>
                guarded(async () => {
                  if (page === "strategies")
                    await refreshStrategies(strategyPage, keyword);
                  if (page === "strategy-detail")
                    await loadStrategyDetail(selectedStrategyId);
                  if (page === "batch-detail")
                    await loadBatchDetail(selectedBatchId);
                  if (page === "stock-detail")
                    await loadStockDetail(selectedStockId);
                })
              }
              title="刷新"
              type="button"
            >
              {loading ?
                <Loader2 className="spin" size={18} />
              : <RefreshCw size={18} />}
            </button>
          </div>
        </header>

        {message && <div className="notice">{message}</div>}

        {page === "strategies" && (
          <section className="page-stack">
            <div className="page-toolbar">
              <div className="search-box page-search">
                <Search size={16} />
                <input
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  placeholder="搜索所有可见策略"
                />
              </div>
              <form className="create-strip" onSubmit={createStrategy}>
                <input
                  value={strategyForm.name}
                  onChange={(event) =>
                    setStrategyForm({
                      ...strategyForm,
                      name: event.target.value,
                    })
                  }
                  placeholder="策略名称"
                  required
                />
                <input
                  value={strategyForm.benchmark}
                  onChange={(event) =>
                    setStrategyForm({
                      ...strategyForm,
                      benchmark: event.target.value,
                    })
                  }
                  placeholder="基准（如 CSI300）"
                  title="基准指数：用于计算超额收益的对标指数，如 CSI300 表示对标沪深300指数"
                />
                <input
                  value={strategyForm.tags}
                  onChange={(event) =>
                    setStrategyForm({
                      ...strategyForm,
                      tags: event.target.value,
                    })
                  }
                  placeholder="标签（如 价值, 成长）"
                  title="标签：用于分类和筛选策略，多个标签用逗号分隔"
                />
                <button className="primary-button" type="submit">
                  <Plus size={16} />
                  新增策略
                </button>
              </form>
            </div>

            <div className="strategy-grid">
              {strategies.map((strategy) => (
                <div className="strategy-card-wrapper" key={strategy.id}>
                  <button
                    className="strategy-card"
                    onClick={() => openStrategy(strategy.id)}
                    type="button"
                  >
                    <div>
                      <span className="pill">
                        {strategy.benchmark || "benchmark"}
                      </span>
                      {strategy.tags?.map((tag) => (
                        <span key={tag} className="tag-pill">
                          {tag}
                        </span>
                      ))}
                      <h3>{strategy.name}</h3>
                      <p>{strategy.description || "暂无描述"}</p>
                    </div>
                    <div className="card-meta">
                      <span>
                        {strategy.owner_name || `owner ${strategy.owner_id}`}
                      </span>
                      <span>{strategy.created_at.slice(0, 10)}</span>
                    </div>
                  </button>
                  {(user.role === "admin" || strategy.owner_id === user.id) && (
                    <div className="card-actions">
                      <button
                        className="edit-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          editStrategy(strategy.id);
                        }}
                        type="button"
                        title="编辑策略"
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        className="delete-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteStrategy(strategy.id, strategy.name);
                        }}
                        type="button"
                        title="删除策略"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {!strategies.length && <EmptyState title="暂无可见策略" />}
            <Pagination
              page={strategyPage}
              total={strategyTotal}
              pageSize={strategyPageSize}
              onChange={setStrategyPage}
            />
          </section>
        )}

        {page === "strategy-detail" && (
          <section className="page-stack">
            <section className="summary-strip">
              <Stat
                label="个股平均收益"
                value={formatPercent(strategyOverview?.average_return)}
                tone={classForReturn(strategyOverview?.average_return)}
              />
              <Stat
                label="个股最大回撤"
                value={formatPercent(strategyOverview?.max_drawdown)}
                tone="negative"
              />
              <Stat
                label="个股最大收益"
                value={formatPercent(strategyOverview?.max_gain)}
                tone="positive"
              />
              <Stat label="可见批次" value={String(batches.length)} />
              <Stat
                label="胜率"
                value={formatPercent(strategyOverview?.win_rate)}
                tone={
                  strategyOverview && strategyOverview.win_rate > 0.5 ?
                    "positive"
                  : "negative"
                }
              />
              <Stat
                label="盈利个股"
                value={`${strategyOverview?.profitable_stocks || 0}/${strategyOverview?.total_stocks || 0}`}
                tone="positive"
              />
              <Stat
                label="亏损个股"
                value={`${strategyOverview?.losing_stocks || 0}/${strategyOverview?.total_stocks || 0}`}
                tone="negative"
              />
            </section>

            {strategyOverview &&
              (strategyOverview.best_stock || strategyOverview.worst_stock) && (
                <section className="summary-strip stock-cards-strip">
                  {strategyOverview.best_stock && (
                    <StockCard
                      title="收益最大"
                      stock={strategyOverview.best_stock}
                      type="best"
                    />
                  )}
                  {strategyOverview.worst_stock && (
                    <StockCard
                      title="亏损最大"
                      stock={strategyOverview.worst_stock}
                      type="worst"
                    />
                  )}
                </section>
              )}

            <div className="panel">
              <div className="panel-head">
                <h3>新增批次</h3>
                <CalendarDays size={17} />
              </div>
              <form className="create-batch-form" onSubmit={createBatch}>
                <div className="batch-header-fields">
                  <input
                    value={batchForm.name}
                    onChange={(event) =>
                      setBatchForm({ ...batchForm, name: event.target.value })
                    }
                    placeholder="批次名称"
                    required
                  />
                  <input
                    type="date"
                    value={batchForm.batch_date}
                    onChange={(event) =>
                      setBatchForm({
                        ...batchForm,
                        batch_date: event.target.value,
                      })
                    }
                    required
                  />
                  <input
                    value={batchForm.description}
                    onChange={(event) =>
                      setBatchForm({
                        ...batchForm,
                        description: event.target.value,
                      })
                    }
                    placeholder="说明"
                  />
                </div>
                <div className="stock-table-wrap">
                  <table className="stock-input-table">
                    <thead>
                      <tr>
                        <th>股票代码 *</th>
                        <th>股票名称</th>
                        <th>备注</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchForm.stocks.map((stock, idx) => (
                        <tr key={idx}>
                          <td>{stock.stock_code}</td>
                          <td>{stock.stock_name || "-"}</td>
                          <td>{stock.remark || "-"}</td>
                          <td>
                            <button
                              type="button"
                              className="icon-button"
                              onClick={() => {
                                const newStocks = batchForm.stocks.filter(
                                  (_, i) => i !== idx,
                                );
                                setBatchForm({
                                  ...batchForm,
                                  stocks: newStocks,
                                });
                              }}
                            >
                              ×
                            </button>
                          </td>
                        </tr>
                      ))}
                      <tr className="stock-add-row">
                        <td>
                          <StockCodeAutocomplete
                            token={token}
                            stockCode={newBatchStockCodeInput}
                            onStockCodeChange={setNewBatchStockCodeInput}
                            onStockNameSelect={(name) => {
                              const nameInput = document.getElementById(
                                "new-stock-name",
                              ) as HTMLInputElement;
                              if (nameInput) {
                                nameInput.value = name;
                              }
                            }}
                            inputId="new-stock-code"
                            placeholder="股票代码 *"
                          />
                        </td>
                        <td>
                          <input placeholder="股票名称" id="new-stock-name" />
                        </td>
                        <td>
                          <input placeholder="备注" id="new-stock-remark" />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="primary-button small"
                            onClick={() => {
                              const codeInput = document.getElementById(
                                "new-stock-code",
                              ) as HTMLInputElement;
                              const nameInput = document.getElementById(
                                "new-stock-name",
                              ) as HTMLInputElement;
                              const remarkInput = document.getElementById(
                                "new-stock-remark",
                              ) as HTMLInputElement;
                              const code = codeInput?.value.trim();
                              if (!code) {
                                alert("请填写股票代码");
                                codeInput?.focus();
                                return;
                              }
                              const newStock: NewStock = {
                                stock_code: code,
                                stock_name: nameInput?.value.trim() || "",
                                remark: remarkInput?.value.trim() || "",
                              };
                              setBatchForm({
                                ...batchForm,
                                stocks: [...batchForm.stocks, newStock],
                              });
                              setNewBatchStockCodeInput("");
                              if (nameInput) nameInput.value = "";
                              if (remarkInput) remarkInput.value = "";
                            }}
                          >
                            添加
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <button className="primary-button" type="submit">
                  <Plus size={16} />
                  创建批次
                </button>
              </form>
            </div>

            <div className="panel chart-panel-flat">
              <div className="panel-head">
                <h3>数据可视化</h3>
                <div className="segmented">
                  <button
                    type="button"
                    className={selectedChartView === "winrate" ? "active" : ""}
                    onClick={() => {
                      setSelectedChartView("winrate");
                      updateChartData(
                        strategyOverview,
                        winRateHistory,
                        "winrate",
                      );
                    }}
                  >
                    胜率变化
                  </button>
                  <button
                    type="button"
                    className={selectedChartView === "best" ? "active" : ""}
                    onClick={() => {
                      setSelectedChartView("best");
                      updateChartData(strategyOverview, winRateHistory, "best");
                    }}
                  >
                    最大收益个股
                  </button>
                  <button
                    type="button"
                    className={selectedChartView === "worst" ? "active" : ""}
                    onClick={() => {
                      setSelectedChartView("worst");
                      updateChartData(
                        strategyOverview,
                        winRateHistory,
                        "worst",
                      );
                    }}
                  >
                    最大亏损个股
                  </button>
                </div>
              </div>
              <div className="chart-box compact-chart">
                {selectedChartView === "winrate" && chartData.length ?
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid stroke="#e2e8e8" strokeDasharray="4 4" />
                      <XAxis dataKey="date" tickLine={false} axisLine={false} />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `${value}%`}
                        width={52}
                      />
                      <Tooltip formatter={(value) => [`${value}%`, "胜率"]} />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#0f766e"
                        strokeWidth={2.5}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                : (
                  selectedChartView === "best" &&
                  bestStockKline &&
                  strategyOverview?.best_stock
                ) ?
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <div style={{ fontSize: "14px", color: "#666" }}>
                      {strategyOverview.best_stock.stock_name} (
                      {strategyOverview.best_stock.stock_code}) - 最大收益{" "}
                      {strategyOverview.best_stock.current_return.toFixed(2)}%
                    </div>
                    {klineLoading ?
                      <div>加载中...</div>
                    : <CandlestickChart
                        kline={bestStockKline}
                        addedDate={strategyOverview.best_stock.added_date || ""}
                      />
                    }
                  </div>
                : (
                  selectedChartView === "worst" &&
                  worstStockKline &&
                  strategyOverview?.worst_stock
                ) ?
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <div style={{ fontSize: "14px", color: "#666" }}>
                      {strategyOverview.worst_stock.stock_name} (
                      {strategyOverview.worst_stock.stock_code}) - 最大亏损{" "}
                      {strategyOverview.worst_stock.current_return.toFixed(2)}%
                    </div>
                    {klineLoading ?
                      <div>加载中...</div>
                    : <CandlestickChart
                        kline={worstStockKline}
                        addedDate={
                          strategyOverview.worst_stock.added_date || ""
                        }
                      />
                    }
                  </div>
                : <EmptyState title="暂无数据" />}
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>所有可见批次</h3>
                <span className="pill">{batches.length} 个</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>批次</th>
                      <th>日期</th>
                      <th>状态</th>
                      <th>累计收益</th>
                      <th>最大回撤</th>
                      <th>最大涨幅</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleBatches.map((batch) => {
                      const metric = batchMetrics[batch.id];
                      return (
                        <tr key={batch.id}>
                          <td>{batch.name}</td>
                          <td>{batch.batch_date}</td>
                          <td>{batch.status || "-"}</td>
                          <td
                            className={classForReturn(
                              metric?.summary.total_return,
                            )}
                          >
                            {formatPercent(metric?.summary.total_return)}
                          </td>
                          <td className="negative">
                            {formatPercent(metric?.summary.max_drawdown)}
                          </td>
                          <td className="positive">
                            {formatPercent(metric?.summary.max_gain)}
                          </td>
                          <td className="right">
                            <button
                              className="secondary-button slim"
                              onClick={() => openBatch(batch.id)}
                              type="button"
                            >
                              查看
                            </button>
                            {(user.role === "admin" ||
                              selectedStrategy?.owner_id === user.id) && (
                              <>
                                <button
                                  className="edit-button slim"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    editBatch(batch.id);
                                  }}
                                  type="button"
                                  title="编辑批次"
                                >
                                  <Edit size={12} />
                                </button>
                                <button
                                  className="delete-button slim"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    deleteBatch(batch.id, batch.name);
                                  }}
                                  type="button"
                                  title="删除批次"
                                >
                                  <Trash2 size={12} />
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {!batches.length && <EmptyState title="暂无批次" />}
              </div>
              <Pagination
                page={batchPage}
                total={batches.length}
                pageSize={tablePageSize}
                onChange={setBatchPage}
              />
            </div>
          </section>
        )}

        {page === "batch-detail" && (
          <section className="page-stack">
            <section className="summary-strip">
              <Stat
                label="批次收益"
                value={
                  batchStocksPerformance.length ?
                    formatPercent(
                      batchStocksPerformance.reduce(
                        (sum, stock) => sum + stock.current_return,
                        0,
                      ) / batchStocksPerformance.length,
                    )
                  : "0.00%"
                }
                tone={
                  batchStocksPerformance.length ?
                    classForReturn(
                      batchStocksPerformance.reduce(
                        (sum, stock) => sum + stock.current_return,
                        0,
                      ) / batchStocksPerformance.length,
                    )
                  : "muted"
                }
              />
              <Stat
                label="个股最大回撤"
                value={
                  batchStocksPerformance.length ?
                    formatPercent(
                      Math.min(
                        ...batchStocksPerformance.map(
                          (stock) => stock.max_drawdown,
                        ),
                      ),
                    )
                  : "0.00%"
                }
                tone="negative"
              />
              <Stat
                label="个股最大收益"
                value={
                  batchStocksPerformance.length ?
                    formatPercent(
                      Math.max(
                        ...batchStocksPerformance.map(
                          (stock) => stock.max_gain,
                        ),
                      ),
                    )
                  : "0.00%"
                }
                tone="positive"
              />
              <Stat
                label="个股数"
                value={String(batchDetail?.stocks.length || 0)}
              />
            </section>

            <div className="panel">
              <div className="panel-head">
                <h3>批次个股导入</h3>
                <span className="pill">
                  {batchDetail?.stocks.length || 0} 只
                </span>
              </div>
              <div className="stock-table-wrap">
                <table className="stock-input-table">
                  <thead>
                    <tr>
                      <th>股票代码 *</th>
                      <th>股票名称</th>
                      <th>备注</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchForm.stocks.map((stock, idx) => (
                      <tr key={idx}>
                        <td>{stock.stock_code}</td>
                        <td>{stock.stock_name || "-"}</td>
                        <td>{stock.remark || "-"}</td>
                        <td>
                          <button
                            type="button"
                            className="icon-button"
                            onClick={() => {
                              const newStocks = batchForm.stocks.filter(
                                (_, i) => i !== idx,
                              );
                              setBatchForm({
                                ...batchForm,
                                stocks: newStocks,
                              });
                            }}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                    <tr className="stock-add-row">
                      <td>
                        <StockCodeAutocomplete
                          token={token}
                          stockCode={batchStockCodeInput}
                          onStockCodeChange={setBatchStockCodeInput}
                          onStockNameSelect={(name) => {
                            const nameInput = document.getElementById(
                              "batch-stock-name",
                            ) as HTMLInputElement;
                            if (nameInput) {
                              nameInput.value = name;
                            }
                          }}
                          inputId="batch-stock-code"
                          placeholder="股票代码 *"
                        />
                      </td>
                      <td>
                        <input placeholder="股票名称" id="batch-stock-name" />
                      </td>
                      <td>
                        <input placeholder="备注" id="batch-stock-remark" />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="primary-button small"
                          onClick={() => {
                            const codeInput = document.getElementById(
                              "batch-stock-code",
                            ) as HTMLInputElement;
                            const nameInput = document.getElementById(
                              "batch-stock-name",
                            ) as HTMLInputElement;
                            const remarkInput = document.getElementById(
                              "batch-stock-remark",
                            ) as HTMLInputElement;
                            const code = codeInput?.value.trim();
                            if (!code) {
                              alert("请填写股票代码");
                              codeInput?.focus();
                              return;
                            }
                            const newStock: NewStock = {
                              stock_code: code,
                              stock_name: nameInput?.value.trim() || "",
                              remark: remarkInput?.value.trim() || "",
                            };
                            setBatchForm({
                              ...batchForm,
                              stocks: [...batchForm.stocks, newStock],
                            });
                            setBatchStockCodeInput("");
                            if (nameInput) nameInput.value = "";
                            if (remarkInput) remarkInput.value = "";
                          }}
                        >
                          添加
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <button
                className="primary-button"
                onClick={async () => {
                  if (!token || !selectedBatchId || !batchForm.stocks.length)
                    return;
                  await guarded(async () => {
                    await api.addStocks(
                      token,
                      selectedBatchId,
                      batchForm.stocks,
                    );
                    setBatchForm({
                      ...batchForm,
                      stocks: [],
                    });
                    await loadBatchDetail(selectedBatchId);
                  });
                }}
                disabled={!selectedBatchId || !batchForm.stocks.length}
                type="button"
              >
                <Plus size={16} />
                批量添加个股
              </button>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>个股收益详情</h3>
                <span className="pill">{batchStocksPerformance.length} 只</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>加入日期</th>
                      <th>加入时收盘价</th>
                      <th>最新价</th>
                      <th>收益率</th>
                      <th>最大回撤</th>
                      <th>最大收益</th>
                      <th>持有天数</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchStocksPerformance.map((stock) => (
                      <tr key={stock.id}>
                        <td className="mono">{stock.stock_code}</td>
                        <td>{stock.stock_name || "-"}</td>
                        <td>{stock.added_date || "-"}</td>
                        <td>
                          {stock.added_close_price ?
                            stock.added_close_price.toFixed(2)
                          : "-"}
                        </td>
                        <td>
                          {stock.current_price ?
                            stock.current_price.toFixed(2)
                          : "-"}
                        </td>
                        <td className={classForReturn(stock.current_return)}>
                          {formatPercent(stock.current_return)}
                        </td>
                        <td className="negative">
                          {formatPercent(stock.max_drawdown)}
                        </td>
                        <td className="positive">
                          {formatPercent(stock.max_gain)}
                        </td>
                        <td>{stock.hold_days}天</td>
                        <td className="right">
                          <button
                            className="secondary-button slim"
                            onClick={() => openStockDetail(stock.id)}
                            type="button"
                          >
                            查看详情
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!batchStocksPerformance.length && (
                  <EmptyState title="暂无个股数据" />
                )}
              </div>
              <Pagination
                page={stockPage}
                total={batchStocksPerformance.length}
                pageSize={tablePageSize}
                onChange={setStockPage}
              />
            </div>
          </section>
        )}

        {page === "stock-detail" && stockDetail && (
          <section className="page-stack">
            <section className="summary-strip">
              <Stat
                label="股票名称"
                value={stockDetail.stock_name || stockDetail.stock_code}
              />
              <Stat label="股票代码" value={stockDetail.stock_code} />
              <Stat label="加入日期" value={stockDetail.added_date || "-"} />
              <Stat
                label="加入时收盘价"
                value={
                  stockDetail.added_close_price ?
                    stockDetail.added_close_price.toFixed(2)
                  : "-"
                }
              />
              <Stat
                label="当前最新价"
                value={
                  stockDetail.current_price ?
                    stockDetail.current_price.toFixed(2)
                  : "-"
                }
              />
              <Stat
                label="当前收益率"
                value={formatPercent(stockDetail.current_return)}
                tone={classForReturn(stockDetail.current_return)}
              />
              <Stat
                label="最大回撤"
                value={formatPercent(stockDetail.max_drawdown)}
                tone="negative"
              />
              <Stat
                label="最大收益"
                value={formatPercent(stockDetail.max_gain)}
                tone="positive"
              />
              <Stat label="持有天数" value={`${stockDetail.hold_days}天`} />
            </section>

            <div className="panel chart-panel-flat">
              <div className="panel-head">
                <h3>K线图</h3>
                <span className="pill">
                  加入日期: {stockDetail.added_date || "-"}
                </span>
              </div>
              <div className="chart-box">
                {stockKline ?
                  <CandlestickChart
                    kline={stockKline}
                    addedDate={stockDetail.added_date || ""}
                  />
                : <EmptyState title="暂无K线数据" />}
              </div>
            </div>

            <div className="panel chart-panel-flat">
              <div className="panel-head">
                <h3>收益率变化</h3>
              </div>
              <div className="chart-box compact-chart">
                {(
                  stockDetail.return_history &&
                  stockDetail.return_history.length > 0
                ) ?
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={stockDetail.return_history.map((h) => ({
                        date: h.date.slice(5),
                        value: (h.return * 100).toFixed(2),
                      }))}
                    >
                      <CartesianGrid stroke="#e2e8e8" strokeDasharray="4 4" />
                      <XAxis dataKey="date" tickLine={false} axisLine={false} />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `${value}%`}
                        width={52}
                      />
                      <Tooltip formatter={(value) => [`${value}%`, "收益率"]} />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#0f766e"
                        strokeWidth={2.5}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                : <EmptyState title="暂无收益率数据" />}
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>收益率历史数据</h3>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>收益率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(
                      stockDetail.return_history &&
                      stockDetail.return_history.length > 0
                    ) ?
                      stockDetail.return_history.map((history, idx) => (
                        <tr key={idx}>
                          <td>{history.date}</td>
                          <td className={classForReturn(history.return)}>
                            {formatPercent(history.return)}
                          </td>
                        </tr>
                      ))
                    : <tr>
                        <td colSpan={2}>
                          <EmptyState title="暂无历史数据" />
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {page === "admin-logs" && user.role === "admin" && (
          <section className="page-stack">
            <div className="panel">
              <div className="panel-head">
                <h3>后台同步服务</h3>
                <Server size={17} />
              </div>
              <div className="service-status">
                <div className="status-indicator">
                  <span
                    className={`status-dot ${maintenanceStatus?.is_running ? "running" : "stopped"}`}
                  />
                  <span>
                    {maintenanceStatus?.is_running ? "运行中" : "已停止"}
                  </span>
                </div>
                {maintenanceStatus?.last_error && (
                  <div className="error-message">
                    上次错误: {maintenanceStatus.last_error}
                  </div>
                )}
                <button
                  className={
                    maintenanceStatus?.is_running ?
                      "secondary-button danger"
                    : "primary-button"
                  }
                  onClick={toggleMaintenance}
                  disabled={loading}
                  type="button"
                >
                  {loading ?
                    <Loader2 className="spin" size={16} />
                  : null}
                  {maintenanceStatus?.is_running ? "停止同步" : "启动同步"}
                </button>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>日志系统</h3>
                <div className="log-filters">
                  <select
                    value={logFilter.log_type || "all"}
                    onChange={(e) =>
                      setLogFilter({
                        ...logFilter,
                        log_type: e.target.value || undefined,
                      })
                    }
                  >
                    <option value="all">全部日志</option>
                    <option value="sync">同步日志</option>
                    <option value="app">应用日志</option>
                  </select>
                  {logFilter.log_type === "app" && (
                    <select
                      value={logFilter.level || ""}
                      onChange={(e) =>
                        setLogFilter({
                          ...logFilter,
                          level: e.target.value || undefined,
                        })
                      }
                    >
                      <option value="">全部级别</option>
                      <option value="info">信息</option>
                      <option value="warning">警告</option>
                      <option value="error">错误</option>
                    </select>
                  )}
                  {logFilter.log_type === "app" && (
                    <select
                      value={logFilter.category || ""}
                      onChange={(e) =>
                        setLogFilter({
                          ...logFilter,
                          category: e.target.value || undefined,
                        })
                      }
                    >
                      <option value="">全部分类</option>
                      <option value="sync">同步</option>
                      <option value="auth">认证</option>
                      <option value="api">API</option>
                      <option value="general">通用</option>
                    </select>
                  )}
                  <select
                    value={logFilter.source || ""}
                    onChange={(e) =>
                      setLogFilter({
                        ...logFilter,
                        source: e.target.value || undefined,
                      })
                    }
                  >
                    <option value="">全部来源</option>
                    <option value="maintenance">后台维护</option>
                    <option value="manual">手动同步</option>
                  </select>
                  <input
                    type="date"
                    value={logFilter.start || ""}
                    onChange={(e) =>
                      setLogFilter({
                        ...logFilter,
                        start: e.target.value || undefined,
                      })
                    }
                    placeholder="开始日期"
                  />
                  <input
                    type="date"
                    value={logFilter.end || ""}
                    onChange={(e) =>
                      setLogFilter({
                        ...logFilter,
                        end: e.target.value || undefined,
                      })
                    }
                    placeholder="结束日期"
                  />
                  <button
                    className="secondary-button"
                    onClick={() =>
                      guarded(async () => {
                        await loadMaintenanceData();
                        await loadSyncLogs();
                      })
                    }
                    disabled={loading}
                    type="button"
                  >
                    {loading ?
                      <Loader2 className="spin" size={16} />
                    : <RefreshCw size={16} />}
                    刷新
                  </button>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>类型</th>
                      <th>来源</th>
                      <th>内容</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginate(logs, logPage, logPageSize).map((log, idx) => {
                      const isSyncLog = "status" in log;
                      return (
                        <tr key={idx}>
                          <td>{log.created_at?.slice(0, 19)}</td>
                          <td>
                            {isSyncLog ?
                              <span className={`status-badge ${log.status}`}>
                                {log.status === "success" ?
                                  "同步成功"
                                : "同步失败"}
                              </span>
                            : <span
                                className={`level-badge ${(log as AppLog).level}`}
                              >
                                {(log as AppLog).level.toUpperCase()}
                              </span>
                            }
                          </td>
                          <td>
                            <span
                              className={`source-badge ${log.source || "manual"}`}
                            >
                              {log.source === "maintenance" ?
                                "后台"
                              : log.source === "manual" ?
                                "手动"
                              : log.source || "-"}
                            </span>
                          </td>
                          <td className="log-message">
                            {isSyncLog ?
                              <>
                                {log.success_count > 0 && (
                                  <span className="positive">
                                    {log.success_count}成功
                                  </span>
                                )}
                                {log.success_count > 0 &&
                                  log.fail_count > 0 &&
                                  " / "}
                                {log.fail_count > 0 && (
                                  <span className="negative">
                                    {log.fail_count}失败
                                  </span>
                                )}
                                {log.error_detail && (
                                  <span className="error-detail">
                                    {" "}
                                    {log.error_detail}
                                  </span>
                                )}
                              </>
                            : <span>{(log as AppLog).message}</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {!logs.length && <EmptyState title="暂无日志" />}
              </div>
              <Pagination
                page={logPage}
                total={logTotal}
                pageSize={logPageSize}
                onChange={setLogPage}
              />
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
