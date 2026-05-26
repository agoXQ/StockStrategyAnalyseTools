from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, BigInteger, String, Date, DateTime, Text, ForeignKey, Numeric, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    email = Column(String(256), nullable=True)
    role = Column(String(16), nullable=False, default="user")
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    strategies = relationship("Strategy", back_populates="owner")

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_status", "status"),
        {"sqlite_autoincrement": True},
    )

class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    benchmark = Column(String(64), nullable=True)
    tags = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="strategies")
    batches = relationship("Batch", back_populates="strategy", cascade="all, delete-orphan")

    @property
    def owner_name(self):
        return self.owner.username if self.owner else None

    __table_args__ = (
        Index("idx_strategies_owner", "owner_id"),
        Index("idx_strategies_status", "status"),
        Index("idx_strategies_name", "name"),
    )

class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    name = Column(String(256), nullable=False)
    batch_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="进行中")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    strategy = relationship("Strategy", back_populates="batches")
    stocks = relationship("BatchStock", back_populates="batch", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_batches_strategy", "strategy_id"),
        Index("idx_batches_batch_date", "batch_date"),
        Index("idx_batches_status", "status"),
    )

class BatchStock(Base):
    __tablename__ = "batch_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    stock_code = Column(String(32), nullable=False)
    stock_name = Column(String(128), nullable=True)
    added_date = Column(Date, nullable=True)
    is_traded = Column(Boolean, nullable=False, default=False)
    is_held = Column(Boolean, nullable=False, default=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    remark = Column(Text, nullable=True)

    batch = relationship("Batch", back_populates="stocks")

    __table_args__ = (
        Index("idx_batch_stocks_batch", "batch_id"),
        Index("idx_batch_stocks_code", "stock_code"),
        UniqueConstraint("batch_id", "stock_code", name="uniq_batch_stock_code"),
    )

class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    symbol = Column(String(32), nullable=False)
    market_type = Column(String(16), nullable=False)
    close_price = Column(Numeric(18, 6), nullable=False)
    open_price = Column(Numeric(18, 6), nullable=True)
    high_price = Column(Numeric(18, 6), nullable=True)
    low_price = Column(Numeric(18, 6), nullable=True)
    volume = Column(BigInteger, nullable=True)
    source = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("trade_date", "symbol", name="uniq_market_data_date_symbol"),
        Index("idx_market_data_symbol", "symbol"),
        Index("idx_market_data_trade_date", "trade_date"),
        Index("idx_market_data_market_type", "market_type"),
        {"sqlite_autoincrement": True},
    )

class StockBasicInfo(Base):
    __tablename__ = "stock_basic_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(32), unique=True, nullable=False, index=True)
    stock_name = Column(String(128), nullable=True)
    industry = Column(String(128), nullable=True)
    market = Column(String(32), nullable=True)  # SH, SZ, BJ等
    list_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_stock_basic_info_code", "stock_code"),
        Index("idx_stock_basic_info_name", "stock_name"),
        {"sqlite_autoincrement": True},
    )

class StrategyMetric(Base):
    __tablename__ = "strategy_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    stock_code = Column(String(32), nullable=True)
    metric_date = Column(Date, nullable=False)
    daily_return = Column(Numeric(18, 6), nullable=True)
    cumulative_return = Column(Numeric(18, 6), nullable=True)
    max_drawdown = Column(Numeric(18, 6), nullable=True)
    max_gain = Column(Numeric(18, 6), nullable=True)
    trade_days_since_entry = Column(Integer, nullable=True)
    hold_return_n_k = Column(Numeric(18, 6), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_strategy_metrics_strategy_date", "strategy_id", "metric_date"),
        Index("idx_strategy_metrics_batch_date", "batch_id", "metric_date"),
        Index("idx_strategy_metrics_stock_date", "stock_code", "metric_date"),
        Index("idx_strategy_metrics_scope", "strategy_id", "batch_id", "stock_code", "metric_date"),
    )

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_type = Column(String(32), nullable=False, default="sync", index=True)
    level = Column(String(16), nullable=False, default="info", index=True)
    trade_date = Column(Date, nullable=True, index=True)
    status = Column(String(32), nullable=False)
    success_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)
    error_detail = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, default="manual")
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_sync_logs_type_date", "log_type", "created_at"),
        Index("idx_sync_logs_source", "source"),
    )


class AppLog(Base):
    __tablename__ = "app_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(16), nullable=False, default="info", index=True)
    category = Column(String(64), nullable=False, default="general", index=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    source = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_app_logs_category_date", "category", "created_at"),
    )