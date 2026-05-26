from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.auth import router as auth_router
from app.routes.batches import router as batches_router
from app.routes.data_sync import router as data_sync_router
from app.routes.metrics import router as metrics_router
from app.routes.stocks import router as stocks_router
from app.routes.strategies import router as strategies_router
from app.routes.users import router as users_router
from app.routes.maintenance import router as maintenance_router
from app.config import CORS_ALLOW_ORIGINS
from app.database import engine
from app import models
from app.schema_migrations import ensure_sqlite_schema
from app.services.market_data_maintenance import start_maintenance_service, stop_maintenance_service
from app.middleware import DatabaseLoggingMiddleware, register_exception_handlers

models.Base.metadata.create_all(bind=engine)
ensure_sqlite_schema(engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Strategy Tracking Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(DatabaseLoggingMiddleware)
register_exception_handlers(app)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(strategies_router, prefix="/api/strategies", tags=["strategies"])
app.include_router(batches_router, prefix="/api", tags=["batches"])
app.include_router(stocks_router, prefix="/api", tags=["stocks"])
app.include_router(data_sync_router, prefix="/api/data", tags=["data_sync"])
app.include_router(metrics_router, prefix="/api", tags=["metrics"])
app.include_router(maintenance_router, prefix="/api/maintenance", tags=["maintenance"])

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


@app.on_event("startup")
async def startup_event():
    logger.info("Starting market data maintenance service...")
    try:
        start_maintenance_service(interval_hours=1, lookback_days=60)
        logger.info("Market data maintenance service started")
    except Exception as e:
        logger.error(f"Failed to start maintenance service: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping market data maintenance service...")
    stop_maintenance_service()
    logger.info("Market data maintenance service stopped")