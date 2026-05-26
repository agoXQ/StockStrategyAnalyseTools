from typing import List, Optional
from datetime import date, datetime, timedelta
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models
from app.deps import get_current_user, get_db
from app.schemas import BatchStockBulkCreate, BatchStockCreate, BatchStockOut, BatchStockUpdate
from app.services.metrics import recalculate_all_metrics

router = APIRouter()

def sync_stock_data_immediately(stock_codes: List[str], db: Session) -> dict:
    """立即同步股票数据"""
    try:
        from app.services.market_data_maintenance import MarketDataMaintenance
        from app.config import DEFAULT_MARKET_TYPE_STOCK
        
        maintenance = MarketDataMaintenance()
        results = {
            "success": True,
            "stocks_synced": 0,
            "records_synced": 0,
            "errors": []
        }
        
        today = date.today()
        pro = maintenance._get_pro_api()
        
        for stock_code in stock_codes:
            try:
                # 获取股票的加入日期
                batch_stock = db.query(models.BatchStock).filter(
                    models.BatchStock.stock_code == stock_code
                ).order_by(models.BatchStock.added_date.asc()).first()
                
                if batch_stock is None or batch_stock.added_date is None:
                    continue
                
                added_date = batch_stock.added_date
                if not isinstance(added_date, date):
                    continue
                    
                start_date: date = added_date - timedelta(days=365)
                
                # 检查是否已有足够数据
                existing_count = crud.get_market_data_count_from_date(db, stock_code, start_date)
                if existing_count > 240:
                    continue
                
                # 同步历史数据
                records = maintenance._fetch_stock_daily(pro, stock_code, start_date, today)
                if records:
                    count = crud.upsert_market_data_batch(db, records)
                    results["records_synced"] += count
                    results["stocks_synced"] += 1
                
            except Exception as e:
                error_msg = f"同步股票 {stock_code} 失败: {str(e)}"
                results["errors"].append(error_msg)
        
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stocks_synced": 0,
            "records_synced": 0,
            "errors": [str(e)]
        }

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
    
    # 立即同步股票数据（异步执行，不阻塞响应）
    def sync_in_background():
        try:
            sync_result = sync_stock_data_immediately([stock_in.stock_code], db)
            if sync_result["success"] and sync_result["stocks_synced"] > 0:
                recalculate_all_metrics(db)
        except Exception as e:
            print(f"Background sync error: {e}")
    
    sync_thread = threading.Thread(target=sync_in_background, daemon=True)
    sync_thread.start()
    
    return BatchStockOut.from_orm(stock)

@router.post("/batches/{batch_id}/stocks/bulk", response_model=List[BatchStockOut])
def add_stocks_bulk(batch_id: int, payload: BatchStockBulkCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    created = []
    stock_codes_to_sync = []
    for stock_in in payload.stocks:
        if crud.get_batch_stock_by_code(db, batch_id=batch_id, stock_code=stock_in.stock_code):
            continue
        stock_data = stock_in.dict()
        stock_data["added_date"] = stock_data["added_date"] or batch.batch_date
        created.append(crud.create_batch_stock(db, batch_id=batch_id, stock_data=stock_data))
        stock_codes_to_sync.append(stock_in.stock_code)
    
    if created:
        recalculate_all_metrics(db)
        
        # 立即同步股票数据（异步执行，不阻塞响应）
        if stock_codes_to_sync:
            def sync_in_background():
                try:
                    sync_result = sync_stock_data_immediately(stock_codes_to_sync, db)
                    if sync_result["success"] and sync_result["stocks_synced"] > 0:
                        recalculate_all_metrics(db)
                except Exception as e:
                    print(f"Background sync error: {e}")
            
            sync_thread = threading.Thread(target=sync_in_background, daemon=True)
            sync_thread.start()
    
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
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    stock = crud.get_batch_stock(db, stock_id=stock_id)
    if stock is None or stock.batch_id is None or stock.batch_id != batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    updated = crud.update_batch_stock(db, stock=stock, updates=stock_in.dict(exclude_unset=True))
    return BatchStockOut.from_orm(updated)

@router.delete("/batches/{batch_id}/stocks/{stock_id}")
def delete_stock(batch_id: int, stock_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = crud.get_batch(db, batch_id=batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    stock = crud.get_batch_stock(db, stock_id=stock_id)
    if stock is None or stock.batch_id is None or stock.batch_id != batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    if current_user.role != "admin" and batch.strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    crud.delete_batch_stock(db, stock)
    return {"ok": True}


@router.get("/stocks/search")
def search_stock_by_code(stock_code: str = Query(..., description="股票代码"), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """根据股票代码搜索股票信息"""
    result = crud.search_stock_by_code(db, stock_code=stock_code)
    if result:
        return result
    return {"stock_code": stock_code, "stock_name": None}