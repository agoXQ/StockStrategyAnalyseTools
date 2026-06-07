import logging
from typing import Callable

from fastapi import Request, Response
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.crud import log_error
from app.database import SessionLocal

logger = logging.getLogger(__name__)


class DatabaseLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = None
        error_occurred = False
        error_detail = None

        try:
            response = await call_next(request)
            if response.status_code == 404 and not request.url.path.startswith("/docs") and not request.url.path.startswith("/openapi"):
                try:
                    db = SessionLocal()
                    try:
                        log_error(
                            db,
                            message=f"404: {request.method} {request.url.path}",
                            category="api",
                            source="middleware",
                            details={
                                "method": request.method,
                                "path": request.url.path,
                                "query_params": str(request.url.query),
                                "status_code": 404,
                            },
                        )
                    except Exception as log_exc:
                        logger.error(f"Failed to log 404 to database: {log_exc}")
                    finally:
                        db.close()
                except Exception:
                    pass
            return response
        except Exception as exc:
            error_occurred = True
            error_detail = self._get_error_detail(exc)
            tb = self._format_traceback(exc)

            logger.error(f"Unhandled exception: {exc}\n{tb}")

            db = SessionLocal()
            try:
                log_error(
                    db,
                    message=f"API异常: {request.method} {request.url.path}",
                    category="api",
                    source="middleware",
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": str(request.query_params),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "traceback": tb,
                    },
                )
            except Exception as log_exc:
                logger.error(f"Failed to log error to database: {log_exc}")
            finally:
                db.close()

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": str(exc) if not isinstance(exc, (ValueError, TypeError)) else "An error occurred",
                },
            )

    def _get_error_detail(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return str(exc)
        elif isinstance(exc, TypeError):
            return str(exc)
        elif hasattr(exc, "detail"):
            return str(exc.detail)
        else:
            return str(exc)[:500]

    def _format_traceback(self, exc: Exception) -> str:
        import traceback
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def register_exception_handlers(app):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        db = SessionLocal()
        try:
            log_error(
                db,
                message=f"ValueError: {str(exc)}",
                category="api",
                source="handler",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": "ValueError",
                    "error_message": str(exc),
                },
            )
        finally:
            db.close()
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(TypeError)
    async def type_error_handler(request: Request, exc: TypeError):
        db = SessionLocal()
        try:
            log_error(
                db,
                message=f"TypeError: {str(exc)}",
                category="api",
                source="handler",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": "TypeError",
                    "error_message": str(exc),
                },
            )
        finally:
            db.close()
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        db = SessionLocal()
        try:
            log_error(
                db,
                message=f"未处理异常: {type(exc).__name__}",
                category="api",
                source="handler",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": tb,
                },
            )
        finally:
            db.close()
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


import traceback