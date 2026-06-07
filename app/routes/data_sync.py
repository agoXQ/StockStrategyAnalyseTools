from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.config import DEFAULT_MARKET_TYPE_INDEX, DEFAULT_MARKET_TYPE_STOCK
from app.deps import get_current_user, get_db, require_admin
from app.models import MarketData
from app.schemas import SyncHistoryItem, SyncRequest, SyncStatusOut
from app.services.metrics import recalculate_all_metrics

router = APIRouter()


class MarketDataResponse(BaseModel):
    trade_date: date
    symbol: str
    market_type: str
    close_price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[int] = None
    source: Optional[str] = None

    class Config:
        orm_mode = True


@router.post("/sync")
def sync_data(payload: SyncRequest, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    trade_date = payload.trade_date or date.today()
    stock_codes = payload.stock_codes or []
    index_codes = payload.index_codes or []
    success_count = 0
    fail_count = 0
    errors = []

    for symbol in stock_codes:
        market_data = (
            db.query(MarketData)
            .filter(
                MarketData.trade_date == trade_date,
                MarketData.symbol == symbol,
                MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
            )
            .first()
        )
        if market_data:
            success_count += 1
        else:
            fail_count += 1
            errors.append(f"{symbol}: No data in local database")

    for symbol in index_codes:
        market_data = (
            db.query(MarketData)
            .filter(
                MarketData.trade_date == trade_date,
                MarketData.symbol == symbol,
                MarketData.market_type == DEFAULT_MARKET_TYPE_INDEX,
            )
            .first()
        )
        if market_data:
            success_count += 1
        else:
            fail_count += 1
            errors.append(f"{symbol}: No data in local database")

    recalculated_metrics = recalculate_all_metrics(db) if payload.recalculate_metrics else 0

    crud.create_sync_log(
        db,
        trade_date=trade_date,
        status="success" if fail_count == 0 else "failed",
        success_count=success_count,
        fail_count=fail_count,
        error_detail="; ".join(errors) if errors else None,
        source="manual",
    )

    crud.log_info(
        db,
        message=f"手动同步 {trade_date}: {success_count} 成功, {fail_count} 失败",
        category="sync",
        source="manual",
        details={"trade_date": str(trade_date), "success_count": success_count, "fail_count": fail_count},
    )

    return {
        "trade_date": trade_date,
        "success_count": success_count,
        "fail_count": fail_count,
        "errors": errors,
        "recalculated_metrics": recalculated_metrics,
        "source": "local_database",
    }


@router.get("/data")
def get_local_market_data(
    trade_date: date,
    symbol: Optional[str] = None,
    market_type: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(5000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(MarketData).filter(MarketData.trade_date == trade_date)
    if symbol:
        query = query.filter(MarketData.symbol == symbol)
    if market_type:
        query = query.filter(MarketData.market_type == market_type)

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return {
        "trade_date": trade_date,
        "total": total,
        "items": [
            {
                "symbol": item.symbol,
                "market_type": item.market_type,
                "close_price": float(item.close_price),
                "open_price": float(item.open_price) if item.open_price else None,
                "high_price": float(item.high_price) if item.high_price else None,
                "low_price": float(item.low_price) if item.low_price else None,
                "volume": item.volume,
                "source": item.source,
            }
            for item in items
        ],
    }


@router.get("/status", response_model=SyncStatusOut)
def get_sync_status(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    logs = crud.list_sync_logs(db, skip=0, limit=1)
    last = logs[0] if logs else None
    return SyncStatusOut(
        last_sync_date=last.trade_date if last else None,
        success_count=last.success_count if last else 0,
        fail_count=last.fail_count if last else 0,
        errors=[last.error_detail] if last and last.error_detail else []
    )


@router.get("/history", response_model=List[SyncHistoryItem])
def get_sync_history(
    start: Optional[date] = None,
    end: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logs = crud.list_sync_logs(db, skip=skip, limit=limit, start=start, end=end)
    return [SyncHistoryItem.from_orm(log) for log in logs]