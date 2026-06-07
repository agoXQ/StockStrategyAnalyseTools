from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models
from app.deps import get_current_user, get_db
from app.schemas import StrategyCreate, StrategyListResponse, StrategyOut, StrategyOverview, StockPerformance, StrategyUpdate

router = APIRouter()

@router.post("/", response_model=StrategyOut)
def create_strategy(strategy_in: StrategyCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.create_strategy(db, owner_id=current_user.id, strategy_data=strategy_in.dict())
    return StrategyOut.from_orm(strategy)

@router.get("/", response_model=StrategyListResponse)
def list_strategies(
    owner_id: Optional[int] = Query(None, alias="ownerId"),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "user":
        scoped_owner_id = current_user.id
    else:
        scoped_owner_id = owner_id
    skip = (page - 1) * page_size
    total, strategies = crud.list_strategies(
        db,
        owner_id=scoped_owner_id,
        keyword=keyword,
        skip=skip,
        limit=page_size,
    )
    return StrategyListResponse(total=total, items=[StrategyOut.from_orm(strategy) for strategy in strategies])

@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role == "user" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return StrategyOut.from_orm(strategy)

@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, strategy_in: StrategyUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role != "admin" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    updated = crud.update_strategy(db, strategy=strategy, updates=strategy_in.dict(exclude_unset=True))
    return StrategyOut.from_orm(updated)

@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role != "admin" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    crud.delete_strategy(db, strategy)
    return {"ok": True}

@router.get("/{strategy_id}/overview", response_model=StrategyOverview)
def get_strategy_overview(strategy_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role == "user" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    _, performances = crud.get_strategy_stock_performance(db, strategy_id)

    if not performances:
        return StrategyOverview(
            best_stock=None,
            worst_stock=None,
            win_rate=0.0,
            total_stocks=0,
            profitable_stocks=0,
            losing_stocks=0,
            average_return=0.0,
            max_drawdown=0.0,
            max_gain=0.0,
        )

    performances_sorted = sorted(performances, key=lambda x: x["current_return"], reverse=True)
    best = performances_sorted[0]
    worst = performances_sorted[-1]

    total = len(performances)
    profitable = sum(1 for p in performances if p["is_profitable"])
    losing = total - profitable

    average_return = sum(p["current_return"] for p in performances) / total if total > 0 else 0.0
    max_drawdown = min(p["max_drawdown"] for p in performances) if performances else 0.0
    max_gain = max(p["max_gain"] for p in performances) if performances else 0.0

    return StrategyOverview(
        best_stock=StockPerformance(**best),
        worst_stock=StockPerformance(**worst),
        win_rate=profitable / total if total > 0 else 0.0,
        total_stocks=total,
        profitable_stocks=profitable,
        losing_stocks=losing,
        average_return=average_return,
        max_drawdown=max_drawdown,
        max_gain=max_gain,
    )

@router.get("/{strategy_id}/win-rate-history")
def get_win_rate_history(strategy_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from datetime import timedelta
    from app.config import DEFAULT_MARKET_TYPE_STOCK

    strategy = crud.get_strategy(db, strategy_id=strategy_id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    if current_user.role == "user" and strategy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    all_stocks_data = []
    for batch in strategy.batches:
        for stock in batch.stocks:
            if stock.added_date:
                all_stocks_data.append({
                    "stock_code": stock.stock_code,
                    "added_date": stock.added_date,
                })

    if not all_stocks_data:
        return {"dates": [], "win_rates": [], "total_stocks": 0}

    max_date = date.today()
    min_date = min(s["added_date"] for s in all_stocks_data)

    trade_dates = (
        db.query(models.MarketData.trade_date)
        .filter(
            models.MarketData.trade_date >= min_date,
            models.MarketData.trade_date <= max_date,
            models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
        )
        .distinct()
        .order_by(models.MarketData.trade_date.asc())
        .all()
    )
    trade_dates = [d[0] for d in trade_dates]

    history = []
    for trade_date in trade_dates:
        profitable_count = 0
        total_count = 0

        for stock_info in all_stocks_data:
            if not stock_info["added_date"] or stock_info["added_date"] > trade_date:
                continue

            all_price_rows = (
                db.query(models.MarketData)
                .filter(
                    models.MarketData.symbol == stock_info["stock_code"],
                    models.MarketData.market_type == DEFAULT_MARKET_TYPE_STOCK,
                )
                .order_by(models.MarketData.trade_date.asc())
                .all()
            )

            if not all_price_rows:
                continue

            entry_row = None
            for row in all_price_rows:
                if row.trade_date >= stock_info["added_date"]:
                    entry_row = row
                    break

            if not entry_row:
                entry_row = all_price_rows[-1]

            entry_price = float(entry_row.close_price)

            price_rows = [row for row in all_price_rows if row.trade_date >= entry_row.trade_date and row.trade_date <= trade_date]

            if not price_rows:
                continue

            current_price = float(price_rows[-1].close_price)

            if entry_price <= 0:
                continue

            total_count += 1
            if current_price > entry_price:
                profitable_count += 1

        win_rate = profitable_count / total_count if total_count > 0 else 0.0
        history.append({
            "date": trade_date.isoformat(),
            "win_rate": win_rate,
            "total_stocks": total_count,
        })

    return {
        "dates": [h["date"] for h in history],
        "win_rates": [h["win_rate"] for h in history],
        "total_stocks": [h["total_stocks"] for h in history],
    }