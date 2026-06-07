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
        self._trading_days_cache: Optional[list[date]] = None
        self._trading_days_cache_time: Optional[datetime] = None
        self._trading_days_cache_key: Optional[tuple] = None

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

    def _fetch_and_save_market_data_by_stock(
        self, trade_date: date, stock_code: str, db, max_retries: int = 5
    ) -> tuple[int, int, list[str]]:
        """使用个股接口获取当日数据（支持指数退避重试）"""
        success_count = 0
        fail_count = 0
        errors = []
        
        for attempt in range(max_retries):
            try:
                pro = self._get_pro_api()
                records = self._fetch_stock_daily(pro, stock_code, trade_date, trade_date)
                
                if records:
                    count = crud.upsert_market_data_batch(db, records)
                    success_count += count
                    db.commit()
                    return success_count, fail_count, errors
                else:
                    return 0, 0, []
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_seconds = 60 * (2 ** attempt)
                    error_msg = f"同步股票 {stock_code} {trade_date} 失败 (尝试 {attempt + 1}/{max_retries})，{wait_seconds}秒后重试: {str(e)}"
                    logger.warning(error_msg)
                    time.sleep(wait_seconds)
                else:
                    error_msg = f"同步股票 {stock_code} {trade_date} 最终失败 (已重试 {max_retries} 次): {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    fail_count += 1
                    return success_count, fail_count, errors
        
        return success_count, fail_count, errors

    def _fetch_and_save_market_data_by_stock_range(
        self, stock_code: str, start_date: date, end_date: date, db, max_retries: int = 5
    ) -> tuple[int, int, list[str]]:
        """使用个股接口获取某只股票在指定日期范围内的数据（支持指数退避重试）"""
        success_count = 0
        fail_count = 0
        errors = []
        
        for attempt in range(max_retries):
            try:
                pro = self._get_pro_api()
                records = self._fetch_stock_daily(pro, stock_code, start_date, end_date)
                
                if records:
                    count = crud.upsert_market_data_batch(db, records)
                    success_count += count
                    db.commit()
                    return success_count, fail_count, errors
                else:
                    return 0, 0, []
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_seconds = 60 * (2 ** attempt)
                    error_msg = f"同步股票 {stock_code} ({start_date}~{end_date}) 失败 (尝试 {attempt + 1}/{max_retries})，{wait_seconds}秒后重试: {str(e)}"
                    logger.warning(error_msg)
                    time.sleep(wait_seconds)
                else:
                    error_msg = f"同步股票 {stock_code} ({start_date}~{end_date}) 最终失败 (已重试 {max_retries} 次): {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    fail_count += 1
                    return success_count, fail_count, errors
        
        return success_count, fail_count, errors

    def _fetch_and_save_market_data(self, trade_date: date, db) -> tuple[int, int, list[str]]:
        """使用个股接口获取当日数据（替代批量接口，避免频率限制）"""
        all_stocks = crud.get_all_batch_stock_codes(db)
        if not all_stocks:
            return 0, 0, ["No batch stocks found"]

        total_success = 0
        total_fail = 0
        all_errors = []

        for stock_code in all_stocks:
            try:
                s, f, errors = self._fetch_and_save_market_data_by_stock(trade_date, stock_code, db)
                total_success += s
                total_fail += f
                all_errors.extend(errors)
                
                time.sleep(1)
                
            except Exception as e:
                error_msg = f"同步股票 {stock_code} {trade_date} 异常: {str(e)}"
                logger.error(error_msg)
                all_errors.append(error_msg)
                total_fail += 1

        return total_success, total_fail, all_errors

    def _fetch_and_save_market_data_batch_by_stock(
        self, start_date: date, end_date: date, db
    ) -> tuple[int, int, list[str]]:
        """按股票批量获取指定日期范围内的数据（优化：减少接口调用次数）"""
        all_stocks = crud.get_all_batch_stock_codes(db)
        if not all_stocks:
            return 0, 0, ["No batch stocks found"]

        total_success = 0
        total_fail = 0
        all_errors = []

        for stock_code in all_stocks:
            try:
                s, f, errors = self._fetch_and_save_market_data_by_stock_range(
                    stock_code, start_date, end_date, db
                )
                total_success += s
                total_fail += f
                all_errors.extend(errors)
                
                time.sleep(1)
                
            except Exception as e:
                error_msg = f"同步股票 {stock_code} ({start_date}~{end_date}) 异常: {str(e)}"
                logger.error(error_msg)
                all_errors.append(error_msg)
                total_fail += 1

        return total_success, total_fail, all_errors

    def run_batch_api_sync(self, db, trade_date: date) -> dict[str, Any]:
        """批量接口同步：调用 Tushare daily 批量接口获取指定日期的所有股票数据"""
        self._is_running = True
        results = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": False,
            "trade_date": str(trade_date),
            "success_count": 0,
            "fail_count": 0,
            "errors": [],
            "error": None,
        }

        self._log_to_db(db, "info", f"开始批量接口同步: {trade_date}")

        try:
            provider = self._get_provider()
            all_stocks_data = provider.fetch_all_stocks_daily(trade_date)
            
            if not all_stocks_data:
                results["error"] = "未获取到数据（可能是非交易日）"
                results["end_time"] = datetime.now().isoformat()
                self._is_running = False
                self._log_to_db(db, "warning", f"批量接口同步 {trade_date}: 未获取到数据")
                return results

            # 转换为数据库记录格式
            records = []
            for stock_data in all_stocks_data:
                records.append({
                    "trade_date": stock_data.trade_date,
                    "symbol": stock_data.symbol,
                    "market_type": stock_data.market_type,
                    "open_price": stock_data.open_price,
                    "close_price": stock_data.close_price,
                    "high_price": stock_data.high_price,
                    "low_price": stock_data.low_price,
                    "volume": stock_data.volume,
                    "source": stock_data.source,
                })

            # 批量 upsert
            count = crud.upsert_market_data_batch(db, records)
            db.commit()
            
            results["success_count"] = count
            results["success"] = True

            logger.info(f"批量接口同步完成: {count} 条数据 ({trade_date})")
            self._log_to_db(
                db, "info",
                f"批量接口同步完成: {count} 条数据 ({trade_date})",
                {"trade_date": str(trade_date), "count": count}
            )

            # 记录同步日志
            crud.create_sync_log(
                db,
                trade_date=trade_date,
                status="success",
                success_count=count,
                fail_count=0,
                source="batch_api",
                log_type="batch_api_sync",
                message=f"批量接口同步 {trade_date}: {count} 条数据"
            )

        except Exception as e:
            results["error"] = str(e)
            self._last_error = str(e)
            logger.error(f"Batch API sync error: {e}")
            self._log_to_db(db, "error", f"批量接口同步异常: {str(e)}", {"error": str(e)})
        finally:
            results["end_time"] = datetime.now().isoformat()
            self._is_running = False

        return results

    def run_manual_full_sync(self, db, start_date: Optional[date] = None, end_date: Optional[date] = None) -> dict[str, Any]:
        """手动批量同步：按指定日期范围批量获取股票数据（管理员手动触发）"""
        self._is_running = True
        results = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": False,
            "start_date": None,
            "end_date": None,
            "success_count": 0,
            "fail_count": 0,
            "errors": [],
            "error": None,
        }

        self._log_to_db(db, "info", "开始手动批量同步")

        try:
            # 如果没有指定日期范围，使用默认范围
            if start_date is None:
                earliest_date = crud.get_earliest_batch_stock_date(db)
                if earliest_date is None:
                    results["error"] = "No batch stocks found"
                    results["end_time"] = datetime.now().isoformat()
                    self._is_running = False
                    self._log_to_db(db, "warning", "未找到批次股票，无法同步")
                    return results
                start_date = earliest_date - timedelta(days=self.lookback_days)
            
            if end_date is None:
                end_date = date.today()

            results["start_date"] = str(start_date)
            results["end_date"] = str(end_date)

            # 按股票批量获取指定日期范围内的数据
            s, f, errors = self._fetch_and_save_market_data_batch_by_stock(
                start_date, end_date, db
            )
            results["success_count"] = s
            results["fail_count"] = f
            results["errors"] = errors[:100]
            results["success"] = True

            logger.info(f"手动批量同步完成: {s} 条数据, {f} 条失败")
            self._log_to_db(
                db, "info",
                f"手动批量同步完成: {s} 条数据 ({start_date} ~ {end_date})",
                {"start_date": str(start_date), "end_date": str(end_date), "success": s, "fail": f}
            )

            # 记录同步日志
            crud.create_sync_log(
                db,
                trade_date=end_date,
                status="success" if f == 0 else "partial",
                success_count=s,
                fail_count=f,
                error_detail="; ".join(errors) if errors else None,
                source="manual",
                log_type="manual_sync",
                message=f"手动批量同步 ({start_date} ~ {end_date}): {s} 成功, {f} 失败"
            )

        except Exception as e:
            results["error"] = str(e)
            self._last_error = str(e)
            logger.error(f"Manual sync error: {e}")
            self._log_to_db(db, "error", f"手动批量同步异常: {str(e)}", {"error": str(e)})
        finally:
            results["end_time"] = datetime.now().isoformat()
            self._is_running = False

        return results

    def _get_trading_days_cached(self, provider, start_date: date, end_date: date) -> list[date]:
        """获取交易日列表（带缓存，避免频繁调用 trade_cal 接口）"""
        cache_key = (start_date, end_date)
        now = datetime.now()
        
        # 如果缓存有效（5分钟内相同查询），直接返回缓存
        if (self._trading_days_cache_key == cache_key and 
            self._trading_days_cache_time and 
            self._trading_days_cache is not None and
            (now - self._trading_days_cache_time).total_seconds() < 300):
            return list(self._trading_days_cache)
        
        # 调用接口获取交易日
        trading_days = provider.get_trading_days(start_date, end_date)
        
        # 更新缓存
        self._trading_days_cache = list(trading_days)
        self._trading_days_cache_time = now
        self._trading_days_cache_key = cache_key
        
        return trading_days

    def _get_days_to_sync(self, start_date: date, end_date: date, db) -> list[date]:
        provider = self._get_provider()
        existing_dates = set(crud.get_existing_market_data_dates(db, start_date, end_date))
        trading_days = self._get_trading_days_cached(provider, start_date, end_date)
        days_to_sync = [d for d in trading_days if d not in existing_dates]
        return days_to_sync

    def run_sync(self) -> dict[str, Any]:
        """执行每日增量同步（优化：按股票批量获取，减少接口调用次数）"""
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

            # 优化：按股票批量获取所有缺失日期的数据，而不是逐天获取
            # 原逻辑：N只股票 × M天 = N×M次调用
            # 新逻辑：N只股票 × 1次调用 = N次调用
            try:
                s, f, errors = self._fetch_and_save_market_data_batch_by_stock(
                    start_date, end_date, db
                )
                results["success_count"] = s
                results["fail_count"] = f
                results["errors"] = errors[:100]
                results["success"] = True

                logger.info(f"批量同步完成: {s} 条数据, {f} 条失败")
                self._log_to_db(
                    db, "info",
                    f"每日同步完成: {s} 条数据 ({len(days_to_sync)} 个交易日)",
                    {"total_days": results["total_days"], "success": s, "fail": f}
                )

                # 记录整体同步日志
                crud.create_sync_log(
                    db,
                    trade_date=end_date,
                    status="success" if f == 0 else "partial",
                    success_count=s,
                    fail_count=f,
                    error_detail="; ".join(errors) if errors else None,
                    source="maintenance",
                    log_type="batch_sync",
                    message=f"批量同步 {len(days_to_sync)} 个交易日: {s} 成功, {f} 失败"
                )

            except Exception as e:
                error_msg = f"批量同步失败: {str(e)}"
                logger.error(error_msg)
                results["error"] = error_msg
                results["errors"].append(error_msg)
                self._last_error = error_msg
                self._log_to_db(db, "error", error_msg)

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

    def _is_today_synced(self, db) -> bool:
        """检查今天是否已经成功同步过"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        logs = db.query(models.SyncLog).filter(
            models.SyncLog.created_at >= today_start,
            models.SyncLog.status.in_(["success", "partial"]),
            models.SyncLog.log_type.in_(["daily_sync", "batch_sync", "manual_sync"])
        ).all()
        
        return len(logs) > 0

    def _worker(self):
        """后台工作线程：每天17点执行一次同步"""
        while not self._stop_event.is_set():
            now = datetime.now()
            target_time = now.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # 计算到下一个17点的时间
            if now >= target_time:
                # 已经过了今天的17点，计算明天的17点
                next_run = target_time + timedelta(days=1)
            else:
                # 还没到今天的17点
                next_run = target_time
            
            wait_seconds = (next_run - now).total_seconds()
            
            logger.info(f"下次同步时间: {next_run.isoformat()}, 等待 {wait_seconds/3600:.1f} 小时")
            self._stop_event.wait(wait_seconds)
            
            if self._stop_event.is_set():
                break
            
            # 执行同步前检查今天是否已经同步过
            db = SessionLocal()
            try:
                if self._is_today_synced(db):
                    logger.info("今天已经执行过同步任务，跳过")
                    self._log_to_db(db, "info", "今天已经执行过同步任务，跳过自动同步")
                    db.close()
                    continue
                
                logger.info("Starting daily market data maintenance at 17:00")
                self._log_to_db(db, "info", "每日17点自动同步开始执行")
                db.close()
                
                self.run_full_sync()
            except Exception as e:
                logger.error(f"Maintenance worker error: {e}")
                self._last_error = str(e)
                self._log_to_db(db, "error", f"每日自动同步异常: {str(e)}")
                db.close()

    def start(self, run_immediately: bool = True):
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
        
        # 服务器启动时立即执行一次同步（如果今天还没同步过）
        if run_immediately:
            db = SessionLocal()
            try:
                if self._is_today_synced(db):
                    logger.info("今天已经执行过同步任务，跳过启动时同步")
                    self._log_to_db(db, "info", "今天已经执行过同步任务，跳过启动时同步")
                else:
                    logger.info("服务器启动，立即执行同步任务")
                    self._log_to_db(db, "info", "服务器启动，立即执行同步任务")
                    db.close()
                    self.run_full_sync()
            except Exception as e:
                logger.error(f"启动时同步失败: {e}")
                self._log_to_db(db, "error", f"启动时同步失败: {str(e)}")
            finally:
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