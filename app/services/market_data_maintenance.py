import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

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

    def _log_to_db(self, db, level: str, message: str, details: Optional[dict] = None):
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

    def _sync_stock_basic_info_from_daily_data(self, market_data_list, db) -> dict:
        """从每日数据同步股票基本信息到stock_basic_info表"""
        result = {
            "total_processed": 0,
            "new_stocks": 0,
            "updated_stocks": 0,
            "errors": []
        }
        
        try:
            pro = self._get_pro_api()
            
            unique_stock_codes = set()
            for data in market_data_list:
                if data.market_type == DEFAULT_MARKET_TYPE_STOCK:
                    unique_stock_codes.add(data.symbol)
            
            if not unique_stock_codes:
                return result
            
            all_stocks_basic_info = {}
            try:
                basic_df = pro.stock_basic()
                if basic_df is not None and not basic_df.empty:
                    for _, row in basic_df.iterrows():
                        ts_code = str(row.get("ts_code", ""))
                        if not ts_code or "." not in ts_code:
                            continue
                        stock_code = ts_code.split(".")[0]
                        all_stocks_basic_info[stock_code] = {
                            "stock_name": row.get("name", ""),
                            "industry": row.get("industry", ""),
                            "market": ts_code.split(".")[1],
                            "list_date_str": row.get("list_date", "")
                        }
            except Exception as e:
                result["errors"].append(f"Failed to fetch all stocks basic info: {str(e)}")
                return result
            
            for stock_code in unique_stock_codes:
                result["total_processed"] += 1
                try:
                    stock_info = all_stocks_basic_info.get(stock_code)
                    if not stock_info:
                        continue
                    
                    stock_name = stock_info["stock_name"]
                    industry = stock_info["industry"]
                    market = stock_info["market"]
                    list_date = None
                    list_date_str = stock_info["list_date_str"]
                    if list_date_str:
                        try:
                            list_date = datetime.strptime(str(list_date_str), "%Y%m%d").date()
                        except:
                            pass
                    
                    existing_stock = db.query(models.StockBasicInfo).filter(
                        models.StockBasicInfo.stock_code == stock_code
                    ).first()
                    
                    if existing_stock:
                        if stock_name and existing_stock.stock_name != stock_name:
                            existing_stock.stock_name = stock_name
                        if industry and existing_stock.industry != industry:
                            existing_stock.industry = industry
                        if market and existing_stock.market != market:
                            existing_stock.market = market
                        if list_date and existing_stock.list_date != list_date:
                            existing_stock.list_date = list_date
                        existing_stock.updated_at = datetime.utcnow()
                        result["updated_stocks"] += 1
                    else:
                        new_stock = models.StockBasicInfo(
                            stock_code=stock_code,
                            stock_name=stock_name,
                            industry=industry,
                            market=market,
                            list_date=list_date
                        )
                        db.add(new_stock)
                        result["new_stocks"] += 1
                    
                    db.commit()
                        
                except Exception as e:
                    result["errors"].append(f"Stock {stock_code}: {str(e)}")
                    db.rollback()
                    
        except Exception as e:
            result["errors"].append(f"Sync process error: {str(e)}")
            
        return result

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
            
            self._sync_stock_basic_info_from_daily_data(market_data_list, db)

        except Exception as e:
            errors.append(f"API error: {str(e)}")
            raise

        return success_count, fail_count, errors

    def _is_date_synced_today(self, db: Session, trade_date: date) -> bool:
        """检查指定日期是否在今天已成功同步过"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        synced_log = db.query(models.SyncLog).filter(
            models.SyncLog.trade_date == trade_date,
            models.SyncLog.status == "success",
            models.SyncLog.log_type == "daily_sync",
            models.SyncLog.created_at >= today_start
        ).first()
        return synced_log is not None

    def _get_date_sync_status(self, db: Session, trade_date: date) -> dict:
        """获取指定日期的同步状态"""
        # 检查是否已有数据
        existing_count = crud.get_market_data_count_by_date(db, trade_date)
        if existing_count > 0:
            return {"status": "completed", "reason": "has_data"}
        
        # 检查今天是否已成功同步过
        if self._is_date_synced_today(db, trade_date):
            return {"status": "completed_today", "reason": "synced_today"}
        
        # 检查最近的同步记录
        recent_log = db.query(models.SyncLog).filter(
            models.SyncLog.trade_date == trade_date,
            models.SyncLog.log_type == "daily_sync"
        ).order_by(models.SyncLog.created_at.desc()).first()
        
        if recent_log:
            if recent_log.status == "failed":
                # 检查失败时间，避免频繁重试
                hours_since_failure = (datetime.now() - recent_log.created_at).total_seconds() / 3600
                if hours_since_failure < 1:  # 1小时内不重试
                    return {"status": "failed_recently", "reason": "failed_recently", "hours_since": hours_since_failure}
                else:
                    return {"status": "failed", "reason": "failed_before", "hours_since": hours_since_failure}
            elif recent_log.status == "success":
                return {"status": "completed", "reason": "synced_before"}
        
        return {"status": "pending", "reason": "never_synced"}

    def _should_sync_date(self, db: Session, trade_date: date) -> tuple[bool, str]:
        """判断是否应该同步指定日期"""
        sync_status = self._get_date_sync_status(db, trade_date)
        status = sync_status["status"]
        reason = sync_status["reason"]
        
        if status == "completed":
            return False, f"已完成 ({reason})"
        elif status == "completed_today":
            return False, f"今日已同步"
        elif status == "failed_recently":
            return False, f"最近失败 ({reason}, {sync_status.get('hours_since', 0):.1f}小时前)"
        elif status == "failed":
            return True, f"重试失败 ({reason}, {sync_status.get('hours_since', 0):.1f}小时前)"
        else:  # pending
            return True, f"待同步 ({reason})"

    def _try_sync_today(self, db: Session) -> bool:
        """尝试同步今天的数据"""
        today = date.today()
        provider = self._get_provider()
        
        # 检查今天是否是交易日
        if not provider.is_trading_day(today):
            logger.info(f"今天 {today} 不是交易日，跳过今日数据同步")
            return False
        
        # 检查今天是否已经同步过
        if self._is_date_synced_today(db, today):
            logger.info(f"今天 {today} 的数据已同步过，跳过")
            return False
        
        # 尝试同步今天的数据
        try:
            logger.info(f"开始同步今天 {today} 的数据...")
            self._log_to_db(db, "info", f"开始同步今天 {today} 的数据")
            
            s, f, errors = self._fetch_and_save_market_data(today, db)
            
            # 记录同步日志
            crud.create_sync_log(
                db,
                trade_date=today,
                status="success" if f == 0 else "failed",
                success_count=s,
                fail_count=f,
                error_detail="; ".join(errors) if errors else None,
                source="maintenance",
                log_type="daily_sync",
                message=f"今日数据同步: {s}成功, {f}失败"
            )
            
            if f == 0:
                logger.info(f"今天 {today} 的数据同步成功: {s} 条")
                self._log_to_db(db, "info", f"今天 {today} 的数据同步成功: {s} 条")
                return True
            else:
                logger.warning(f"今天 {today} 的数据同步部分失败: {f} 条失败")
                return False
                
        except Exception as e:
            error_msg = f"同步今天 {today} 数据失败: {str(e)}"
            logger.error(error_msg)
            
            # 记录失败日志
            crud.create_sync_log(
                db,
                trade_date=today,
                status="failed",
                success_count=0,
                fail_count=0,
                error_detail=str(e),
                source="maintenance",
                log_type="daily_sync",
                message=error_msg
            )
            
            self._log_to_db(db, "error", error_msg)
            return False

    def _sync_earliest_missing_date(self, db: Session) -> dict:
        """同步最早的缺失日期数据"""
        provider = self._get_provider()
        
        # 获取最早股票日期
        earliest_date = crud.get_earliest_batch_stock_date(db)
        if earliest_date is None:
            return {"success": False, "message": "No batch stocks found"}
        
        # 计算同步范围
        start_date = earliest_date - timedelta(days=self.lookback_days)
        end_date = date.today()
        
        # 获取所有交易日
        trading_days = provider.get_trading_days(start_date, end_date)
        
        # 找出最早的需要同步的日期
        for trade_date in trading_days:
            # 使用新的状态检查逻辑
            should_sync, reason = self._should_sync_date(db, trade_date)
            
            if not should_sync:
                logger.info(f"日期 {trade_date} 跳过: {reason}")
                continue
            
            # 尝试同步这个日期
            try:
                logger.info(f"开始同步历史数据 {trade_date} ({reason})...")
                self._log_to_db(db, "info", f"开始同步历史数据 {trade_date} ({reason})")
                
                s, f, errors = self._fetch_and_save_market_data(trade_date, db)
                
                # 记录同步日志
                crud.create_sync_log(
                    db,
                    trade_date=trade_date,
                    status="success" if f == 0 else "failed",
                    success_count=s,
                    fail_count=f,
                    error_detail="; ".join(errors) if errors else None,
                    source="maintenance",
                    log_type="daily_sync",
                    message=f"历史数据同步 {trade_date}: {s}成功, {f}失败"
                )
                
                result = {
                    "success": f == 0,
                    "trade_date": str(trade_date),
                    "success_count": s,
                    "fail_count": f,
                    "errors": errors,
                    "reason": reason
                }
                
                if f == 0:
                    logger.info(f"历史数据 {trade_date} 同步成功: {s} 条")
                    self._log_to_db(db, "info", f"历史数据 {trade_date} 同步成功: {s} 条")
                else:
                    logger.warning(f"历史数据 {trade_date} 同步部分失败: {f} 条失败")
                
                return result
                
            except Exception as e:
                error_msg = f"同步历史数据 {trade_date} 失败: {str(e)}"
                logger.error(error_msg)
                
                # 记录失败日志
                crud.create_sync_log(
                    db,
                    trade_date=trade_date,
                    status="failed",
                    success_count=0,
                    fail_count=0,
                    error_detail=str(e),
                    source="maintenance",
                    log_type="daily_sync",
                    message=error_msg
                )
                
                self._log_to_db(db, "error", error_msg)
                
                return {
                    "success": False,
                    "trade_date": str(trade_date),
                    "error": str(e),
                    "reason": reason
                }
        
        return {"success": True, "message": "所有历史数据已同步完成"}

    def run_sync(self) -> dict[str, Any]:
        """执行智能增量同步：优先今日数据，然后历史数据"""
        self._is_running = True
        db = SessionLocal()
        results = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": False,
            "today_sync": {},
            "historical_sync": {},
            "errors": [],
        }

        self._log_to_db(db, "info", "开始智能增量同步")

        try:
            # 步骤1: 尝试同步今天的数据
            logger.info("步骤1: 尝试同步今天的数据...")
            self._log_to_db(db, "info", "步骤1: 尝试同步今天的数据")
            
            today_success = self._try_sync_today(db)
            results["today_sync"] = {
                "success": today_success,
                "date": str(date.today())
            }
            
            # 步骤2: 如果今天同步失败或不是交易日，同步历史数据
            if not today_success:
                logger.info("步骤2: 开始同步历史数据...")
                self._log_to_db(db, "info", "步骤2: 开始同步历史数据")
                
                historical_result = self._sync_earliest_missing_date(db)
                results["historical_sync"] = historical_result
                
                if historical_result.get("success"):
                    results["success"] = True
                    logger.info("历史数据同步成功")
                else:
                    results["success"] = False
                    results["errors"].append(historical_result.get("error", "Unknown error"))
            else:
                # 今天同步成功，尝试再同步一个历史日期
                logger.info("步骤2: 今日数据同步成功，尝试同步历史数据...")
                self._log_to_db(db, "info", "步骤2: 今日数据同步成功，尝试同步历史数据")
                
                historical_result = self._sync_earliest_missing_date(db)
                results["historical_sync"] = historical_result
                results["success"] = True

        except Exception as e:
            results["error"] = str(e)
            self._last_error = str(e)
            logger.error(f"Market data maintenance error: {e}")
            self._log_to_db(db, "error", f"智能增量同步异常: {str(e)}", {"error": str(e)})
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