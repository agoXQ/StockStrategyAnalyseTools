from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str
    token_type: str
    token: Optional[str] = None
    user: Optional["UserOut"] = None

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    role: str = Field(default="user", regex="^(admin|vip|user)$")

class UserCreate(UserBase):
    password: str

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: Optional[str] = Field(default=None, regex="^(admin|vip|user)$")

class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = Field(default=None, regex="^(admin|vip|user)$")
    status: Optional[str] = Field(default=None, regex="^(active|disabled)$")
    password: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    status: Optional[str] = None

    class Config:
        orm_mode = True

class StrategyBase(BaseModel):
    name: str
    description: Optional[str] = None
    benchmark: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = "active"

class StrategyCreate(StrategyBase):
    pass

class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    benchmark: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None

class StrategyOut(StrategyBase):
    id: int
    owner_id: int
    owner_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class StrategyListResponse(BaseModel):
    total: int
    items: List[StrategyOut]

class BatchBase(BaseModel):
    name: str
    batch_date: date
    description: Optional[str] = None
    status: Optional[str] = "进行中"

class BatchStockCreate(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    remark: Optional[str] = None
    added_date: Optional[date] = None
    is_traded: bool = False
    is_held: bool = False


class BatchCreate(BatchBase):
    stocks: List[BatchStockCreate] = []

    def __init__(self, **data):
        super().__init__(**data)


class BatchUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class BatchOut(BatchBase):
    id: int
    strategy_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class BatchStockUpdate(BaseModel):
    stock_name: Optional[str] = None
    remark: Optional[str] = None
    added_date: Optional[date] = None
    is_traded: Optional[bool] = None
    is_held: Optional[bool] = None

class BatchStockBulkCreate(BaseModel):
    stocks: List[BatchStockCreate]

class BatchStockOut(BaseModel):
    id: int
    batch_id: int
    stock_code: str
    stock_name: Optional[str]
    remark: Optional[str]
    added_date: Optional[date] = None
    is_traded: bool = False
    is_held: bool = False
    added_at: datetime

    class Config:
        orm_mode = True

class BatchDetailOut(BatchOut):
    stocks: List[BatchStockOut] = Field(default_factory=list)

class SyncRequest(BaseModel):
    trade_date: Optional[date] = None
    stock_codes: Optional[List[str]] = None
    index_codes: Optional[List[str]] = None
    recalculate_metrics: bool = True

class SyncStatusOut(BaseModel):
    last_sync_date: Optional[date]
    success_count: int
    fail_count: int
    errors: List[str] = Field(default_factory=list)

class SyncHistoryItem(BaseModel):
    log_type: Optional[str] = "sync"
    level: Optional[str] = "info"
    trade_date: Optional[date] = None
    status: str
    success_count: int
    fail_count: int
    error_detail: Optional[str]
    source: Optional[str] = "manual"
    message: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class AppLogItem(BaseModel):
    id: int
    level: str
    category: str
    message: str
    details: Optional[Any] = None
    source: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True

class StockPerformance(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    batch_id: int
    batch_name: Optional[str] = None
    added_date: Optional[date] = None
    hold_days: int
    current_return: float
    max_drawdown: float
    max_gain: float
    is_profitable: bool

    class Config:
        orm_mode = True

class StrategyOverview(BaseModel):
    best_stock: Optional[StockPerformance] = None
    worst_stock: Optional[StockPerformance] = None
    win_rate: float
    total_stocks: int
    profitable_stocks: int
    losing_stocks: int
    average_return: float = 0.0
    max_drawdown: float = 0.0
    max_gain: float = 0.0

class MetricsSummary(BaseModel):
    total_return: float
    max_drawdown: float
    max_gain: float

class MetricsPoint(BaseModel):
    trade_date: date
    daily_return: float
    cumulative_return: float

class MetricsResponse(BaseModel):
    strategy_id: Optional[int] = None
    batch_id: Optional[int] = None
    stock_code: Optional[str] = None
    start: date
    end: date
    daily: List[MetricsPoint]
    summary: MetricsSummary

class HoldReturnResponse(BaseModel):
    scope: str
    id: int
    n: int
    k: int
    hold_return: Optional[float]
    status: str

class BatchComparisonItem(BaseModel):
    batch_id: int
    batch_name: str
    total_return: float
    max_drawdown: float
    max_gain: float

class BatchComparisonResponse(BaseModel):
    strategy_id: int
    trade_date: Optional[date]
    batch_comparison: List[BatchComparisonItem]

class BatchStockPerformance(BaseModel):
    id: int
    stock_code: str
    stock_name: Optional[str] = None
    added_date: Optional[date] = None
    added_close_price: Optional[float] = None
    current_price: Optional[float] = None
    current_return: float
    max_drawdown: float
    max_gain: float
    hold_days: int
    remark: Optional[str] = None
    is_traded: bool = False
    is_held: bool = False

    class Config:
        orm_mode = True

class StockDetail(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    batch_id: int
    batch_name: Optional[str] = None
    added_date: Optional[date] = None
    added_close_price: Optional[float] = None
    current_price: Optional[float] = None
    current_return: float
    max_drawdown: float
    max_gain: float
    hold_days: int
    return_history: Optional[List[dict]] = None

    class Config:
        orm_mode = True


Token.update_forward_refs()