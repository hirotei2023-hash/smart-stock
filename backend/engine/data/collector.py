import time
from datetime import datetime, timedelta
import pandas as pd
import akshare as ak
from backend.config import DATA_YEARS
from backend.engine.data.schema import get_connection


def fetch_hs300_stocks() -> list[dict]:
    """获取沪深300成分股列表"""
    try:
        df = ak.index_stock_cons_csindex(symbol="000300")
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                "ts_code": row["成分券代码"],
                "name": row["成分券名称"],
            })
        return stocks
    except Exception:
        df = ak.index_stock_cons(symbol="000300")
        return [{"ts_code": r["品种代码"], "name": r["品种名称"]}
                for _, r in df.iterrows()]


def fetch_csi500_stocks() -> list[dict]:
    """获取中证500成分股列表"""
    try:
        df = ak.index_stock_cons_csindex(symbol="000905")
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                "ts_code": row["成分券代码"],
                "name": row["成分券名称"],
            })
        return stocks
    except Exception:
        try:
            df = ak.index_stock_cons(symbol="000905")
            return [{"ts_code": r["品种代码"], "name": r["品种名称"]}
                    for _, r in df.iterrows()]
        except Exception:
            return []


def _ts_code_to_sina(ts_code: str) -> str:
    """将 ts_code (000001/600001) 转换为 Sina 格式 (sz000001/sh600001)"""
    if ts_code.startswith("6"):
        return f"sh{ts_code}"
    else:
        return f"sz{ts_code}"


def fetch_daily_kline(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取单只股票日线数据（东方财富 -> Sina fallback）"""
    # 方案 1：东方财富
    try:
        df = ak.stock_zh_a_hist(
            symbol=ts_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if not df.empty:
            df = df.rename(columns={
                "日期": "trade_date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume",
                "成交额": "amount", "换手率": "turnover", "涨跌幅": "pct_chg",
                "股票代码": "ts_code",
            })
            cols = ["ts_code", "trade_date", "open", "high", "low", "close",
                    "volume", "amount", "turnover", "pct_chg"]
            return df[[c for c in cols if c in df.columns]]
    except Exception:
        pass

    # 方案 2：Sina fallback
    try:
        sina_sym = _ts_code_to_sina(ts_code)
        df = ak.stock_zh_a_daily(
            symbol=sina_sym,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            "date": "trade_date",
        })
        df["ts_code"] = ts_code
        if "pct_chg" not in df.columns:
            df["pct_chg"] = df["close"].pct_change() * 100
        if "turnover" not in df.columns and "outstanding_share" in df.columns:
            df["turnover"] = df["volume"] / df["outstanding_share"]

        cols = ["ts_code", "trade_date", "open", "high", "low", "close",
                "volume", "amount", "turnover", "pct_chg"]
        return df[[c for c in cols if c in df.columns]]
    except Exception as e:
        print(f"[WARN] fetch {ts_code} failed: {e}")
        return pd.DataFrame()


def fetch_all_hs300(conn, delay: float = 0.5):
    """拉取全部沪深300成分股2年日线数据"""
    stocks = fetch_hs300_stocks()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=DATA_YEARS * 366)).strftime("%Y%m%d")

    # 写入股票基本信息
    for s in stocks:
        conn.execute(
            "INSERT OR REPLACE INTO stock_basic (ts_code, name) VALUES (?, ?)",
            (s["ts_code"], s["name"])
        )
    conn.commit()

    # 逐只拉取K线
    total = len(stocks)
    for i, s in enumerate(stocks):
        print(f"[{i+1}/{total}] Fetching {s['ts_code']} {s['name']}...")
        df = fetch_daily_kline(s["ts_code"], start_date, end_date)
        if not df.empty:
            for _, row in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO daily_kline
                       (ts_code, trade_date, open, high, low, close, volume, amount, turnover, pct_chg)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s["ts_code"], row["trade_date"], row["open"], row["high"],
                     row["low"], row["close"], row["volume"],
                     row.get("amount"), row.get("turnover"), row.get("pct_chg"))
                )
            conn.commit()
        time.sleep(delay)  # 限速

    print(f"Done. {total} stocks fetched.")
    return stocks


def fetch_all_stocks(conn, stock_list: list[dict], delay: float = 0.5):
    """拉取指定股票列表的日线数据"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=DATA_YEARS * 366)).strftime("%Y%m%d")

    for s in stock_list:
        conn.execute(
            "INSERT OR REPLACE INTO stock_basic (ts_code, name) VALUES (?, ?)",
            (s["ts_code"], s["name"])
        )
    conn.commit()

    total = len(stock_list)
    for i, s in enumerate(stock_list):
        print(f"[{i+1}/{total}] Fetching {s['ts_code']} {s['name']}...")
        df = fetch_daily_kline(s["ts_code"], start_date, end_date)
        if not df.empty:
            for _, row in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO daily_kline
                       (ts_code, trade_date, open, high, low, close, volume, amount, turnover, pct_chg)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s["ts_code"], row["trade_date"], row["open"], row["high"],
                     row["low"], row["close"], row["volume"],
                     row.get("amount"), row.get("turnover"), row.get("pct_chg"))
                )
            conn.commit()
        time.sleep(delay)

    print(f"Done. {total} stocks fetched.")
    return stock_list


