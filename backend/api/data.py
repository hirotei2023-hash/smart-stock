# smart-stock/backend/api/data.py
from fastapi import APIRouter, Query
from backend.engine.data.schema import get_connection

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/stocks")
def list_stocks(search: str = Query("", max_length=20)):
    conn = get_connection()
    if search:
        rows = conn.execute(
            "SELECT ts_code, name, industry FROM stock_basic WHERE ts_code LIKE ? OR name LIKE ? LIMIT 20",
            (f"%{search}%", f"%{search}%")
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT ts_code, name, industry FROM stock_basic LIMIT 300"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/top-gainers")
def top_gainers(date: str = Query("")):
    """涨幅 Top50 + 次新股，支持指定日期"""
    conn = get_connection()

    if date:
        base = date
    else:
        base = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]

    y_ago = conn.execute(
        "SELECT MAX(trade_date) FROM daily_kline WHERE trade_date <= date(?, '-12 months')",
        (base,)
    ).fetchone()[0]
    m_ago = conn.execute(
        "SELECT MAX(trade_date) FROM daily_kline WHERE trade_date <= date(?, '-1 months')",
        (base,)
    ).fetchone()[0]
    # 本年第一个交易日
    year_start = conn.execute(
        "SELECT MIN(trade_date) FROM daily_kline WHERE trade_date >= ?",
        (base[:4] + "-01-01",)
    ).fetchone()[0] or base
    # 本月第一个交易日
    month_start = conn.execute(
        "SELECT MIN(trade_date) FROM daily_kline WHERE trade_date >= ?",
        (base[:7] + "-01",)
    ).fetchone()[0] or base

    this_year_start = base[:4] + "-01-01"

    # 今年上市股票代码
    new_codes = set(r[0] for r in conn.execute(
        "SELECT ts_code FROM daily_kline GROUP BY ts_code HAVING MIN(trade_date) >= ?",
        (this_year_start,)
    ).fetchall())

    # 老股排行 (排除今年新股)
    rows = conn.execute("""
        WITH latest_p AS (
            SELECT ts_code, close, pct_chg FROM daily_kline WHERE trade_date = ?
        ),
        year_p AS (
            SELECT ts_code, close FROM daily_kline WHERE trade_date = ?
        ),
        month_p AS (
            SELECT ts_code, close FROM daily_kline WHERE trade_date = ?
        ),
        mtd_p AS (
            SELECT ts_code, close FROM daily_kline WHERE trade_date = ?
        ),
        ytd_p AS (
            SELECT ts_code, close FROM daily_kline WHERE trade_date = ?
        ),
        limit_up AS (
            SELECT ts_code,
                SUM(CASE WHEN trade_date >= ? AND pct_chg >= 9.5 THEN 1 ELSE 0 END) AS lu_year,
                SUM(CASE WHEN trade_date >= ? AND pct_chg >= 9.5 THEN 1 ELSE 0 END) AS lu_month
            FROM daily_kline
            WHERE trade_date >= ?
            GROUP BY ts_code
        )
        SELECT b.ts_code, b.name,
               ROUND((l.close - y.close) / y.close * 100, 2) AS ret_1y,
               ROUND((l.close - m.close) / m.close * 100, 2) AS ret_1m,
               ROUND((l.close - mt.close) / mt.close * 100, 2) AS ret_mtd,
               ROUND((l.close - yt.close) / yt.close * 100, 2) AS ret_ytd,
               COALESCE(lu.lu_year, 0) AS lu_year,
               COALESCE(lu.lu_month, 0) AS lu_month,
               l.close AS close,
               ROUND(l.pct_chg, 2) AS pct_chg
        FROM latest_p l
        JOIN year_p y ON l.ts_code = y.ts_code
        JOIN month_p m ON l.ts_code = m.ts_code
        JOIN mtd_p mt ON l.ts_code = mt.ts_code
        JOIN ytd_p yt ON l.ts_code = yt.ts_code
        JOIN stock_basic b ON l.ts_code = b.ts_code
        LEFT JOIN limit_up lu ON l.ts_code = lu.ts_code
        WHERE y.close > 0 AND m.close > 0 AND mt.close > 0 AND yt.close > 0
    """, (base, y_ago, m_ago, month_start, year_start, y_ago, m_ago, y_ago)).fetchall()

    all_result = [dict(r) for r in rows if r["ts_code"] not in new_codes]

    year_top = sorted(all_result, key=lambda x: x["ret_ytd"] or -999, reverse=True)[:50]
    month_top = sorted(all_result, key=lambda x: x["ret_1m"] or -999, reverse=True)[:50]

    # ===== 排名变化：对比上个月最后一个交易日（月榜/年榜各自独立） =====
    rank_change_month = {}
    rank_change_year = {}
    prev_month_end = conn.execute(
        "SELECT MAX(trade_date) FROM daily_kline WHERE strftime('%Y-%m', trade_date) < ?",
        (base[:7],)
    ).fetchone()[0]
    if prev_month_end:
        prev_m_ago = conn.execute(
            "SELECT MAX(trade_date) FROM daily_kline WHERE trade_date <= date(?, '-1 months')",
            (prev_month_end,)
        ).fetchone()[0]
        if prev_m_ago:
            prev_rows = conn.execute("""
                WITH np AS (SELECT ts_code, close FROM daily_kline WHERE trade_date=?),
                     ap AS (SELECT ts_code, close FROM daily_kline WHERE trade_date=?)
                SELECT b.ts_code, ROUND((n.close-a.close)/a.close*100,2) AS ret_1m
                FROM np n JOIN ap a ON n.ts_code=a.ts_code
                JOIN stock_basic b ON n.ts_code=b.ts_code
                WHERE a.close>0
            """, (prev_month_end, prev_m_ago)).fetchall()
            prev_all = [dict(r) for r in prev_rows if r["ts_code"] not in new_codes]
            prev_sorted = sorted(prev_all, key=lambda x: x["ret_1m"] or -999, reverse=True)
            prev_rank = {s["ts_code"]: i+1 for i, s in enumerate(prev_sorted)}
            # 月榜
            for i, s in enumerate(month_top):
                code = s["ts_code"]
                old_rank = prev_rank.get(code, 9999)
                rank_change_month[code] = old_rank - (i + 1)
            # 年榜
            for i, s in enumerate(year_top):
                code = s["ts_code"]
                old_rank = prev_rank.get(code, 9999)
                rank_change_year[code] = old_rank - (i + 1)

    # 次新股: 批量查询，今年上市，按首个交易日降序
    new_listings = []
    if new_codes:
        placeholders = ",".join("?" * len(new_codes))
        codes_tuple = tuple(new_codes)

        # 一次查询: IPO日期 + 名称 + 最新收盘 + 一月前收盘 + 涨停统计
        # 一次性获取次新股所有数据（含IPO首日收盘、最新收盘、一月前收盘、涨停统计）
        rows_n = conn.execute(f"""
            WITH ipo AS (
                SELECT ts_code, MIN(trade_date) AS ipo_date
                FROM daily_kline WHERE ts_code IN ({placeholders}) GROUP BY ts_code
            ),
            ipo_close AS (
                SELECT d.ts_code, d.close
                FROM daily_kline d
                INNER JOIN ipo i ON d.ts_code = i.ts_code AND d.trade_date = i.ipo_date
            ),
            latest AS (
                SELECT ts_code, close, pct_chg FROM daily_kline WHERE trade_date = ?
            ),
            month_p AS (
                SELECT ts_code, close FROM daily_kline WHERE trade_date = ?
            ),
            lu AS (
                SELECT ts_code,
                    SUM(CASE WHEN trade_date >= ? AND pct_chg >= 9.5 THEN 1 ELSE 0 END) AS lu_year,
                    SUM(CASE WHEN trade_date >= ? AND pct_chg >= 9.5 THEN 1 ELSE 0 END) AS lu_month
                FROM daily_kline WHERE ts_code IN ({placeholders}) AND trade_date >= ?
                GROUP BY ts_code
            )
            SELECT b.ts_code, b.name, i.ipo_date, ic.close AS ipo_close,
                   l.close, l.pct_chg, m.close AS close_m,
                   COALESCE(lu.lu_year, 0) AS lu_year,
                   COALESCE(lu.lu_month, 0) AS lu_month
            FROM ipo i
            JOIN stock_basic b ON i.ts_code = b.ts_code
            JOIN latest l ON i.ts_code = l.ts_code
            JOIN ipo_close ic ON i.ts_code = ic.ts_code
            LEFT JOIN month_p m ON i.ts_code = m.ts_code
            LEFT JOIN lu ON i.ts_code = lu.ts_code
        """, codes_tuple + (base, m_ago, y_ago, m_ago) + codes_tuple + (y_ago,)).fetchall()

        for r in rows_n:
            ipo_ret = round((r["close"] - r["ipo_close"]) / r["ipo_close"] * 100, 2) if r["ipo_close"] > 0 else None
            ret_1m = round((r["close"] - r["close_m"]) / r["close_m"] * 100, 2) if r["close_m"] and r["close_m"] > 0 else None
            new_listings.append({
                "ts_code": r["ts_code"],
                "name": r["name"],
                "ipo_date": r["ipo_date"],
                "close": r["close"],
                "pct_chg": r["pct_chg"],
                "ret_1m": ret_1m,
                "ipo_ret": ipo_ret,
                "lu_year": r["lu_year"],
                "lu_month": r["lu_month"],
            })

        new_listings.sort(key=lambda x: x["ipo_date"], reverse=True)

    # 可选日期列表
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT trade_date FROM daily_kline ORDER BY trade_date DESC LIMIT 60"
    ).fetchall()]

    conn.close()
    return {
        "date": base,
        "year_top": year_top,
        "month_top": month_top,
        "new_listings": new_listings[:50],
        "available_dates": dates,
        "rank_change_month": rank_change_month,
        "rank_change_year": rank_change_year,
    }


