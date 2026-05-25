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
        # akshare 接口可能变更，提供 fallback
        df = ak.index_stock_cons(symbol="000300")
        return [{"ts_code": r["品种代码"], "name": r["品种名称"]}
                for _, r in df.iterrows()]


def fetch_daily_kline(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取单只股票日线数据"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=ts_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            "日期": "trade_date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover",
            "涨跌幅": "pct_chg",
            "股票代码": "ts_code",
        })

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
