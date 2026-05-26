from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models
from app.auth import get_password_hash


def log_info(db: Session, message: str, category: str = "general", source: Optional[str] = None, details: Optional[dict] = None) -> models.AppLog:
    return create_app_log(db, level="info", message=message, category=category, source=source, details=details)


def log_warning(db: Session, message: str, category: str = "general", source: Optional[str] = None, details: Optional[dict] = None) -> models.AppLog:
    return create_app_log(db, level="warning", message=message, category=category, source=source, details=details)


def log_error(db: Session, message: str, category: str = "general", source: Optional[str] = None, details: Optional[dict] = None) -> models.AppLog:
    return create_app_log(db, level="error", message=message, category=category, source=source, details=details)

# User CRUD

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def count_users(db: Session) -> int:
    return db.query(models.User).count()


def list_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    return db.query(models.User).order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()


def create_user(db: Session, username: str, password: str, email: Optional[str], role: str) -> models.User:
    user = models.User(username=username, password_hash=get_password_hash(password), email=email, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: models.User, updates: dict) -> models.User:
    password = updates.pop("password", None)
    if password:
        user.password_hash = get_password_hash(password)
    for field, value in updates.items():
        if value is not None:
            setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Strategy CRUD

def create_strategy(db: Session, owner_id: int, strategy_data: dict) -> models.Strategy:
    strategy = models.Strategy(owner_id=owner_id, **strategy_data)
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def get_strategy(db: Session, strategy_id: int) -> Optional[models.Strategy]:
    return db.query(models.Strategy).filter(models.Strategy.id == strategy_id).first()


def list_strategies(
    db: Session,
    owner_id: Optional[int] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[int, List[models.Strategy]]:
    query = db.query(models.Strategy)
    if owner_id is not None:
        query = query.filter(models.Strategy.owner_id == owner_id)
    if keyword:
        like_keyword = f"%{keyword}%"
        query = query.filter(
            or_(
                models.Strategy.name.ilike(like_keyword),
                models.Strategy.description.ilike(like_keyword),
            )
        )
    total = query.count()
    items = query.order_by(models.Strategy.created_at.desc()).offset(skip).limit(limit).all()
    return total, items


def update_strategy(db: Session, strategy: models.Strategy, updates: dict) -> models.Strategy:
    for field, value in updates.items():
        if value is not None:
            setattr(strategy, field, value)
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def delete_strategy(db: Session, strategy: models.Strategy):
    db.delete(strategy)
    db.commit()

# Batch CRUD

def create_batch(db: Session, strategy_id: int, batch_data: dict) -> models.Batch:
    stocks_data = batch_data.pop("stocks", []) or []
    batch = models.Batch(strategy_id=strategy_id, **batch_data)
    db.add(batch)
    db.flush()
    for stock_data in stocks_data:
        stock_code = stock_data.get("stock_code") or getattr(stock_data, "stock_code", None) if isinstance(stock_data, dict) else getattr(stock_data, "stock_code", None)
        if not stock_code:
            continue
        stock_name = stock_data.get("stock_name") if isinstance(stock_data, dict) else getattr(stock_data, "stock_name", None)
        remark = stock_data.get("remark") if isinstance(stock_data, dict) else getattr(stock_data, "remark", None)
        stock = models.BatchStock(
            batch_id=batch.id,
            stock_code=stock_code,
            stock_name=stock_name,
            remark=remark,
            added_date=batch.batch_date,
        )
        db.add(stock)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: int) -> Optional[models.Batch]:
    return db.query(models.Batch).filter(models.Batch.id == batch_id).first()


