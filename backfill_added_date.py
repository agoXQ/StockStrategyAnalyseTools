#!/usr/bin/env python3
"""补全 batch_stocks 表中缺失的 added_date"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models
from sqlalchemy import update

def backfill_added_date():
    db = SessionLocal()
    try:
        # 查询所有 added_date 为 NULL 的 batch_stocks
        stocks_without_date = (
            db.query(models.BatchStock)
            .filter(models.BatchStock.added_date.is_(None))
            .all()
        )

        if not stocks_without_date:
            print("没有需要补全的记录")
            return

        print(f"找到 {len(stocks_without_date)} 条需要补全的记录")

        # 按 batch_id 分组，批量查询 batch_date
        batch_ids = set(s.batch_id for s in stocks_without_date)
        batches = db.query(models.Batch).filter(
            models.Batch.id.in_(batch_ids)
        ).all()
        batch_date_map = {b.id: b.batch_date for b in batches}

        updated_count = 0
        for stock in stocks_without_date:
            batch_date = batch_date_map.get(stock.batch_id)
            if batch_date:
                stock.added_date = batch_date
                updated_count += 1
            else:
                print(f"警告: batch_id={stock.batch_id} 不存在，stock_code={stock.stock_code}")

        db.commit()
        print(f"成功补全 {updated_count} 条记录的 added_date")

    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    backfill_added_date()