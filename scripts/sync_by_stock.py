#!/usr/bin/env python3
"""
按个股同步历史数据
- 遍历 batch_stocks 中的股票
- 调用 pro.query('daily', ...) 获取历史数据
- 写入本地数据库
"""

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tushare as ts
from app import crud
from app.config import DEFAULT_MARKET_TYPE_STOCK
from app.config_loader import load_app_config
from app.database import SessionLocal
from app.models import BatchStock


TUSHARE_TOKEN = None


def get_tushare_pro():
    global TUSHARE_TOKEN
    if TUSHARE_TOKEN is None:
        config = load_app_config()
        TUSHARE_TOKEN = config.get("market_data", {}).get("tushare", {}).get("token")
        if not TUSHARE_TOKEN:
            raise ValueError("Tushare token not found in config")
    return ts.pro_api(TUSHARE_TOKEN)


def normalize_ts_code(stock_code: str) -> str:
    """将股票代码转换为 Tushare 格式"""
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


def sync_stock_history(db, pro, stock: BatchStock, start_date: date, end_date: date) -> tuple[int, int]:
    """同步单只股票的历史数据"""
    success_count = 0
    fail_count = 0
    ts_code = normalize_ts_code(stock.stock_code)

    try:
        df = pro.query(
            "daily",
            ts_code=ts_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        if df is None or len(df) == 0:
            return 0, 1

        records = []
        for _, row in df.iterrows():
            records.append({
                "trade_date": datetime.strptime(str(row["trade_date"]), "%Y%m%d").date(),
                "symbol": stock.stock_code,
                "market_type": DEFAULT_MARKET_TYPE_STOCK,
                "close_price": float(row["close"]),
                "open_price": float(row["open"]) if row["open"] else None,
                "high_price": float(row["high"]) if row["high"] else None,
                "low_price": float(row["low"]) if row["low"] else None,
                "volume": int(row["vol"]) if row["vol"] else None,
                "source": "tushare",
            })

        if records:
            success_count = crud.upsert_market_data_batch(db, records)

    except Exception as e:
        print(f"    失败: {e}")
        fail_count = 1

    return success_count, fail_count


def main():
    parser = argparse.ArgumentParser(description="按个股同步历史数据")
    parser.add_argument("--days", type=int, default=60, help="回溯天数 (默认60天)")
    parser.add_argument("--delay", type=float, default=0.2, help="每次请求间隔秒数 (默认0.2秒)")
    parser.add_argument("--batch-id", type=int, help="只同步指定批次的股票")
    args = parser.parse_args()

    db = SessionLocal()
    end_date = date.today()
    start_date = end_date - timedelta(days=args.days)

    print(f"同步范围: {start_date} 到 {end_date}")
    print(f"请求间隔: {args.delay} 秒")
    print()

    query = db.query(BatchStock)
    if args.batch_id:
        query = query.filter(BatchStock.batch_id == args.batch_id)

    stocks = query.all()
    unique_stocks = {s.stock_code: s for s in stocks}
    print(f"发现 {len(unique_stocks)} 只股票需要同步")
    print()

    pro = get_tushare_pro()
    total_success = 0
    total_fail = 0

    for idx, (stock_code, stock) in enumerate(unique_stocks.items(), 1):
        print(f"[{idx}/{len(unique_stocks)}] 同步 {stock_code}...", end=" ", flush=True)

        success, fail = sync_stock_history(db, pro, stock, start_date, end_date)
        total_success += success
        total_fail += fail

        if success > 0:
            print(f"成功 ({success} 条)")
        else:
            print(f"失败")

        if idx % 10 == 0:
            db.commit()

        time.sleep(args.delay)

    db.commit()
    db.close()

    print()
    print(f"同步完成! 总计: {total_success} 成功, {total_fail} 失败")


if __name__ == "__main__":
    main()