from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models
from app.deps import get_current_user, get_db
from app.schemas import (
    BatchComparisonItem,
    BatchComparisonResponse,
    HoldReturnResponse,
    MetricsPoint,
    MetricsResponse,
    MetricsSummary,
)
from app.services.metrics import hold_return_for_batch, hold_return_for_stock, hold_return_for_strategy

router = APIRouter()

def build_metrics_response(metric_rows: List[models.StrategyMetric], start: date, end: date, strategy_id: Optional[int] = None, batch_id: Optional[int] = None, stock_code: Optional[str] = None) -> MetricsResponse:
    points = [MetricsPoint(trade_date=row.metric_date, daily_return=float(row.daily_return or 0.0), cumulative_return=float(row.cumulative_return or 0.0)) for row in metric_rows]
    drawdowns = [float(row.max_drawdown or 0.0) for row in metric_rows]
    gains = [float(row.max_gain or 0.0) for row in metric_rows]
    summary = MetricsSummary(
        total_return=float(metric_rows[-1].cumulative_return or 0.0) if metric_rows else 0.0,
        max_drawdown=min(drawdowns) if drawdowns else 0.0,
        max_gain=max(gains) if gains else 0.0,
    )
    return MetricsResponse(strategy_id=strategy_id, batch_id=batch_id, stock_code=stock_code, start=start, end=end, daily=points, summary=summary)

@router.get("/strategies/{strategy_id}/metrics", response_model=MetricsResponse)
def strategy_metrics(strategy_id: int, start: date, end: date, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if current_user.role == "user" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    metrics = crud.get_strategy_metrics(db, strategy_id=strategy_id, start=start, end=end)
    return build_metrics_response(metrics, start, end, strategy_id=strategy_id)

@router.get("/batches/{batch_id}/metrics", response_model=MetricsResponse)
def batch_metrics(batch_id: int, start: date, end: date, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 使用基于个股的指标
    stock_based_metrics = crud.get_batch_stock_based_metrics(db, batch_id)
    
    # 构建响应
    summary = MetricsSummary(
        total_return=stock_based_metrics["average_return"],
        max_drawdown=stock_based_metrics["max_drawdown"],
        max_gain=stock_based_metrics["max_gain"],
    )
    
    return MetricsResponse(
        strategy_id=batch.strategy_id,
        batch_id=batch_id,
        start=start,
        end=end,
        daily=[],
        summary=summary,
    )

@router.get("/stocks/{stock_code}/kline")
def get_stock_kline(
    stock_code: str,
    start: date,
    end: date,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.config import DEFAULT_MARKET_TYPE_STOCK

    price_rows = (
        db.query(models.MarketData)
        .filter(
            models.MarketData.symbol == stock_code,
            models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
            models.MarketData.trade_date >= start,
            models.MarketData.trade_date <= end,
        )
        .order_by(models.MarketData.trade_date.asc())
        .all()
    )

    return {
        "stock_code": stock_code,
        "dates": [row.trade_date.isoformat() for row in price_rows],
        "opens": [float(row.open_price) if row.open_price else None for row in price_rows],
        "closes": [float(row.close_price) for row in price_rows],
        "highs": [float(row.high_price) if row.high_price else None for row in price_rows],
        "lows": [float(row.low_price) if row.low_price else None for row in price_rows],
        "volumes": [int(row.volume) if row.volume else 0 for row in price_rows],
    }

@router.get("/stocks/{stock_code}/metrics", response_model=MetricsResponse)
def stock_metrics(stock_code: str, start: date, end: date, batch_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role == "user" and batch_id is None:
        raise HTTPException(status_code=400, detail="batch_id is required for stock metrics")
    if batch_id:
        batch = crud.get_batch(db, batch_id=batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    metrics = crud.get_stock_metrics(db, stock_code=stock_code, start=start, end=end, batch_id=batch_id)
    return build_metrics_response(metrics, start, end, stock_code=stock_code)

@router.get("/metrics/hold-return", response_model=HoldReturnResponse)
def hold_return(n: int, k: int, scope: str, id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if n < 0 or k < 1:
        raise HTTPException(status_code=400, detail="n must be >= 0 and k must be >= 1")
    if scope not in {"strategy", "batch", "stock"}:
        raise HTTPException(status_code=400, detail="Invalid scope")

    value = None
    if scope == "strategy":
        strategy = crud.get_strategy(db, strategy_id=id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        if current_user.role == "user" and strategy.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        value = hold_return_for_strategy(db, strategy, n=n, k=k)
    elif scope == "batch":
        batch = crud.get_batch(db, batch_id=id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        value = hold_return_for_batch(db, batch, n=n, k=k)
    else:
        stock = crud.get_batch_stock(db, stock_id=id)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        if current_user.role == "user" and stock.batch.strategy.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        value = hold_return_for_stock(db, stock, n=n, k=k)

    return HoldReturnResponse(
        scope=scope,
        id=id,
        n=n,
        k=k,
        hold_return=value,
        status="completed" if value is not None else "insufficient_data",
    )


@router.get("/strategies/{strategy_id}/compare-batches", response_model=BatchComparisonResponse)
def compare_batches(strategy_id: int, trade_date: Optional[date] = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if current_user.role == "user" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    comparison = []
    for batch in strategy.batches:
        query = db.query(models.StrategyMetric).filter(
            models.StrategyMetric.batch_id == batch.id,
            models.StrategyMetric.stock_code.is_(None),
        )
        if trade_date:
            query = query.filter(models.StrategyMetric.metric_date == trade_date)
        metric = query.order_by(models.StrategyMetric.metric_date.desc()).first()
        if not metric:
            continue
        comparison.append(
            BatchComparisonItem(
                batch_id=batch.id,
                batch_name=batch.name,
                total_return=float(metric.cumulative_return or 0.0),
                max_drawdown=float(metric.max_drawdown or 0.0),
                max_gain=float(metric.max_gain or 0.0),
            )
        )

    return BatchComparisonResponse(strategy_id=strategy_id, trade_date=trade_date, batch_comparison=comparison)