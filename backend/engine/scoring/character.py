"""股性评分: 基于涨停次数的全市场排名百分位"""
import numpy as np
import pandas as pd


def compute_limit_up_counts(df: pd.DataFrame) -> dict:
    """计算单只股票的涨停次数统计。
    返回: {limit_up_year: int, limit_up_month: int, total_limit_ups: int}
    """
    if "pct_chg" not in df.columns:
        return {"limit_up_year": 0, "limit_up_month": 0, "total_limit_ups": 0}

    pct = df["pct_chg"].values
    n = len(df)

    # 涨停判定: 涨幅 >= 9.5% (主板10%, 科创/创业20%, 用9.5覆盖大部分)
    is_limit_up = pct >= 9.5

    # 近一年: 约 250 个交易日
    year_window = min(250, n)
    year_count = int(is_limit_up[-year_window:].sum())

    # 近一月: 约 22 个交易日
    month_window = min(22, n)
    month_count = int(is_limit_up[-month_window:].sum())

    total = int(is_limit_up.sum())

    return {
        "limit_up_year": year_count,
        "limit_up_month": month_count,
        "total_limit_ups": total,
    }


def compute_character_score(lu_year: int, lu_month: int,
                            year_ranks: dict, month_ranks: dict) -> float:
    """根据全市场百分位计算股性得分 (0-100)。
    year_ranks: {count → percentile} 近一年涨停次数的排名映射
    month_ranks: {count → percentile} 近一月涨停次数的排名映射
    """
    year_pct = year_ranks.get(lu_year, 0.0)
    month_pct = month_ranks.get(lu_month, 0.0)

    year_score = year_pct * 60  # 近一年占60分
    month_score = month_pct * 40  # 近一月占40分

    return round(year_score + month_score, 1)


def build_rank_maps(all_counts: list[dict]) -> tuple[dict, dict]:
    """根据全市场股票的涨停次数，构建排名百分位映射。
    all_counts: [{limit_up_year, limit_up_month}, ...]
    返回: (year_ranks, month_ranks)
    """
    if not all_counts:
        return {}, {}

    year_vals = sorted(set(c["limit_up_year"] for c in all_counts))
    month_vals = sorted(set(c["limit_up_month"] for c in all_counts))

    n_year = len(year_vals)
    n_month = len(month_vals)

    year_ranks = {}
    for rank, val in enumerate(year_vals):
        year_ranks[val] = round(rank / max(n_year - 1, 1), 4)

    month_ranks = {}
    for rank, val in enumerate(month_vals):
        month_ranks[val] = round(rank / max(n_month - 1, 1), 4)

    return year_ranks, month_ranks
