"""
指数成分权重同步
================
同步沪深300/中证500/中证1000 的最新月末成分权重。
来源: Tushare index_weight（需 2000 积分）
"""

import time
import structlog
import pandas as pd
from typing import Optional

from core.database import db_session
from jobs.sync_base import report_progress, write_watermark

log = structlog.get_logger("sync_index_weight")

# 三大宽基指数
INDEX_CODES = {
    "399300.SZ": "沪深300",
    "000905.SH": "中证500",
    "000852.SH": "中证1000",
}


def sync_index_weight(ts_source, task_id: Optional[str] = None) -> dict:
    """
    同步三大指数最新月末成分权重。

    策略：每次只拉取最新月末数据（index_weight 不传 trade_date 则返回最新），
    按 (index_code, con_code, trade_date) 三主键 upsert。
    """
    t_start = time.time()
    total_rows = 0
    results = []
    latest_date_str = None

    for idx, (idx_code, idx_name) in enumerate(INDEX_CODES.items()):
        if task_id:
            report_progress(task_id, idx, len(INDEX_CODES),
                            f"正在同步 {idx_name} 成分权重...")
        try:
            import data_sources.tushare_source as tushare_module

            # 用默认参数捕获当前 idx_code，避免闭包陷阱
            @tushare_module.with_tushare_retry(max_retries=2, delay=2.0)
            def _fetch(_code=idx_code):
                return ts_source.pro.index_weight(index_code=_code)

            df = _fetch()
            if df is None or df.empty:
                log.warning("index_weight_empty", index=idx_name)
                results.append(f"{idx_name}: 0条")
                continue

            # 只保留最新月末数据
            latest_date = df["trade_date"].max()
            df = df[df["trade_date"] == latest_date].copy()

            # 记录水位日期（取所有指数中最新的）
            ld = str(latest_date)
            if latest_date_str is None or ld > latest_date_str:
                latest_date_str = ld

            # 写入 DB
            rows = _upsert_index_weight(idx_code, df)
            total_rows += rows
            results.append(f"{idx_name}: {rows}条")
            log.info("index_weight_synced", index=idx_name, rows=rows, date=latest_date)

            time.sleep(1.0)  # API 限频

        except Exception as e:
            log.error("index_weight_failed", index=idx_name, error=str(e))
            results.append(f"{idx_name}: ❌{str(e)[:30]}")

    duration = round(time.time() - t_start, 1)

    # 只有实际写入数据时才推进水位
    if total_rows > 0:
        # 水位日期用实际拉取到的最新月末日期
        if not latest_date_str:
            from utils.trade_date import resolve_end_date
            latest_date_str = resolve_end_date().replace("-", "")
        write_watermark("index_weight", "any", latest_date_str, t_start, "success")
    else:
        log.warning("index_weight_no_data_watermark_skip")
    log.info("sync_index_weight_done", total=total_rows, duration=duration)

    if task_id:
        report_progress(task_id, len(INDEX_CODES), len(INDEX_CODES),
                        f"指数成分权重同步完成 ({total_rows}条, {duration}s)")

    return {"rows": total_rows, "detail": results}


def _upsert_index_weight(index_code: str, df: pd.DataFrame) -> int:
    """批量 upsert 单个指数的成分权重"""
    from sqlalchemy import text

    written = 0
    with db_session() as db:
        for _, row in df.iterrows():
            try:
                trade_date = str(row.get("trade_date", ""))
                if len(trade_date) == 8:
                    trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"

                con_code = row.get("con_code", "")
                weight = row.get("weight")
                if not con_code or not trade_date:
                    continue

                try:
                    weight = float(weight) if weight is not None else None
                except (ValueError, TypeError):
                    weight = None

                db.execute(text("""
                    INSERT INTO index_weight (index_code, con_code, trade_date, weight)
                    VALUES (:index_code, :con_code, :trade_date, :weight)
                    ON CONFLICT(index_code, con_code, trade_date) DO UPDATE SET
                        weight=excluded.weight
                """), {
                    "index_code": index_code,
                    "con_code": con_code,
                    "trade_date": trade_date,
                    "weight": weight,
                })
                written += 1
            except Exception as e:
                log.debug("index_weight_row_skip", error=str(e))

    return written


def backfill_index_weight(
    ts_source, start_date: str = "20180101", end_date: str = None,
    task_id: Optional[str] = None,
) -> dict:
    """
    回填指数成分历史权重（S6 修复）。

    按月末日期逐月拉取 index_weight(trade_date=YYYYMMDD)，
    覆盖 start_date 到 end_date 之间的所有月末。

    Args:
        ts_source: Tushare 数据源实例
        start_date: 起始日期（YYYYMMDD），默认 20180101
        end_date: 结束日期（YYYYMMDD），默认当前日期
        task_id: 异步任务 ID（可选，用于进度上报）
    """
    import data_sources.tushare_source as tushare_module
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta

    if end_date is None:
        from utils.trade_date import resolve_end_date
        end_date = resolve_end_date().replace("-", "")

    # 生成月末日期序列
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    month_ends = []
    cursor = start.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
    while cursor <= end:
        month_ends.append(cursor.strftime("%Y%m%d"))
        cursor += relativedelta(months=1)

    total_rows = 0
    total_steps = len(month_ends) * len(INDEX_CODES)
    step = 0

    for td in month_ends:
        for idx_code, idx_name in INDEX_CODES.items():
            step += 1
            if task_id:
                report_progress(task_id, step, total_steps,
                                f"回填 {idx_name} {td[:4]}-{td[4:6]}...")
            try:
                @tushare_module.with_tushare_retry(max_retries=2, delay=2.0)
                def _fetch(_code=idx_code, _td=td):
                    return ts_source.pro.index_weight(
                        index_code=_code, trade_date=_td
                    )

                df = _fetch()
                if df is None or df.empty:
                    continue

                rows = _upsert_index_weight(idx_code, df)
                total_rows += rows
                if rows > 0:
                    log.debug("backfill_index_weight", index=idx_name,
                              date=td, rows=rows)

                time.sleep(0.5)  # API 限频（回填量大，适当降速）

            except Exception as e:
                log.warning("backfill_index_weight_failed",
                            index=idx_name, date=td, error=str(e))

    log.info("backfill_index_weight_done", total=total_rows,
             months=len(month_ends))
    return {"rows": total_rows, "months": len(month_ends)}