def fetch_stock_daily_basic_snapshot(conn, stock_list: list[dict]):
    """快照式基本面数据 — 由于 eastmoney API 被网络封禁，使用 Sina spot 获取最新 PE/PB/MV"""
    try:
        df = ak.stock_zh_a_spot()
        if df is None or df.empty:
            print("[WARN] stock_zh_a_spot returned empty")
            return 0

        # Sina spot columns: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 买入, 卖出, 昨收, 今开, ...
        inserted = 0
        latest_date = datetime.now().strftime("%Y%m%d")

        for _, row in df.iterrows():
            try:
                code = str(row.get("代码", "")).strip()
                if not code or len(code) < 6:
                    continue
                if "." in code:
                    code = code.replace("sh", "").replace("sz", "").replace(".", "")
                pe = float(row.get("市盈率", 0)) if row.get("市盈率") else None
                total_mv = float(row.get("总市值", 0)) if row.get("总市值") else None
                circ_mv = float(row.get("流通市值", 0)) if row.get("流通市值") else None
                pb = None
                if total_mv and total_mv > 0:
                    pb = float(row.get("市净率", 0)) if row.get("市净率") else None

                conn.execute(
                    """INSERT OR REPLACE INTO stock_daily_basic
                       (ts_code, trade_date, pe, pe_ttm, pb, ps, total_mv, circ_mv)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (code, latest_date, pe, pe, pb, None, total_mv, circ_mv)
                )
                inserted += 1
            except Exception:
                continue
        conn.commit()
        return inserted
    except Exception as e:
        print(f"[WARN] stock_zh_a_spot failed: {e}")
        return 0


def fetch_sector_classification(conn):
    """拉取申万行业分类并写入 stock_sector 表"""
    try:
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return 0

        count = 0
        for _, row in df.iterrows():
            try:
                board_name = row["板块名称"]
                if "SW" not in str(board_name) and "申万" not in str(board_name):
                    continue
                board_code = row["板块代码"]
                members = ak.stock_board_industry_cons_em(symbol=board_name)
                if members is None or members.empty:
                    continue
                for _, m in members.iterrows():
                    code = m.get("代码", "")
                    if not code:
                        continue
                    conn.execute(
                        """INSERT OR REPLACE INTO stock_sector
                           (ts_code, sw_level1, sw_level2, sw_level3)
                           VALUES (?, ?, ?, ?)""",
                        (code, board_name, row.get("板块名称", ""), row.get("板块名称", ""))
                    )
                    count += 1
            except Exception:
                continue
        conn.commit()
        return count
    except Exception as e:
        print(f"[WARN] sector classification: {e}")
        return 0


def fetch_market_index(conn, start_date: str, end_date: str):
    """拉取市场指数日频数据 (上证/深证/沪深300/中证500)"""
    indices = {
        "sh_idx": "sh000001",   # 上证综指
        "sz_idx": "sz399001",   # 深证成指
        "hs300_idx": "sh000300",  # 沪深300
        "zz500_idx": "sh000905",  # 中证500
    }

    for name, symbol in indices.items():
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                continue
            df = df.rename(columns={"date": "trade_date"})
            for _, row in df.iterrows():
                td = str(row["trade_date"])
                if td < start_date or td > end_date:
                    continue
                pct_col = f"{name}_pct"
                conn.execute(
                    f"""INSERT OR IGNORE INTO market_index (trade_date) VALUES (?);""",
                    (td,)
                )
                pct_val = row.get("pct_chg", row.get("close"))
                if isinstance(pct_val, (int, float)):
                    conn.execute(
                        f"UPDATE market_index SET {pct_col}=? WHERE trade_date=?",
                        (float(pct_val), td)
                    )
                if name == "hs300_idx":
                    amt = row.get("amount")
                    if amt is not None:
                        conn.execute(
                            "UPDATE market_index SET amount_billion=? WHERE trade_date=?",
                            (float(amt) / 1e9, td)
                        )
            conn.commit()
            print(f"  Market index {name} done.")
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] market_index {name}: {e}")

    # 涨跌家数
    try:
        df = ak.stock_zh_a_spot()
        # spot 只有当日数据，作为快照写入最新日期
        if df is not None and not df.empty:
            latest = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]
            up_count = int((df["涨跌幅"] > 0).sum())
            down_count = int((df["涨跌幅"] < 0).sum())
            conn.execute(
                "UPDATE market_index SET up_count=?, down_count=? WHERE trade_date=?",
                (up_count, down_count, latest)
            )
            conn.commit()
    except Exception:
        pass
