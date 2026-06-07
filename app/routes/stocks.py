from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.deps import get_current_user, get_db
from app.schemas import BatchStockBulkCreate, BatchStockCreate, BatchStockOut, BatchStockUpdate
from app.services.metrics import recalculate_all_metrics

router = APIRouter()

@router.post("/batches/{batch_id}/stocks", response_model=BatchStockOut)
def add_stock(batch_id: int, stock_in: BatchStockCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    if crud.get_batch_stock_by_code(db, batch_id=batch_id, stock_code=stock_in.stock_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock already exists in batch")
    stock_data = stock_in.dict()
    stock_data["added_date"] = stock_data["added_date"] or batch.batch_date
    stock = crud.create_batch_stock(db, batch_id=batch_id, stock_data=stock_data)
    recalculate_all_metrics(db)
    return BatchStockOut.from_orm(stock)

@router.post("/batches/{batch_id}/stocks/bulk", response_model=List[BatchStockOut])
def add_stocks_bulk(batch_id: int, payload: BatchStockBulkCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    created = []
    for stock_in in payload.stocks:
        if crud.get_batch_stock_by_code(db, batch_id=batch_id, stock_code=stock_in.stock_code):
            continue
        stock_data = stock_in.dict()
        stock_data["added_date"] = stock_data["added_date"] or batch.batch_date
        created.append(crud.create_batch_stock(db, batch_id=batch_id, stock_data=stock_data))
    if created:
        recalculate_all_metrics(db)
    return [BatchStockOut.from_orm(stock) for stock in created]

@router.get("/batches/{batch_id}/stocks", response_model=List[BatchStockOut])
def list_stocks(batch_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role == "user" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    stocks = crud.list_batch_stocks(db, batch_id=batch_id)
    return [BatchStockOut.from_orm(stock) for stock in stocks]

@router.put("/batches/{batch_id}/stocks/{stock_id}", response_model=BatchStockOut)
def update_stock(batch_id: int, stock_id: int, stock_in: BatchStockUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    stock = crud.get_batch_stock(db, stock_id=stock_id)
    if not stock or stock.batch_id != batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    updated = crud.update_batch_stock(db, stock=stock, updates=stock_in.dict(exclude_unset=True))
    return BatchStockOut.from_orm(updated)

@router.delete("/batches/{batch_id}/stocks/{stock_id}")
def delete_stock(batch_id: int, stock_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    stock = crud.get_batch_stock(db, stock_id=stock_id)
    if not stock or stock.batch_id != batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    crud.delete_batch_stock(db, stock)
    return {"ok": True}