from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.deps import get_current_user, get_db
from app.schemas import BatchCreate, BatchDetailOut, BatchOut, BatchStockOut, BatchUpdate, BatchStockPerformance, StockDetail
from app.services.metrics import recalculate_all_metrics

router = APIRouter()

@router.post("/strategies/{strategy_id}/batches", response_model=BatchOut)
def create_batch(strategy_id: int, batch_in: BatchCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role != "admin" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    batch = crud.create_batch(db, strategy_id=strategy_id, batch_data=batch_in.dict())
    recalculate_all_metrics(db)
    return BatchOut.from_orm(batch)

@router.get("/strategies/{strategy_id}/batches", response_model=List[BatchOut])
def list_batches(
    strategy_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date: Optional[date] = Query(None, alias="startDate"),
    end_date: Optional[date] = Query(None, alias="endDate"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role == "user" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    batches = crud.list_batches(
        db,
        strategy_id=strategy_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
    )
    return [BatchOut.from_orm(batch) for batch in batches]

@router.get("/batches/{batch_id}", response_model=BatchDetailOut)
def get_batch(batch_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    result = BatchDetailOut.from_orm(batch)
    result.stocks = [BatchStockOut.from_orm(stock) for stock in batch.stocks]
    return result

@router.put("/batches/{batch_id}", response_model=BatchOut)
def update_batch(batch_id: int, batch_in: BatchUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    updated = crud.update_batch(db, batch=batch, updates=batch_in.dict(exclude_unset=True))
    return BatchOut.from_orm(updated)

@router.delete("/batches/{batch_id}")
def delete_batch(batch_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    crud.delete_batch(db, batch)
    return {"ok": True}

@router.get("/batches/{batch_id}/stocks/performance", response_model=List[BatchStockPerformance])
def get_batch_stocks_performance(batch_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    performances = crud.get_batch_stocks_performance(db, batch_id)
    return performances

@router.get("/batches/{batch_id}/stocks/{stock_id}/detail", response_model=StockDetail)
def get_stock_detail(batch_id: int, stock_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    detail = crud.get_stock_detail(db, batch_id, stock_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    
    return detail