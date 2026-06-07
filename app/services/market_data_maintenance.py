import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from app import crud, models
from app.config import DEFAULT_MARKET_TYPE_STOCK
from app.database import SessionLocal
from app.services.market_data import (
    TushareMarketDataProvider,
    get_market_data_provider,
)


logger = logging.getLogger(__name__)


class MarketDataMaintenance:
    def __init__(self, interval_hours: int = 1, lookback_days: int = 60, new_stock_lookback_days: int = 300):
        self.interval_seconds = interval_hours * 3600
        self.lookback_days = lookback_days
        self.new_stock_lookback_days = new_stock_lookback_days
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None
        self._is_running = False
        self._sync_lock = threading.Lock()

    def _get_provider(self):
        config = get_market_data_provider()
        if not isinstance(config, TushareMarketDataProvider):
            raise RuntimeError("Market data maintenance requires Tushare provider")
        return config

    def _log_to_db(self, db, level: str, message: str, details: dict = None):
        try:
            crud.create_app_log(
                db,
                level=level,
                message=message,
                category="sync",
                source="maintenance",
                details=details,
            )
        except Exception as e:
            logger.warning(f"Failed to write log to database: {e}")

    def _normalize_ts_code(self, stock_code: str) -> str:
        stock_code = stock_code.strip()
        if stock_code.startswith(("6", "9", "5", "7")):
            suffix = ".SH"
        elif stock_code.startswith(("0", "1", "2", "3")):
            suffix = ".SZ"
        else:
            suffix = ".SZ"
        if stock_code.endswith((".SH", ".SZ")):
            return stock_code
        return f"{stock_code}{suffix}"

    def _get_pro_api(self):
        import tushare as ts
        from app.config_loader import load_app_config
        config = load_app_config()
        token = config.get("market_data", {}).get("tushare", {}).get("token")
        if not token:
            raise RuntimeError("Tushare token not configured")
        return ts.pro_api(token)

    def _fetch_stock_daily(self, pro, stock_code: str, start_date: date, end_date: date) -> list[dict]:
        """使用个股接口获取日线数据"""
        ts_code = self._normalize_ts_code(stock_code)
        df = pro.query(
            "daily",
            ts_code=ts_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        if df is None or len(df) == 0:
            return []

        records = []
        for _, row in df.iterrows():
            records.append({
                "trade_date": datetime.strptime(str(row["trade_date"]), "%Y%m%d").date(),
                "symbol": stock_code,
                "market_type": DEFAULT_MARKET_TYPE_STOCK,
                "close_price": float(row["close"]),
                "open_price": float(row["open"]) if row["open"] else None,
                "high_price": float(row["high"]) if row["high"] else None,
                "low_price": float(row["low"]) if row["low"] else None,
                "volume": int(row["vol"]) if row["vol"] else None,
                "source": "tushare",
            })
        return records

    def _sync_new_stocks(self, db) -> dict[str, Any]:
        """同步新增股票的历史数据（使用个股接口，无限制）"""
        results = {
            "new_stocks_found": 0,
            "stocks_synced": 0,
            "records_synced": 0,
            "errors": [],
        }

        all_stocks = crud.get_all_batch_stock_codes(db)
        if not all_stocks:
            self._log_to_db(db, "info", "未找到批次股票")
            return results

        today = date.today()
        pro = self._get_pro_api()

        for stock_code in all_stocks:
            batch_stock = db.query(models.BatchStock).filter(
                models.BatchStock.stock_code == stock_code
            ).first()

            if not batch_stock or not batch_stock.added_date:
                continue

            added_date = batch_stock.added_date
            start_date = added_date - timedelta(days=365)
            check_date = added_date - timedelta(days=1)

            existing_count = crud.get_market_data_count_from_date(db, stock_code, start_date)
            if existing_count > 240:
                continue

            results["new_stocks_found"] += 1
            logger.info(f"同步新增股票 {stock_code} 的历史数据 ({start_date} ~ {today})...")

            try:
                records = self._fetch_stock_daily(pro, stock_code, start_date, today)
                if records:
                    count = crud.upsert_market_data_batch(db, records)
                    results["records_synced"] += count
                    results["stocks_synced"] += 1
                    self._log_to_db(
                        db, "info",
                        f"同步股票 {stock_code}: {count} 条历史数据 ({start_date} ~ {today})",
                        {"stock_code": stock_code, "count": count, "start": str(start_date), "end": str(today)}
                    )
                db.commit()
            except Exception as e:
                error_msg = f"同步股票 {stock_code} 失败: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                self._log_to_db(db, "error", error_msg)

            time.sleep(2)

        return results

    def _fetch_and_save_market_data(self, trade_date: date, db) -> tuple[int, int, list[str]]:
        """使用批量接口获取当日数据（有频率限制）"""
        provider = self._get_provider()
        success_count = 0
        fail_count = 0
        errors = []

        try:
            market_data_list = provider.fetch_all_stocks_daily(trade_date)

            if not market_data_list:
                errors.append(f"No data returned for {trade_date}")
                return success_count, fail_count, errors

            records = [data.as_dict() for data in market_data_list]
            success_count = crud.upsert_market_data_batch(db, records)

        except Exception as e:
            errors.append(f"API error: {str(e)}")
            raise

        return success_count, fail_count, errors

    def _get_days_to_sync(self, start_date: date, end_date: date, db) -> list[date]:
        provider = self._get_provider()
        existing_dates = set(crud.get_existing_market_data_dates(db, start_date, end_date))
        trading_days = provider.get_trading_days(start_date, end_date)
        days_to_sync = [d for d in trading_days if d not in existing_dates]
        return days_to_sync

    def run_sync(self) -> dict[str, Any]:
        """执行每日增量同步"""
        self._is_running = True
        db = SessionLocal()
        results = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": False,
            "total_days": 0,
            "success_count": 0,
            "fail_count": 0,
            "errors": [],
            "error": None,
        }

        self._log_to_db(db, "info", "开始市场数据每日同步")

        try:
            earliest_date = crud.get_earliest_batch_stock_date(db)
            if earliest_date is None:
                results["error"] = "No batch stocks found"
                results["end_time"] = datetime.now().isoformat()
                self._is_running = False
                self._log_to_db(db, "warning", "未找到批次股票，无法同步")
                return results

            start_date = earliest_date - timedelta(days=self.lookback_days)
            end_date = date.today()

            days_to_sync = self._get_days_to_sync(start_date, end_date, db)
            results["total_days"] = len(days_to_sync)

            if len(days_to_sync) == 0:
                self._log_to_db(db, "info", "无需同步，数据已是最新")
                results["success"] = True
                results["end_time"] = datetime.now().isoformat()
                self._is_running = False
                return results

            logger.info(f"需要同步 {len(days_to_sync)} 个交易日")
            self._log_to_db(db, "info", f"每日同步: 需要同步 {len(days_to_sync)} 个交易日")

            total_success = 0
            total_fail = 0
            all_errors = []

            for trade_date in days_to_sync:
                if self._stop_event.is_set():
                    self._log_to_db(db, "info", "同步被手动停止")
                    break

                try:
                    s, f, errors = self._fetch_and_save_market_data(trade_date, db)
                    total_success += s
                    total_fail += f
                    all_errors.extend(errors)
                    logger.info(f"Synced {trade_date}: {s} success, {f} failed")

                    crud.create_sync_log(
                        db,
                        trade_date=trade_date,
                        status="success" if f == 0 else "failed",
                        success_count=s,
                        fail_count=f,
                        error_detail="; ".join(errors) if errors else None,
                        source="maintenance",
                    )

                except Exception as e:
                    error_msg = f"同步失败 {trade_date}: {str(e)}"
                    logger.error(error_msg)
                    all_errors.append(error_msg)
                    results["error"] = error_msg
                    self._last_error = error_msg
                    self._log_to_db(db, "error", error_msg, {"trade_date": str(trade_date)})
                    break

            results["success"] = True
            results["success_count"] = total_success
            results["fail_count"] = total_fail
            results["errors"] = all_errors[:100]
            self._last_error = None

            self._log_to_db(
                db, "info",
                f"每日同步完成: {total_success} 条数据",
                {"total_days": results["total_days"], "success": total_success, "fail": total_fail}
            )

        except Exception as e:
            results["error"] = str(e)
            self._last_error = str(e)
            logger.error(f"Market data maintenance error: {e}")
            self._log_to_db(db, "error", f"每日同步异常: {str(e)}", {"error": str(e)})
        finally:
            db.close()
            results["end_time"] = datetime.now().isoformat()
            self._is_running = False

        return results

    def run_full_sync(self) -> dict[str, Any]:
        """执行完整同步：先同步新增股票，再执行每日增量同步"""
        db = SessionLocal()
        results = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "new_stocks": {},
            "daily_sync": {},
        }

        self._log_to_db(db, "info", "开始完整数据同步")

        try:
            logger.info("步骤1: 同步新增股票历史数据...")
            self._log_to_db(db, "info", "步骤1: 同步新增股票历史数据...")
            results["new_stocks"] = self._sync_new_stocks(db)

            logger.info("步骤2: 执行每日增量同步...")
            self._log_to_db(db, "info", "步骤2: 执行每日增量同步...")
            results["daily_sync"] = self.run_sync()

        except Exception as e:
            logger.error(f"Full sync error: {e}")
            self._log_to_db(db, "error", f"完整同步异常: {str(e)}")
            results["error"] = str(e)
        finally:
            db.close()
            results["end_time"] = datetime.now().isoformat()

        return results

    def _worker(self):
        while not self._stop_event.is_set():
            logger.info("Starting market data maintenance cycle")
            self._log_to_db(SessionLocal(), "info", "后台同步服务开始执行")
            try:
                self.run_full_sync()
            except Exception as e:
                logger.error(f"Maintenance worker error: {e}")
                self._last_error = str(e)
                self._log_to_db(SessionLocal(), "error", f"后台服务异常: {str(e)}")

            if self._stop_event.is_set():
                break

            logger.info(f"Waiting {self.interval_seconds // 3600} hour(s) before next sync")
            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("Maintenance is already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info("Market data maintenance started")
        db = SessionLocal()
        self._log_to_db(db, "info", "后台同步服务已启动")
        db.close()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Market data maintenance stopped")
        db = SessionLocal()
        self._log_to_db(db, "info", "后台同步服务已停止")
        db.close()

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def is_running(self) -> bool:
        return self._is_running


_maintenance_service: Optional[MarketDataMaintenance] = None


def get_maintenance_service() -> Optional[MarketDataMaintenance]:
    return _maintenance_service


def start_maintenance_service(interval_hours: int = 1, lookback_days: int = 60, new_stock_lookback_days: int = 300) -> MarketDataMaintenance:
    global _maintenance_service
    _maintenance_service = MarketDataMaintenance(
        interval_hours=interval_hours,
        lookback_days=lookback_days,
        new_stock_lookback_days=new_stock_lookback_days,
    )
    _maintenance_service.start()
    return _maintenance_service


def stop_maintenance_service():
    global _maintenance_service
    if _maintenance_service:
        _maintenance_service.stop()