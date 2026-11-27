"""
批量数据加载
============
一次 SQL 批量拉取所有股票的截面因子原始数据。
比逐只循环快 10-20 倍。
"""
import structlog
import numpy as np
import pandas as pd
from datetime import date as _date
from typing import List
from collections import defaultdict

log = structlog.get_logger(__name__)

from settings import TRADING_DAYS


def _estimated_ann_date(report_date_str: str) -> str:
    """A股法定最晚财报披露截止日（保守估计）。

    ann_date 缺失时，用报告期推算公告可见的最早安全日期：
      Q1 (03-31) → 04-30 | Q2 (06-30) → 08-31
      Q3 (09-30) → 10-31 | Q4 (12-31) → 次年 04-30
    """
    rd = _date.fromisoformat(str(report_date_str)[:10])
    m = rd.month
    if m == 3:
        return f"{rd.year}-04-30"
    elif m == 6:
        return f"{rd.year}-08-31"
    elif m == 9:
        return f"{rd.year}-10-31"
    else:  # 12
        return f"{rd.year + 1}-04-30"


def load_factor_df(codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    批量拉取因子数据，返回宽表 DataFrame。

    列: code, pe_ttm, pb, turnover_rate, momentum_20, volatility_20,
        roe, revenue_growth, net_profit_growth, holder_change_rate, industry
    """
    # 信任边界：外部传入的 codes 可能无后缀，统一规范化为 DB 格式
    from utils.asset_type import to_ts_code
    codes = [to_ts_code(c) for c in codes]
    try:
        from core.database import db_session
        from models.quant_data import StockDailyFactor, StockDailyBar, StockFinancial
        from sqlalchemy import and_, or_, func, case, extract

        records = {}
        with db_session() as db:
            # ── 1. 估值因子（StockDailyFactor 最新截面）──
            subq = (
                db.query(
                    StockDailyFactor.code,
                    func.max(StockDailyFactor.trade_date).label("max_date"),
                )
                .filter(
                    StockDailyFactor.code.in_(codes),
                    StockDailyFactor.trade_date >= start_date,
                    StockDailyFactor.trade_date <= end_date,
                )
                .group_by(StockDailyFactor.code)
                .subquery()
            )
            factor_rows = (
                db.query(StockDailyFactor)
                .join(subq, and_(
                    StockDailyFactor.code == subq.c.code,
                    StockDailyFactor.trade_date == subq.c.max_date,
                ))
                .all()
            )
            for r in factor_rows:
                records.setdefault(r.code, {})
                records[r.code].update({
                    "pe_ttm": r.pe_ttm,
                    "pb": r.pb,
                    "turnover_rate": r.turnover_rate,
                    "total_mv": r.total_mv,
                    "circ_mv": r.circ_mv,
                    "dv_ttm": r.dv_ttm,
                })

            # ── 2. 动量 + 波动（StockDailyBar 批量，取最近 20 日，前复权）──
            bar_subq = (
                db.query(
                    StockDailyBar.code,
                    StockDailyBar.trade_date,
                    StockDailyBar.close,
                    StockDailyBar.adj_factor,
                )
                .filter(
                    StockDailyBar.code.in_(codes),
                    StockDailyBar.trade_date >= start_date,
                    StockDailyBar.trade_date <= end_date,
                )
                .order_by(StockDailyBar.code, StockDailyBar.trade_date.desc())
                .all()
            )
            # 按 code 分组，使用前复权价格（close * adj_factor / latest_factor）
            bar_map = defaultdict(list)
            adj_map = defaultdict(list)
            for row in bar_subq:
                if row.close is not None:
                    bar_map[row.code].append(float(row.close))
                    adj_map[row.code].append(float(row.adj_factor) if row.adj_factor else 1.0)

            for code, closes in bar_map.items():
                if len(closes) >= 2:
                    closes_raw = np.array(closes[:20])
                    adjs = np.array(adj_map[code][:20])
                    # 前复权：close * adj_factor / latest_adj_factor
                    latest_adj = adjs[0] if adjs[0] != 0 else 1.0
                    closes_arr = closes_raw * adjs / latest_adj
                    if len(closes_arr) >= 2:
                        rev = closes_arr[::-1]
                        returns_20 = np.diff(rev) / np.where(rev[:-1] != 0, rev[:-1], np.nan)
                        returns_20 = returns_20[~np.isnan(returns_20)]
                        records.setdefault(code, {})
                        records[code]["momentum_20"] = float(closes_arr[0] / closes_arr[-1] - 1) \
                            if closes_arr[-1] != 0 else 0.0
                        # reversal = 近期收益取反（A 股短期反转效应）
                        records[code]["reversal_20"] = -records[code]["momentum_20"]
                        vol_std = float(np.std(returns_20)) if len(returns_20) > 1 else 0.0
                        records[code]["volatility_20"] = vol_std * np.sqrt(TRADING_DAYS)

            # ── 3. 财务因子（StockFinancial PIT：仅使用已公告的最新季报）──
            # PIT 逻辑：ann_date <= end_date（公告日不晚于查询日）
            # 兼容老数据：ann_date 为空时，用法定最晚披露截止日估算
            #   Q1(03) → 04-30 | Q2(06) → 08-31 | Q3(09) → 10-31 | Q4(12) → 次年04-30
            _report_month = extract("month", StockFinancial.report_date)
            _report_year = extract("year", StockFinancial.report_date)
            _est_ann = case(
                (_report_month == 3, func.concat(_report_year, "-04-30")),
                (_report_month == 6, func.concat(_report_year, "-08-31")),
                (_report_month == 9, func.concat(_report_year, "-10-31")),
                else_=func.concat(_report_year + 1, "-04-30"),  # Q4: 次年4月30日
            )
            fin_subq = (
                db.query(
                    StockFinancial.code,
                    func.max(StockFinancial.report_date).label("max_date"),
                )
                .filter(
                    StockFinancial.code.in_(codes),
                    # PIT: 只取公告日在查询日期之前的报表
                    or_(
                        StockFinancial.ann_date <= end_date,
                        # 兼容: ann_date 为空时，用法定截止日估算（保守）
                        and_(
                            StockFinancial.ann_date.is_(None),
                            _est_ann <= end_date,
                        ),
                    ),
                )
                .group_by(StockFinancial.code)
                .subquery()
            )
            fin_rows = (
                db.query(StockFinancial)
                .join(fin_subq, and_(
                    StockFinancial.code == fin_subq.c.code,
                    StockFinancial.report_date == fin_subq.c.max_date,
                ))
                .all()
            )
            for r in fin_rows:
                records.setdefault(r.code, {})
                records[r.code].update({
                    "roe": r.roe,
                    "gross_profit_margin": r.gross_profit_margin,
                    "cashflow_oper": r.cashflow_oper if hasattr(r, "cashflow_oper") else None,
                    "debt_to_assets": r.debt_to_assets if hasattr(r, "debt_to_assets") else None,
                    "eps": r.eps if hasattr(r, "eps") else None,
                    "revenue_growth": r.revenue_yoy if hasattr(r, "revenue_yoy") else None,
                    "net_profit_growth": r.net_profit_yoy if hasattr(r, "net_profit_yoy") else None,
                })

            # ── 4. 筹码集中度（StockShareholderCount 最近两期变化率）──
            from models.quant_data import StockShareholderCount
            sh_rows = (
                db.query(
                    StockShareholderCount.code,
                    StockShareholderCount.end_date,
                    StockShareholderCount.holder_num,
                    StockShareholderCount.holder_num_change_rate,
                )
                .filter(
                    StockShareholderCount.code.in_(codes),
                    StockShareholderCount.end_date <= end_date,  # PIT: 仅使用查询日之前的数据
                )
                .order_by(StockShareholderCount.code, StockShareholderCount.end_date.desc())
                .all()
            )
            seen_codes = set()
            for r in sh_rows:
                if r.code in seen_codes:
                    continue
                seen_codes.add(r.code)
                records.setdefault(r.code, {})
                records[r.code]["holder_change_rate"] = (
                    float(r.holder_num_change_rate) if r.holder_num_change_rate is not None else None
                )

            # ── 5. 融资融券 → margin_ratio ──
            from models.quant_data import StockMarginData
            margin_subq = (
                db.query(
                    StockMarginData.code,
                    func.max(StockMarginData.trade_date).label("max_date"),
                )
                .filter(
                    StockMarginData.code.in_(codes),
                    StockMarginData.trade_date <= end_date,  # PIT: 仅使用查询日之前的数据
                )
                .group_by(StockMarginData.code)
                .subquery()
            )
            margin_rows = (
                db.query(StockMarginData)
                .join(margin_subq, and_(
                    StockMarginData.code == margin_subq.c.code,
                    StockMarginData.trade_date == margin_subq.c.max_date,
                ))
                .all()
            )
            for r in margin_rows:
                records.setdefault(r.code, {})
                # circ_mv（流通市值）优先，fallback 到 total_mv（总市值）
                circ_mv = records[r.code].get("circ_mv") or records[r.code].get("total_mv")
                if r.rzye and circ_mv and circ_mv > 0:
                    records[r.code]["margin_ratio"] = r.rzye / (circ_mv * 10000)
                else:
                    records[r.code]["margin_ratio"] = None

            # ── 6. 行业归属 + 名称（StockBasicInfo）──
            from models.quant_data import StockBasicInfo as SBI
            ind_rows = (
                db.query(SBI.code, SBI.industry, SBI.name)
                .filter(SBI.code.in_(codes))
                .all()
            )
            for r in ind_rows:
                records.setdefault(r.code, {})
                if r.industry:
                    records[r.code]["industry"] = r.industry
                if r.name:
                    records[r.code]["name"] = r.name

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame.from_dict(records, orient="index")
        df.index.name = "code"
        df = df.reset_index()
        return df

    except Exception as e:
        log.warning(f"[FactorLoader] load_factor_df error: {e}")
        return pd.DataFrame()


def load_monthly_snapshots(
    codes: list[str],
    start_date: str,
    end_date: str,
    periods: int = 12,
) -> list[dict]:
    """
    按月末截面批量拉取因子数据 + forward return，用于滚动 IC 分析。

    返回 [{period_date, df(code, factor_cols..., fwd_ret)}] × N期
    """
    # 信任边界：外部传入的 codes 可能无后缀，统一规范化为 DB 格式
    from utils.asset_type import to_ts_code
    codes = [to_ts_code(c) for c in codes]
    try:
        from core.database import db_session
        from models.quant_data import StockDailyBar, StockDailyFactor, StockFinancial
        from sqlalchemy import and_, or_, func, case, extract

        with db_session() as db:
            # ── 1. 获取月末日期列表（全局交易日，不依赖单只股票）──
            all_dates = [
                r[0] for r in db.query(StockDailyBar.trade_date)
                .filter(
                    StockDailyBar.trade_date >= start_date,
                    StockDailyBar.trade_date <= end_date,
                )
                .order_by(StockDailyBar.trade_date)
                .distinct()
                .all()
            ]
            if len(all_dates) < 40:
                return []

            # 取每月最后一个交易日
            from collections import defaultdict
            month_map = defaultdict(str)
            for d in all_dates:
                ym = str(d)[:7]  # "2025-03"
                month_map[ym] = str(d)  # 不断更新，最终保留月末

            month_ends = sorted(month_map.values())[-periods - 1:]  # 多取1个用于 fwd_ret
            if len(month_ends) < 3:
                return []

            # ── 2. 批量拉取所有月末截面的收盘价（后复权，F7/R1 修复）──
            price_rows = (
                db.query(StockDailyBar.code, StockDailyBar.trade_date,
                         StockDailyBar.close, StockDailyBar.adj_factor)
                .filter(
                    StockDailyBar.code.in_(codes),
                    StockDailyBar.trade_date.in_(month_ends),
                    StockDailyBar.close.isnot(None),
                )
                .all()
            )
            # {(code, date): close * adj_factor}（后复权，消除除权日虚假跳变）
            price_map = {
                (r.code, str(r.trade_date)):
                    float(r.close) * (float(r.adj_factor) if r.adj_factor else 1.0)
                for r in price_rows
            }

            # ── 3. 批量拉取估值因子（逐月末截面取当月最新）──
            # 一次性拉取区间内全部数据，Python 层按月切片
            all_factor_rows = (
                db.query(
                    StockDailyFactor.code,
                    StockDailyFactor.trade_date,
                    StockDailyFactor.pe_ttm,
                    StockDailyFactor.pb,
                    StockDailyFactor.turnover_rate,
                    StockDailyFactor.total_mv,
                    StockDailyFactor.circ_mv,
                    StockDailyFactor.dv_ttm,
                )
                .filter(
                    StockDailyFactor.code.in_(codes),
                    StockDailyFactor.trade_date >= start_date,
                    StockDailyFactor.trade_date <= end_date,
                )
                .all()
            )
            # 按 code 分组，按日期排序，便于逐月取最新
            from collections import defaultdict as _dd
            factor_by_code = _dd(list)
            for r in all_factor_rows:
                factor_by_code[r.code].append(r)
            for code in factor_by_code:
                factor_by_code[code].sort(key=lambda x: str(x.trade_date))

            # ── 4. 批量拉取财务因子（带 PIT 约束）──
            _report_month = extract("month", StockFinancial.report_date)
            _report_year = extract("year", StockFinancial.report_date)
            _est_ann = case(
                (_report_month == 3, func.concat(_report_year, "-04-30")),
                (_report_month == 6, func.concat(_report_year, "-08-31")),
                (_report_month == 9, func.concat(_report_year, "-10-31")),
                else_=func.concat(_report_year + 1, "-04-30"),
            )
            # 拉取区间内所有可见的财务数据
            all_fin_rows = (
                db.query(StockFinancial)
                .filter(
                    StockFinancial.code.in_(codes),
                    or_(
                        StockFinancial.ann_date <= end_date,
                        and_(
                            StockFinancial.ann_date.is_(None),
                            _est_ann <= end_date,
                        ),
                    ),
                )
                .all()
            )
            # 按 code 分组，按 report_date 排序
            fin_by_code = _dd(list)
            for r in all_fin_rows:
                fin_by_code[r.code].append(r)
            for code in fin_by_code:
                fin_by_code[code].sort(key=lambda x: str(x.report_date))

            # ── 4b. 融资融券 → margin_ratio ──
            from models.quant_data import StockMarginData
            all_margin_rows = (
                db.query(StockMarginData)
                .filter(
                    StockMarginData.code.in_(codes),
                    StockMarginData.trade_date <= end_date,
                )
                .all()
            )
            margin_by_code = _dd(list)
            for r in all_margin_rows:
                margin_by_code[r.code].append(r)
            for code in margin_by_code:
                margin_by_code[code].sort(key=lambda x: str(x.trade_date))

            # ── 5. 批量拉取行情用于动量/波动率（后复权，F7/R1 修复）──
            all_bar_rows = (
                db.query(StockDailyBar.code, StockDailyBar.trade_date,
                         StockDailyBar.close, StockDailyBar.adj_factor)
                .filter(
                    StockDailyBar.code.in_(codes),
                    StockDailyBar.trade_date >= start_date,
                    StockDailyBar.trade_date <= end_date,
                    StockDailyBar.close.isnot(None),
                )
                .order_by(StockDailyBar.code, StockDailyBar.trade_date)
                .all()
            )
            bar_by_code = _dd(list)
            for row in all_bar_rows:
                adj = float(row.adj_factor) if row.adj_factor else 1.0
                bar_by_code[row.code].append((str(row.trade_date), float(row.close) * adj))

        # ── 6. 逐月末截面组装（每月独立因子值）──
        snapshots = []
        for i in range(len(month_ends) - 1):
            t_date = month_ends[i]
            t1_date = month_ends[i + 1]

            # 为当月截面构建独立的因子映射
            cur_factor_map = {}
            for code in codes:
                # 估值：取 <= t_date 的最新一条
                rows = factor_by_code.get(code, [])
                latest = None
                for r in rows:
                    if str(r.trade_date) <= t_date:
                        latest = r
                if latest:
                    cur_factor_map[code] = {
                        "pe_ttm": latest.pe_ttm, "pb": latest.pb,
                        "turnover_rate": latest.turnover_rate,
                        "total_mv": latest.total_mv,
                        "circ_mv": latest.circ_mv, "dv_ttm": latest.dv_ttm,
                    }

            cur_fin_map = {}
            for code in codes:
                # 财务：取 ann_date <= t_date（或估算日 <= t_date）的最新报告期
                rows = fin_by_code.get(code, [])
                latest = None
                for r in rows:
                    ann = str(r.ann_date)[:10] if r.ann_date else _estimated_ann_date(r.report_date)
                    if ann <= t_date:
                        latest = r
                if latest:
                    cur_fin_map[code] = {
                        "roe": latest.roe,
                        "gross_profit_margin": latest.gross_profit_margin,
                        "cashflow_oper": latest.cashflow_oper if hasattr(latest, "cashflow_oper") else None,
                        "debt_to_assets": latest.debt_to_assets if hasattr(latest, "debt_to_assets") else None,
                        "eps": latest.eps if hasattr(latest, "eps") else None,
                        "revenue_growth": latest.revenue_yoy if hasattr(latest, "revenue_yoy") else None,
                        "net_profit_growth": latest.net_profit_yoy if hasattr(latest, "net_profit_yoy") else None,
                    }

            # 融资融券：取 trade_date <= t_date 的最新
            for code in codes:
                rows = margin_by_code.get(code, [])
                latest = None
                for r in rows:
                    if str(r.trade_date) <= t_date:
                        latest = r
                if latest and latest.rzye:
                    circ_mv = cur_factor_map.get(code, {}).get("circ_mv") or cur_factor_map.get(code, {}).get("total_mv")
                    if circ_mv and circ_mv > 0:
                        cur_fin_map.setdefault(code, {})["margin_ratio"] = latest.rzye / (circ_mv * 10000)

            # 动量/波动率：取 <= t_date 的最近 20 日
            cur_momentum_map = {}
            cur_volatility_map = {}
            for code in codes:
                bars = bar_by_code.get(code, [])
                # 取 <= t_date 的最近 20 条
                filtered = [c for d, c in bars if d <= t_date]
                if len(filtered) >= 2:
                    closes_arr = np.array(filtered[-20:])  # 时间正序，取最后20条
                    cur_momentum_map[code] = float(closes_arr[-1] / closes_arr[0] - 1) if closes_arr[0] != 0 else 0.0
                    rev = closes_arr
                    returns_20 = np.diff(rev) / np.where(rev[:-1] != 0, rev[:-1], np.nan)
                    returns_20 = returns_20[~np.isnan(returns_20)]
                    cur_volatility_map[code] = float(np.std(returns_20) * np.sqrt(TRADING_DAYS)) if len(returns_20) > 1 else 0.0

            records = []
            for code in codes:
                p0 = price_map.get((code, t_date))
                p1 = price_map.get((code, t1_date))
                if p0 is None or p1 is None or p0 <= 0:
                    continue

                fwd_ret = (p1 - p0) / p0

                entry = {"code": code, "fwd_ret": fwd_ret}
                entry.update(cur_factor_map.get(code, {}))
                entry.update(cur_fin_map.get(code, {}))
                entry["momentum_20"] = cur_momentum_map.get(code, 0.0)
                entry["reversal_20"] = -cur_momentum_map.get(code, 0.0)
                entry["volatility_20"] = cur_volatility_map.get(code, 0.0)
                records.append(entry)

            if len(records) >= 10:
                snapshots.append({
                    "period_date": t_date,
                    "df": pd.DataFrame(records),
                })

        log.info("monthly_snapshots_loaded", periods=len(snapshots),
                 codes=len(codes), date_range=f"{month_ends[0]}~{month_ends[-1]}")
        return snapshots

    except Exception as e:
        log.warning(f"[FactorLoader] load_monthly_snapshots error: {e}")
        return []