def list_batches(
    db: Session,
    strategy_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[models.Batch]:
    query = db.query(models.Batch)
    if strategy_id is not None:
        query = query.filter(models.Batch.strategy_id == strategy_id)
    if status is not None:
        query = query.filter(models.Batch.status == status)
    if start_date is not None:
        query = query.filter(models.Batch.batch_date >= start_date)
    if end_date is not None:
        query = query.filter(models.Batch.batch_date <= end_date)
    return query.order_by(models.Batch.batch_date.desc()).all()


def update_batch(db: Session, batch: models.Batch, updates: dict) -> models.Batch:
    for field, value in updates.items():
        if value is not None:
            setattr(batch, field, value)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def delete_batch(db: Session, batch: models.Batch):
    db.delete(batch)
    db.commit()

# Batch stock CRUD

def create_batch_stock(db: Session, batch_id: int, stock_data: dict) -> models.BatchStock:
    stock = models.BatchStock(batch_id=batch_id, **stock_data)
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def list_batch_stocks(db: Session, batch_id: int) -> List[models.BatchStock]:
    return db.query(models.BatchStock).filter(models.BatchStock.batch_id == batch_id).order_by(models.BatchStock.added_at).all()


def get_batch_stock(db: Session, stock_id: int) -> Optional[models.BatchStock]:
    return db.query(models.BatchStock).filter(models.BatchStock.id == stock_id).first()


def get_batch_stock_by_code(db: Session, batch_id: int, stock_code: str) -> Optional[models.BatchStock]:
    return db.query(models.BatchStock).filter(models.BatchStock.batch_id == batch_id, models.BatchStock.stock_code == stock_code).first()


def delete_batch_stock(db: Session, stock: models.BatchStock):
    db.delete(stock)
    db.commit()


def update_batch_stock(db: Session, stock: models.BatchStock, updates: dict) -> models.BatchStock:
    for field, value in updates.items():
        if value is not None:
            setattr(stock, field, value)
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock

# Market data and sync

def upsert_market_data(db: Session, trade_date: date, symbol: str, market_type: str, close_price: float, open_price: Optional[float] = None, high_price: Optional[float] = None, low_price: Optional[float] = None, volume: Optional[int] = None, source: Optional[str] = None) -> models.MarketData:
    record = db.query(models.MarketData).filter(models.MarketData.trade_date == trade_date, models.MarketData.symbol == symbol).first()
    if record is None:
        record = models.MarketData(
            trade_date=trade_date,
            symbol=symbol,
            market_type=market_type,
            close_price=close_price,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            volume=volume,
            source=source,
        )
        db.add(record)
    else:
        record.close_price = close_price
        record.open_price = open_price
        record.high_price = high_price
        record.low_price = low_price
        record.volume = volume
        record.source = source
    db.commit()
    db.refresh(record)
    return record


def get_all_batch_stock_codes(db: Session) -> List[str]:
    """获取所有批次中的唯一股票代码"""
    result = db.query(models.BatchStock.stock_code).distinct().all()
    return [r[0] for r in result]


def search_stock_by_code(db: Session, stock_code: str) -> Optional[dict]:
    """根据股票代码搜索股票信息，返回股票代码和名称"""
    stock = db.query(models.StockBasicInfo).filter(
        models.StockBasicInfo.stock_code == stock_code
    ).first()
    if stock:
        return {
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name
        }
    return None


def upsert_stock_basic_info(db: Session, stock_code: str, stock_name: str = None, industry: str = None, market: str = None, list_date: date = None) -> models.StockBasicInfo:
    """更新或插入股票基本信息"""
    stock = db.query(models.StockBasicInfo).filter(
        models.StockBasicInfo.stock_code == stock_code
    ).first()
    
    if stock:
        if stock_name and stock.stock_name != stock_name:
            stock.stock_name = stock_name
        if industry and stock.industry != industry:
            stock.industry = industry
        if market and stock.market != market:
            stock.market = market
        if list_date and stock.list_date != list_date:
            stock.list_date = list_date
        stock.updated_at = datetime.utcnow()
    else:
        stock = models.StockBasicInfo(
            stock_code=stock_code,
            stock_name=stock_name,
            industry=industry,
            market=market,
            list_date=list_date
        )
        db.add(stock)
    
    db.commit()
    db.refresh(stock)
    return stock


def sync_stock_basic_info_from_market_data(db: Session) -> dict:
    """从market_data表同步股票基本信息到stock_basic_info表"""
    result = {
        "total_processed": 0,
        "new_stocks": 0,
        "updated_stocks": 0,
        "errors": []
    }
    
    try:
        from sqlalchemy import distinct
        
        stock_codes = db.query(distinct(models.MarketData.symbol)).filter(
            models.MarketData.market_type == "stock"
        ).all()
        
        for (stock_code,) in stock_codes:
            result["total_processed"] += 1
            try:
                latest_data = db.query(models.MarketData).filter(
                    models.MarketData.symbol == stock_code,
                    models.MarketData.market_type == "stock"
                ).order_by(models.MarketData.trade_date.desc()).first()
                
                if latest_data:
                    if stock_code.startswith("6"):
                        market = "SH"
                    elif stock_code.startswith(("0", "3")):
                        market = "SZ"
                    elif stock_code.startswith("8"):
                        market = "BJ"
                    else:
                        market = "UNKNOWN"
                    
                    upsert_stock_basic_info(
                        db=db,
                        stock_code=stock_code,
                        market=market
                    )
                    
                    existing_stock = db.query(models.StockBasicInfo).filter(
                        models.StockBasicInfo.stock_code == stock_code
                    ).first()
                    if existing_stock and existing_stock.created_at <= datetime.utcnow():
                        result["updated_stocks"] += 1
                    else:
                        result["new_stocks"] += 1
                        
            except Exception as e:
                result["errors"].append(f"Stock {stock_code}: {str(e)}")
                
    except Exception as e:
        result["errors"].append(f"Sync process error: {str(e)}")
        
    return result


def get_market_data_count_for_stock(db: Session, stock_code: str) -> int:
    """获取某只股票已存在的市场数据条数"""
    return db.query(models.MarketData).filter(models.MarketData.symbol == stock_code).count()


def get_market_data_count_by_date(db: Session, trade_date: date) -> int:
    """获取指定日期的市场数据条数"""
    return db.query(models.MarketData).filter(models.MarketData.trade_date == trade_date).count()


def get_market_data_count_from_date(db: Session, stock_code: str, from_date: date) -> int:
    """获取某只股票从指定日期开始的市场数据条数"""
    return db.query(models.MarketData).filter(
        models.MarketData.symbol == stock_code,
        models.MarketData.trade_date >= from_date,
    ).count()


def list_sync_logs(db: Session, skip: int = 0, limit: int = 20, start: Optional[date] = None, end: Optional[date] = None, source: Optional[str] = None, log_type: Optional[str] = None) -> List[models.SyncLog]:
    query = db.query(models.SyncLog)
    if start is not None:
        query = query.filter(models.SyncLog.created_at >= datetime.combine(start, datetime.min.time()))
    if end is not None:
        query = query.filter(models.SyncLog.created_at <= datetime.combine(end, datetime.max.time()))
    if source is not None:
        query = query.filter(models.SyncLog.source == source)
    if log_type is not None:
        query = query.filter(models.SyncLog.log_type == log_type)
    return query.order_by(models.SyncLog.created_at.desc()).offset(skip).limit(limit).all()


def create_sync_log(db: Session, trade_date: Optional[date], status: str, success_count: int, fail_count: int, error_detail: Optional[str] = None, source: str = "manual", log_type: str = "sync", level: str = "info", message: Optional[str] = None) -> models.SyncLog:
    log = models.SyncLog(
        log_type=log_type,
        level=level,
        trade_date=trade_date,
        status=status,
        success_count=success_count,
        fail_count=fail_count,
        error_detail=error_detail,
        source=source,
        message=message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def create_app_log(db: Session, level: str, message: str, category: str = "general", details: Optional[dict] = None, source: Optional[str] = None) -> models.AppLog:
    log = models.AppLog(
        level=level,
        category=category,
        message=message,
        details=details,
        source=source,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_app_logs(db: Session, skip: int = 0, limit: int = 50, level: Optional[str] = None, category: Optional[str] = None, source: Optional[str] = None, start: Optional[date] = None, end: Optional[date] = None) -> List[models.AppLog]:
    query = db.query(models.AppLog)
    if level is not None:
        query = query.filter(models.AppLog.level == level)
    if category is not None:
        query = query.filter(models.AppLog.category == category)
    if source is not None:
        query = query.filter(models.AppLog.source == source)
    if start is not None:
        query = query.filter(models.AppLog.created_at >= datetime.combine(start, datetime.min.time()))
    if end is not None:
        query = query.filter(models.AppLog.created_at <= datetime.combine(end, datetime.max.time()))
    return query.order_by(models.AppLog.created_at.desc()).offset(skip).limit(limit).all()

# Metrics helpers

def get_strategy_metrics(db: Session, strategy_id: int, start: date, end: date) -> List[models.StrategyMetric]:
    return db.query(models.StrategyMetric).filter(models.StrategyMetric.strategy_id == strategy_id, models.StrategyMetric.batch_id.is_(None), models.StrategyMetric.stock_code.is_(None), models.StrategyMetric.metric_date >= start, models.StrategyMetric.metric_date <= end).order_by(models.StrategyMetric.metric_date).all()


def get_batch_metrics(db: Session, batch_id: int, start: date, end: date) -> List[models.StrategyMetric]:
    return db.query(models.StrategyMetric).filter(models.StrategyMetric.batch_id == batch_id, models.StrategyMetric.stock_code.is_(None), models.StrategyMetric.metric_date >= start, models.StrategyMetric.metric_date <= end).order_by(models.StrategyMetric.metric_date).all()


def get_batch_stock_based_metrics(db: Session, batch_id: int) -> dict:
    """基于批次中个股计算批次指标"""
    performances = get_batch_stocks_performance(db, batch_id)
    
    if not performances:
        return {
            "average_return": 0.0,
            "max_drawdown": 0.0,
            "max_gain": 0.0,
        }
    
    average_return = sum(p["current_return"] for p in performances) / len(performances) if performances else 0.0
    max_drawdown = min(p["max_drawdown"] for p in performances) if performances else 0.0
    max_gain = max(p["max_gain"] for p in performances) if performances else 0.0
    
    return {
        "average_return": average_return,
        "max_drawdown": max_drawdown,
        "max_gain": max_gain,
    }


def get_stock_metrics(db: Session, stock_code: str, start: date, end: date, batch_id: Optional[int] = None) -> List[models.StrategyMetric]:
    query = db.query(models.StrategyMetric).filter(models.StrategyMetric.stock_code == stock_code, models.StrategyMetric.metric_date >= start, models.StrategyMetric.metric_date <= end)
    if batch_id is not None:
        query = query.filter(models.StrategyMetric.batch_id == batch_id)
    return query.order_by(models.StrategyMetric.metric_date).all()


def get_earliest_batch_stock_date(db: Session) -> Optional[date]:
    return db.query(func.min(models.BatchStock.added_date)).scalar()


def get_existing_market_data_dates(db: Session, start: date, end: date) -> List[date]:
    results = (
        db.query(models.MarketData.trade_date)
        .filter(
            models.MarketData.trade_date >= start,
            models.MarketData.trade_date <= end,
        )
        .distinct()
        .all()
    )
    return [r[0] for r in results]


def upsert_market_data_batch(db: Session, records: List[dict]) -> int:
    count = 0
    for record_data in records:
        trade_date = record_data["trade_date"]
        symbol = record_data["symbol"]
        record = db.query(models.MarketData).filter(
            models.MarketData.trade_date == trade_date,
            models.MarketData.symbol == symbol,
        ).first()
        if record is None:
            record = models.MarketData(**record_data)
            db.add(record)
        else:
            for key, value in record_data.items():
                if key not in ("trade_date", "symbol"):
                    setattr(record, key, value)
        count += 1
    db.commit()
    return count


def get_local_market_data(
    db: Session,
    trade_date: date,
    symbol: Optional[str] = None,
    market_type: Optional[str] = None,
) -> List[models.MarketData]:
    query = db.query(models.MarketData).filter(models.MarketData.trade_date == trade_date)
    if symbol:
        query = query.filter(models.MarketData.symbol == symbol)
    if market_type:
        query = query.filter(models.MarketData.market_type == market_type)
    return query.all()


def get_local_market_data_range(
    db: Session,
    start_date: date,
    end_date: date,
    symbol: Optional[str] = None,
    market_type: Optional[str] = None,
) -> List[models.MarketData]:
    query = db.query(models.MarketData).filter(
        models.MarketData.trade_date >= start_date,
        models.MarketData.trade_date <= end_date,
    )
    if symbol:
        query = query.filter(models.MarketData.symbol == symbol)
    if market_type:
        query = query.filter(models.MarketData.market_type == market_type)
    return query.order_by(models.MarketData.trade_date).all()


def get_strategy_stock_performance(db: Session, strategy_id: int) -> Tuple[List[models.BatchStock], List[dict]]:
    from app.config import DEFAULT_MARKET_TYPE_STOCK

    strategy = db.query(models.Strategy).filter(models.Strategy.id == strategy_id).first()
    if not strategy:
        return [], []

    all_stocks = []
    for batch in strategy.batches:
        for stock in batch.stocks:
            stock_info = {
                "stock_code": stock.stock_code,
                "stock_name": stock.stock_name,
                "batch_id": batch.id,
                "batch_name": batch.name,
                "added_date": stock.added_date,
                "is_traded": stock.is_traded,
                "is_held": stock.is_held,
            }
            all_stocks.append(stock_info)

    if not all_stocks:
        return [], []

    today = date.today()
    performances = []

    for stock_info in all_stocks:
        stock_code = stock_info["stock_code"]
        added_date = stock_info["added_date"]

        if not added_date:
            continue

        hold_days = (today - added_date).days if added_date else 0

        price_rows = (
            db.query(models.MarketData)
            .filter(
                models.MarketData.symbol == stock_code,
                models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
            )
            .order_by(models.MarketData.trade_date.asc())
            .all()
        )

        if not price_rows:
            continue

        entry_row = None
        for row in price_rows:
            if row.trade_date >= added_date:
                entry_row = row
                break

        if not entry_row:
            entry_row = price_rows[-1]

        entry_price = float(entry_row.close_price)
        current_price = float(price_rows[-1].close_price)

        if entry_price <= 0:
            continue

        current_return = (current_price / entry_price - 1) * 100

        lowest_price = entry_price
        highest_price = entry_price

        for row in price_rows:
            if row.trade_date < entry_row.trade_date:
                continue
            price = float(row.close_price)
            lowest_price = min(lowest_price, price)
            highest_price = max(highest_price, price)

        max_drawdown = (lowest_price / entry_price - 1) * 100
        max_gain = (highest_price / entry_price - 1) * 100

        performances.append({
            "stock_code": stock_code,
            "stock_name": stock_info["stock_name"],
            "batch_id": stock_info["batch_id"],
            "batch_name": stock_info["batch_name"],
            "added_date": stock_info["added_date"],
            "hold_days": hold_days,
            "current_return": current_return / 100 if current_return != 0 else 0.0,
            "max_drawdown": max_drawdown / 100 if max_drawdown != 0 else 0.0,
            "max_gain": max_gain / 100 if max_gain != 0 else 0.0,
            "is_profitable": current_return > 0,
        })

    return all_stocks, performances


def get_batch_stocks_performance(db: Session, batch_id: int) -> List[dict]:
    from app.config import DEFAULT_MARKET_TYPE_STOCK

    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        return []

    today = date.today()
    performances = []

    for stock in batch.stocks:
        stock_code = stock.stock_code
        added_date = stock.added_date

        if not added_date:
            hold_days = 0
            added_close_price = None
            current_price = None
            current_return = 0.0
            max_drawdown = 0.0
            max_gain = 0.0
        else:
            hold_days = (today - added_date).days if added_date else 0

            price_rows = (
                db.query(models.MarketData)
                .filter(
                    models.MarketData.symbol == stock_code,
                    models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
                )
                .order_by(models.MarketData.trade_date.asc())
                .all()
            )

            if not price_rows:
                added_close_price = None
                current_price = None
                current_return = 0.0
                max_drawdown = 0.0
                max_gain = 0.0
            else:
                entry_row = None
                for row in price_rows:
                    if row.trade_date >= added_date:
                        entry_row = row
                        break

                if not entry_row:
                    entry_row = price_rows[-1]

                added_close_price = float(entry_row.close_price) if entry_row else None
                current_price = float(price_rows[-1].close_price)

                if added_close_price and added_close_price > 0:
                    current_return = (current_price / added_close_price - 1) * 100

                    lowest_price = added_close_price
                    highest_price = added_close_price

                    for row in price_rows:
                        if row.trade_date < entry_row.trade_date:
                            continue
                        price = float(row.close_price)
                        lowest_price = min(lowest_price, price)
                        highest_price = max(highest_price, price)

                    max_drawdown = (lowest_price / added_close_price - 1) * 100
                    max_gain = (highest_price / added_close_price - 1) * 100
                else:
                    current_return = 0.0
                    max_drawdown = 0.0
                    max_gain = 0.0

        performances.append({
            "id": stock.id,
            "stock_code": stock_code,
            "stock_name": stock.stock_name,
            "added_date": added_date,
            "added_close_price": added_close_price,
            "current_price": current_price,
            "current_return": current_return / 100 if current_return != 0 else 0.0,
            "max_drawdown": max_drawdown / 100 if max_drawdown != 0 else 0.0,
            "max_gain": max_gain / 100 if max_gain != 0 else 0.0,
            "hold_days": hold_days,
            "remark": stock.remark,
            "is_traded": stock.is_traded,
            "is_held": stock.is_held,
        })

    return performances


def get_stock_detail(db: Session, batch_id: int, stock_id: int) -> Optional[dict]:
    from app.config import DEFAULT_MARKET_TYPE_STOCK

    stock = db.query(models.BatchStock).filter(models.BatchStock.id == stock_id, models.BatchStock.batch_id == batch_id).first()
    if not stock:
        return None

    batch = stock.batch
    today = date.today()
    stock_code = stock.stock_code
    added_date = stock.added_date

    if not added_date:
        hold_days = 0
        added_close_price = None
        current_price = None
        current_return = 0.0
        max_drawdown = 0.0
        max_gain = 0.0
        return_history = []
    else:
        hold_days = (today - added_date).days if added_date else 0

        price_rows = (
            db.query(models.MarketData)
            .filter(
                models.MarketData.symbol == stock_code,
                models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
            )
            .order_by(models.MarketData.trade_date.asc())
            .all()
        )

        if not price_rows:
            added_close_price = None
            current_price = None
            current_return = 0.0
            max_drawdown = 0.0
            max_gain = 0.0
            return_history = []
        else:
            entry_row = None
            for row in price_rows:
                if row.trade_date >= added_date:
                    entry_row = row
                    break

            if not entry_row:
                entry_row = price_rows[-1]

            added_close_price = float(entry_row.close_price) if entry_row else None
            current_price = float(price_rows[-1].close_price)

            if added_close_price and added_close_price > 0:
                current_return = (current_price / added_close_price - 1) * 100

                lowest_price = added_close_price
                highest_price = added_close_price

                return_history = []
                for row in price_rows:
                    if row.trade_date < entry_row.trade_date:
                        continue
                    price = float(row.close_price)
                    lowest_price = min(lowest_price, price)
                    highest_price = max(highest_price, price)
                    
                    daily_return = (price / added_close_price - 1) * 100
                    return_history.append({
                        "date": row.trade_date.isoformat(),
                        "return": daily_return / 100  # 转换为小数
                    })

                max_drawdown = (lowest_price / added_close_price - 1) * 100
                max_gain = (highest_price / added_close_price - 1) * 100
            else:
                current_return = 0.0
                max_drawdown = 0.0
                max_gain = 0.0
                return_history = []

    return {
        "stock_code": stock_code,
        "stock_name": stock.stock_name,
        "batch_id": batch_id,
        "batch_name": batch.name if batch else None,
        "added_date": added_date,
        "added_close_price": added_close_price,
        "current_price": current_price,
        "current_return": current_return / 100 if current_return != 0 else 0.0,  # 转换为小数
        "max_drawdown": max_drawdown / 100 if max_drawdown != 0 else 0.0,  # 转换为小数
        "max_gain": max_gain / 100 if max_gain != 0 else 0.0,  # 转换为小数
        "hold_days": hold_days,
        "return_history": return_history,
    }