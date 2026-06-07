from datetime import date
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.deps import get_current_user, get_db, require_admin
from app.schemas import AppLogItem, SyncHistoryItem
from app.services.market_data_maintenance import (
    get_maintenance_service,
    start_maintenance_service,
    stop_maintenance_service,
)


router = APIRouter()


class MaintenanceStatusResponse(BaseModel):
    is_running: bool
    last_error: Optional[str]


class MaintenanceStartRequest(BaseModel):
    interval_hours: int = 1
    lookback_days: int = 60


class MaintenanceResultResponse(BaseModel):
    success: bool
    total_days: int
    success_count: int
    fail_count: int
    errors: list


class LogListResponse(BaseModel):
    total: int
    items: List[Union[SyncHistoryItem, AppLogItem]]


@router.get("/status", response_model=MaintenanceStatusResponse)
def get_maintenance_status(current_user=Depends(get_current_user)):
    service = get_maintenance_service()
    return MaintenanceStatusResponse(
        is_running=service.is_running if service else False,
        last_error=service.last_error if service else None,
    )


@router.post("/start")
def start_maintenance(
    payload: Optional[MaintenanceStartRequest] = None,
    current_user=Depends(require_admin),
):
    service = get_maintenance_service()
    if service and service.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maintenance service is already running",
        )

    interval = payload.interval_hours if payload else 1
    lookback = payload.lookback_days if payload else 60

    try:
        service = start_maintenance_service(
            interval_hours=interval,
            lookback_days=lookback,
        )
        return {"status": "started", "interval_hours": interval, "lookback_days": lookback}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/stop")
def stop_maintenance(current_user=Depends(require_admin)):
    service = get_maintenance_service()
    if not service or not service.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maintenance service is not running",
        )

    try:
        stop_maintenance_service()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/run", response_model=MaintenanceResultResponse)
def run_maintenance_once(
    payload: Optional[MaintenanceStartRequest] = None,
    current_user=Depends(require_admin),
):
    service = get_maintenance_service()
    if service is None:
        service = start_maintenance_service(
            interval_hours=payload.interval_hours if payload else 1,
            lookback_days=payload.lookback_days if payload else 60,
        )

    try:
        result = service.run_sync()
        return MaintenanceResultResponse(
            success=result["success"],
            total_days=result["total_days"],
            success_count=result["success_count"],
            fail_count=result["fail_count"],
            errors=result["errors"],
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


class BatchApiSyncRequest(BaseModel):
    trade_date: date


class ManualSyncRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@router.post("/run-batch-api-sync")
def run_batch_api_sync(
    payload: BatchApiSyncRequest,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量接口同步：调用 Tushare daily 批量接口获取指定日期的所有股票数据"""
    service = get_maintenance_service()
    if service is None:
        service = start_maintenance_service()

    try:
        result = service.run_batch_api_sync(db, trade_date=payload.trade_date)
        return {
            "success": result["success"],
            "start_time": result["start_time"],
            "end_time": result["end_time"],
            "trade_date": result["trade_date"],
            "success_count": result["success_count"],
            "fail_count": result["fail_count"],
            "errors": result["errors"],
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/run-full-sync")
def run_manual_full_sync(
    payload: Optional[ManualSyncRequest] = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """手动批量同步：按指定日期范围批量获取股票数据"""
    service = get_maintenance_service()
    if service is None:
        service = start_maintenance_service()

    try:
        result = service.run_manual_full_sync(
            db,
            start_date=payload.start_date if payload else None,
            end_date=payload.end_date if payload else None,
        )
        return {
            "success": result["success"],
            "start_time": result["start_time"],
            "end_time": result["end_time"],
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "success_count": result["success_count"],
            "fail_count": result["fail_count"],
            "errors": result["errors"],
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/logs/sync", response_model=List[SyncHistoryItem])
def get_sync_logs(
    start: Optional[date] = None,
    end: Optional[date] = None,
    source: Optional[str] = None,
    log_type: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logs = crud.list_sync_logs(
        db,
        skip=skip,
        limit=limit,
        start=start,
        end=end,
        source=source,
        log_type=log_type,
    )
    return [SyncHistoryItem.from_orm(log) for log in logs]


@router.get("/logs/app", response_model=List[AppLogItem])
def get_app_logs(
    level: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logs = crud.list_app_logs(
        db,
        skip=skip,
        limit=limit,
        level=level,
        category=category,
        source=source,
        start=start,
        end=end,
    )
    return [AppLogItem.from_orm(log) for log in logs]


@router.get("/logs", response_model=List[Union[SyncHistoryItem, AppLogItem]])
def get_all_logs(
    log_type: Optional[str] = Query(None, description="日志类型: sync, app, 或 all"),
    level: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    results = []

    if log_type is None or log_type == "all" or log_type == "sync":
        sync_logs = crud.list_sync_logs(
            db,
            skip=skip,
            limit=limit,
            start=start,
            end=end,
            source=source,
        )
        results.extend([SyncHistoryItem.from_orm(log) for log in sync_logs])

    if log_type is None or log_type == "all" or log_type == "app":
        app_logs = crud.list_app_logs(
            db,
            skip=skip,
            limit=limit,
            level=level,
            category=category,
            source=source,
            start=start,
            end=end,
        )
        results.extend([AppLogItem.from_orm(log) for log in app_logs])

    results.sort(key=lambda x: x.created_at, reverse=True)
    return results[:limit]


class LogCleanupRequest(BaseModel):
    retention_days: int = 7


class LogCleanupResponse(BaseModel):
    app_logs_deleted: int
    sync_logs_deleted: int
    total_deleted: int
    cutoff_date: str


@router.post("/logs/clean", response_model=LogCleanupResponse)
def clean_old_logs_endpoint(
    payload: Optional[LogCleanupRequest] = None,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """清理过期日志，默认保留7天"""
    retention_days = payload.retention_days if payload else 7
    
    try:
        result = crud.clean_old_logs(db, retention_days=retention_days)
        return LogCleanupResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))