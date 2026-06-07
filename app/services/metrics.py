from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app import models
from app.config import DEFAULT_MARKET_TYPE_STOCK


@dataclass
class MetricPoint:
    metric_date: date
    daily_return: float
    cumulative_return: float
    max_drawdown: float
    max_gain: float
    trade_days_since_entry: int


def _as_float(value) -> float:
    return float(value or 0)


def _average(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _price_rows(db: Session, stock_code: str, start_date: date) -> list[models.MarketData]:
    return (
        db.query(models.MarketData)
        .filter(
            models.MarketData.symbol == stock_code,
            models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
            models.MarketData.trade_date >= start_date,
        )
        .order_by(models.MarketData.trade_date.asc())
        .all()
    )


def _series_from_prices(rows: list[models.MarketData]) -> list[MetricPoint]:
    if not rows:
        return []

    entry_price = _as_float(rows[0].close_price)
    if entry_price <= 0:
        return []

    previous_price: Optional[float] = None
    peak_price = entry_price
    max_gain = 0.0
    max_drawdown = 0.0
    points: list[MetricPoint] = []

    for idx, row in enumerate(rows):
        price = _as_float(row.close_price)
        if price <= 0:
            continue

        daily_return = 0.0 if previous_price is None else price / previous_price - 1
        cumulative_return = price / entry_price - 1
        max_gain = max(max_gain, cumulative_return)
        peak_price = max(peak_price, price)
        drawdown = price / peak_price - 1 if peak_price else 0.0
        max_drawdown = min(max_drawdown, drawdown)

        points.append(
            MetricPoint(
                metric_date=row.trade_date,
                daily_return=daily_return,
                cumulative_return=cumulative_return,
                max_drawdown=max_drawdown,
                max_gain=max_gain,
                trade_days_since_entry=idx,
            )
        )
        previous_price = price

    return points


def _aggregate_series(series_list: list[list[MetricPoint]]) -> list[MetricPoint]:
    if not series_list:
        return []
        
    grouped: dict[date, list[MetricPoint]] = defaultdict(list)
    for series in series_list:
        for point in series:
            grouped[point.metric_date].append(point)

    if not grouped:
        return []

    max_gain = 0.0
    max_drawdown = 0.0
    peak_value = 0.0
    cumulative_sum = 0.0
    aggregated: list[MetricPoint] = []

    for idx, metric_date in enumerate(sorted(grouped)):
        points = grouped[metric_date]
        daily_return = _average(point.daily_return for point in points)
        cumulative_sum += _average(point.cumulative_return for point in points)
        cumulative_return = cumulative_sum
        max_gain = max(max_gain, cumulative_return)
        peak_value = max(peak_value, cumulative_return)
        drawdown = cumulative_return - peak_value
        max_drawdown = min(max_drawdown, drawdown)
        aggregated.append(
            MetricPoint(
                metric_date=metric_date,
                daily_return=daily_return,
                cumulative_return=cumulative_return,
                max_drawdown=max_drawdown,
                max_gain=max_gain,
                trade_days_since_entry=idx,
            )
        )

    return aggregated


def _add_metric_rows(
    db: Session,
    strategy_id: int,
    points: list[MetricPoint],
    batch_id: Optional[int] = None,
    stock_code: Optional[str] = None,
) -> int:
    if not points:
        from datetime import date
        db.add(
            models.StrategyMetric(
                strategy_id=strategy_id,
                batch_id=batch_id,
                stock_code=stock_code,
                metric_date=date.today(),
                daily_return=0.0,
                cumulative_return=0.0,
                max_drawdown=0.0,
                max_gain=0.0,
                trade_days_since_entry=0,
            )
        )
        return 1
        
    for point in points:
        db.add(
            models.StrategyMetric(
                strategy_id=strategy_id,
                batch_id=batch_id,
                stock_code=stock_code,
                metric_date=point.metric_date,
                daily_return=point.daily_return,
                cumulative_return=point.cumulative_return,
                max_drawdown=point.max_drawdown,
                max_gain=point.max_gain,
                trade_days_since_entry=point.trade_days_since_entry,
            )
        )
    return len(points)


def recalculate_all_metrics(db: Session) -> int:
    db.query(models.StrategyMetric).delete(synchronize_session=False)

    inserted = 0
    strategies = db.query(models.Strategy).all()
    for strategy in strategies:
        strategy_series: list[list[MetricPoint]] = []
        for batch in strategy.batches:
            batch_stock_series: list[list[MetricPoint]] = []
            for stock in batch.stocks:
                entry_date = stock.added_date or batch.batch_date
                stock_series = _series_from_prices(_price_rows(db, stock.stock_code, entry_date))
                inserted += _add_metric_rows(
                    db,
                    strategy_id=strategy.id,
                    batch_id=batch.id,
                    stock_code=stock.stock_code,
                    points=stock_series,
                )
                if stock_series:
                    batch_stock_series.append(stock_series)

            batch_series = _aggregate_series(batch_stock_series)
            inserted += _add_metric_rows(db, strategy_id=strategy.id, batch_id=batch.id, points=batch_series)
            if batch_series:
                strategy_series.append(batch_series)

        inserted += _add_metric_rows(db, strategy_id=strategy.id, points=_aggregate_series(strategy_series))

    db.commit()
    return inserted


def hold_return_for_stock(db: Session, batch_stock: models.BatchStock, n: int, k: int) -> Optional[float]:
    entry_date = batch_stock.added_date or batch_stock.batch.batch_date
    rows = _price_rows(db, batch_stock.stock_code, entry_date)
    buy_index = n
    sell_index = n + k
    if buy_index < 0 or sell_index >= len(rows):
        return None

    buy_price = _as_float(rows[buy_index].close_price)
    sell_price = _as_float(rows[sell_index].close_price)
    if buy_price <= 0:
        return None
    return sell_price / buy_price - 1


def hold_return_for_batch(db: Session, batch: models.Batch, n: int, k: int) -> Optional[float]:
    returns = []
    for stock in batch.stocks:
        value = hold_return_for_stock(db, stock, n=n, k=k)
        if value is None:
            return None
        returns.append(value)
    return _average(returns) if returns else None


def hold_return_for_strategy(db: Session, strategy: models.Strategy, n: int, k: int) -> Optional[float]:
    returns = []
    for batch in strategy.batches:
        value = hold_return_for_batch(db, batch, n=n, k=k)
        if value is None:
            return None
        returns.append(value)
    return _average(returns) if returns else None