@router.get("/top-gainers/analysis")
def gainers_analysis(date: str = Query(""), top_n: int = Query(30)):
    """量化分析月榜Top N：斜率拐点 + MACD/MA/KDJ金叉 + 量比变化 → 一段话总结"""
    import math
    conn = get_connection()
    if not date:
        date = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]

    m_ago = conn.execute(
        "SELECT MAX(trade_date) FROM daily_kline WHERE trade_date <= date(?, '-1 months')",
        (date,)
    ).fetchone()[0]
    if not m_ago:
        conn.close()
        return {"error": "数据不足"}

    # 排除今年新股
    this_year_start = date[:4] + "-01-01"
    new_codes = set(r[0] for r in conn.execute(
        "SELECT ts_code FROM daily_kline GROUP BY ts_code HAVING MIN(trade_date) >= ?",
        (this_year_start,)
    ).fetchall())

    # 月涨幅排行
    rows = conn.execute("""
        WITH n AS (SELECT ts_code, close FROM daily_kline WHERE trade_date=?),
             a AS (SELECT ts_code, close FROM daily_kline WHERE trade_date=?)
        SELECT b.ts_code, b.name, ROUND((n.close-a.close)/a.close*100,2) AS ret_1m
        FROM n JOIN a ON n.ts_code=a.ts_code JOIN stock_basic b ON n.ts_code=b.ts_code
        WHERE a.close>0
    """, (date, m_ago)).fetchall()

    all_rows = [dict(r) for r in rows if r["ts_code"] not in new_codes]
    top = sorted(all_rows, key=lambda x: x["ret_1m"] or -999, reverse=True)[:top_n]
    if not top:
        conn.close()
        return {"error": "无符合条件的股票"}

    # 每只股票取60天K线用于分析
    s60 = conn.execute(
        "SELECT MAX(trade_date) FROM daily_kline WHERE trade_date <= date(?, '-60 days')",
        (date,)
    ).fetchone()[0] or date

    all_klines = {}
    for s in top:
        k = conn.execute("""
            SELECT trade_date, open, high, low, close, volume
            FROM daily_kline WHERE ts_code=? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """, (s["ts_code"], s60, date)).fetchall()
        if len(k) >= 30:
            all_klines[s["ts_code"]] = {
                "name": s["name"],
                "ret_1m": s["ret_1m"],
                "dates": [r[0] for r in k],
                "o": [r[1] for r in k], "h": [r[2] for r in k],
                "l": [r[3] for r in k], "c": [r[4] for r in k],
                "v": [r[5] for r in k],
            }
    conn.close()

    # ===================== 指标计算工具函数 =====================

    def calc_slope(y, window):
        """线性回归斜率 (n=window)，反映趋势方向与强度"""
        if len(y) < window: return 0
        ys = y[-window:]
        n = len(ys)
        x_sum = n * (n - 1) / 2
        y_sum = sum(ys)
        xy_sum = sum(i * ys[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        denom = n * x2_sum - x_sum * x_sum
        if denom == 0: return 0
        return (n * xy_sum - x_sum * y_sum) / denom

    def calc_ema(y, n):
        if len(y) < 2: return y[-1] if y else 0
        k = 2 / (n + 1)
        ema = y[0]
        for v in y[1:]:
            ema = v * k + ema * (1 - k)
        return ema

    def calc_macd(closes):
        """返回 (DIF, DEA, 柱), 以及是否金叉"""
        if len(closes) < 35: return 0, 0, 0, False, False
        # 计算完整EMA序列
        ema12_list = [closes[0]]
        k12 = 2 / 13
        for v in closes[1:]:
            ema12_list.append(v * k12 + ema12_list[-1] * (1 - k12))
        k26 = 2 / 27
        ema26_list = [closes[0]]
        for v in closes[1:]:
            ema26_list.append(v * k26 + ema26_list[-1] * (1 - k26))
        dif = [ema12_list[i] - ema26_list[i] for i in range(len(closes))]
        dea = [dif[0]]
        k9 = 2 / 10
        for v in dif[1:]:
            dea.append(v * k9 + dea[-1] * (1 - k9))
        bar = [(dif[i] - dea[i]) * 2 for i in range(len(closes))]

        # 最近5天是否金叉(DIF从下穿上DEA)
        crossed = False
        cross_day = -1
        for i in range(max(1, len(closes)-5), len(closes)):
            if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                crossed = True
                cross_day = i
                break
        return dif[-1], dea[-1], bar[-1], crossed, cross_day

    def calc_kdj(highs, lows, closes, n=9):
        """返回 (K, D, J), 以及近5日是否金叉"""
        if len(closes) < n + 5: return 50, 50, 50, False
        k_vals = [50] * (n - 1)
        d_vals = [50] * (n - 1)
        for i in range(n - 1, len(closes)):
            hh = max(highs[i-n+1:i+1])
            ll = min(lows[i-n+1:i+1])
            rsv = (closes[i] - ll) / (hh - ll) * 100 if hh != ll else 50
            k_vals.append(2/3 * k_vals[-1] + 1/3 * rsv if k_vals else rsv)
            d_vals.append(2/3 * d_vals[-1] + 1/3 * k_vals[-1] if d_vals else k_vals[-1])
        j_vals = [3*k_vals[i] - 2*d_vals[i] for i in range(len(k_vals))]
        # 近5日金叉
        crossed = False
        for i in range(max(1, len(k_vals)-5), len(k_vals)):
            if k_vals[i-1] <= d_vals[i-1] and k_vals[i] > d_vals[i]:
                crossed = True
                break
        return k_vals[-1], d_vals[-1], j_vals[-1], crossed

    def calc_ma_cross(closes, short=5, long=21):
        """MA均线金叉检测"""
        if len(closes) < long + 5: return False
        ma_s = [sum(closes[i-short+1:i+1])/short for i in range(short-1, len(closes))]
        ma_l = [sum(closes[i-long+1:i+1])/long for i in range(long-1, len(closes))]
        offset = long - short
        for i in range(max(1, len(ma_s)-5), len(ma_s)):
            j = i - offset
            if j < 1: continue
            if ma_s[j-1] <= ma_l[j-1] and ma_s[j] > ma_l[j]:
                return True
        return False

    def find_upturn_idx(closes, window=30):
        """找近window日内上涨趋势的起点（最低点位置）"""
        if len(closes) < window: return 0
        seg = closes[-window:]
        min_idx = seg.index(min(seg))
        return len(closes) - window + min_idx

    # ===================== 逐只分析 =====================

    results = {
        "slope_5_before": [],   # 启动前短期斜率
        "slope_5_after": [],    # 启动后短期斜率
        "slope_10_before": [],  # 启动前中期斜率
        "slope_10_after": [],   # 启动后中期斜率
        "slope_20_before": [],
        "slope_20_after": [],
        "macd_cross": 0,        # MACD金叉计数
        "ma_cross": 0,          # MA金叉计数
        "kdj_cross": 0,         # KDJ金叉计数
        "vol_ratio_at_start": [], # 启动时量比
        "vol_ratio_after": [],  # 启动后5日均量比
        "rsi_before": [],       # 启动前RSI
        "rsi_after": [],        # 当前RSI
        "bb_position": [],      # 布林带位置
        "ret_before_start": [], # 启动前一周涨跌
    }

    rsi_14_vals = []
    for code, d in all_klines.items():
        closes = d["c"]
        volumes = d["v"]
        highs = d["h"]
        lows = d["l"]
        n = len(closes)

        # 找上涨起点：近30日最低点
        pivot = find_upturn_idx(closes, 30)
        if pivot < 5: pivot = max(5, n - 21)

        # === 斜率 ===
        before = closes[:pivot+1]
        after = closes[pivot:]

        results["slope_5_before"].append(calc_slope(before, 5))
        results["slope_5_after"].append(calc_slope(after, 5))
        results["slope_10_before"].append(calc_slope(before, 10))
        results["slope_10_after"].append(calc_slope(after, 10))
        results["slope_20_before"].append(calc_slope(before, 20))
        results["slope_20_after"].append(calc_slope(after, 20))

        # === MACD ===
        _, _, _, mc, _ = calc_macd(closes)
        if mc: results["macd_cross"] += 1

        # === MA5/21金叉 ===
        if calc_ma_cross(closes):
            results["ma_cross"] += 1

        # === KDJ金叉 ===
        _, _, _, kc = calc_kdj(highs, lows, closes, 9)
        if kc: results["kdj_cross"] += 1

        # === 量比 ===
        if pivot >= 2 and len(volumes) > 20:
            vol_base = sum(volumes[max(0,pivot-20):pivot]) / max(1, min(20, pivot))
            vol_at = volumes[pivot] / max(vol_base, 1)
            results["vol_ratio_at_start"].append(vol_at)

            vol_after = sum(volumes[pivot:min(n,pivot+5)]) / 5 / max(vol_base, 1)
            results["vol_ratio_after"].append(vol_after)

        # === RSI ===
        gains = [max(0, closes[i]-closes[i-1]) for i in range(1, n)]
        losses = [max(0, closes[i-1]-closes[i]) for i in range(1, n)]
        if len(gains) >= 14:
            avg_g = sum(gains[-14:])/14
            avg_l = sum(losses[-14:])/14 if sum(losses[-14:]) > 0 else 0.0001
            rsi_now = 100 - 100/(1 + avg_g/avg_l)
            results["rsi_after"].append(rsi_now)
        if pivot >= 15:
            avg_g = sum(gains[pivot-14:pivot])/14
            avg_l = sum(losses[pivot-14:pivot])/14 if sum(losses[pivot-14:pivot]) > 0 else 0.0001
            results["rsi_before"].append(100 - 100/(1 + avg_g/avg_l))

        # === 布林带位置 (20日均线 ± 2std) ===
        if n >= 20:
            ma20 = sum(closes[-20:])/20
            std20 = (sum((c-ma20)**2 for c in closes[-20:])/20)**0.5
            bb_top = ma20 + 2*std20
            bb_bot = ma20 - 2*std20
            bb_pos = (closes[pivot] - bb_bot) / max(bb_top - bb_bot, 0.01) * 100
            results["bb_position"].append(bb_pos)

        # === 启动前一周涨跌 ===
        if pivot >= 5:
            results["ret_before_start"].append((closes[pivot]-closes[pivot-5])/closes[pivot-5]*100)

    # ===================== 统计汇总 =====================
    def avg(vals):
        vals = [v for v in vals if v is not None and abs(v) < 1000]
        return round(sum(vals)/len(vals), 2) if vals else 0
    def pct(vals, cond):
        vals = [v for v in vals if v is not None]
        return round(sum(1 for v in vals if cond(v))/len(vals)*100) if vals else 0
    def median(vals):
        vals = sorted([v for v in vals if v is not None and abs(v) < 1000])
        return round(vals[len(vals)//2], 2) if vals else 0

    n_stocks = len(all_klines)
    total = top_n

    # ===================== 生成一段话总结 =====================
    parts = []
    # 斜率变化
    s5b = avg(results["slope_5_before"])
    s5a = avg(results["slope_5_after"])
    s10b = avg(results["slope_10_before"])
    s10a = avg(results["slope_10_after"])
    s20b = avg(results["slope_20_before"])
    s20a = avg(results["slope_20_after"])

    slope_5_change = "转正" if s5b <= 0 and s5a > 0 else "加速" if s5b > 0 and s5a > s5b else "放缓"
    parts.append(
        f"对近一月涨幅Top{total}的量化回溯显示，这些股票在上涨启动前，"
        f"短期(5日)斜率均值为{s5b:.1f}，启动后升至{s5a:.1f}（{slope_5_change}）；"
        f"中期(10日)斜率从{s10b:.1f}升至{s10a:.1f}，20日斜率从{s20b:.1f}升至{s20a:.1f}，"
        f"表明上涨具有持续性，非一日游行情。"
    )

    # 金叉情况
    macd_pct = round(results["macd_cross"]/n_stocks*100)
    ma_pct = round(results["ma_cross"]/n_stocks*100)
    kdj_pct = round(results["kdj_cross"]/n_stocks*100)
    parts.append(
        f"技术指标方面，{macd_pct}%的股票在启动阶段出现MACD金叉，"
        f"{ma_pct}%出现MA5/21均线金叉，{kdj_pct}%出现KDJ金叉。"
        f"{'MACD和均线金叉的共振是较强的启动信号。' if macd_pct >= 50 and ma_pct >= 50 else '多数股票至少满足一项金叉条件，可作为辅助筛选信号。'}"
    )

    # 量比
    vr_start = avg(results["vol_ratio_at_start"])
    vr_after = avg(results["vol_ratio_after"])
    vol_desc = "显著放量" if vr_after > 2 else "温和放量" if vr_after > 1.3 else "缩量" if vr_after < 0.8 else "平量"
    parts.append(
        f"量比方面，启动点均量比为{vr_start:.1f}倍，启动后5日均量比升至{vr_after:.1f}倍（{vol_desc}），"
        f"说明{'资金在趋势确认后跟进明显' if vr_after > 1.3 else '量能配合一般，需结合其他指标综合判断'}。"
    )

    # RSI
    rsi_b = avg(results["rsi_before"])
    rsi_a = avg(results["rsi_after"])
    rsi_desc = "超卖区反弹" if rsi_b < 35 else "中性区启动" if rsi_b < 55 else "强势区延续"
    parts.append(
        f"RSI(14)从启动前的{median(results['rsi_before']):.0f}升至当前的{median(results['rsi_after']):.0f}，"
        f"属于{rsi_desc}特征。"
    )

    # 布林带
    bb_m = median(results["bb_position"])
    bb_desc = "下轨附近（超卖反弹型）" if bb_m < 30 else "中轨附近（趋势启动型）" if bb_m < 60 else "上轨附近（强势追涨型）"
    parts.append(
        f"启动时布林带位置中位数{bb_m:.0f}%，"
        f"多数处于{bb_desc}。"
    )

    # 启动前状态
    ret_b = avg(results["ret_before_start"])
    parts.append(
        f"启动前一周平均涨跌幅{ret_b:.1f}%，"
        f"{'已有小幅反弹迹象' if ret_b > 0 else '处于下跌末端，属于典型的均值回归启动'}。"
    )

    summary_text = "".join(parts)

    return {
        "date": date,
        "top_count": total,
        "analyzed": n_stocks,
        "summary": summary_text,
        "detail": {
            "slope": {
                "5d": {"before": s5b, "after": s5a},
                "10d": {"before": s10b, "after": s10a},
                "20d": {"before": s20b, "after": s20a},
            },
            "golden_cross": {
                "macd_pct": macd_pct,
                "ma_5_21_pct": ma_pct,
                "kdj_pct": kdj_pct,
            },
            "volume": {
                "at_start": vr_start,
                "after_5d": vr_after,
            },
            "rsi": {
                "before_median": median(results["rsi_before"]),
                "after_median": median(results["rsi_after"]),
            },
            "bollinger_position_median": bb_m,
        },
    }


@router.get("/status")
def data_status():
    conn = get_connection()
    stock_count = conn.execute("SELECT COUNT(*) FROM stock_basic").fetchone()[0]
    kline_count = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    latest_date = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]
    conn.close()
    return {
        "stocks": stock_count,
        "kline_rows": kline_count,
        "latest_date": latest_date,
    }
