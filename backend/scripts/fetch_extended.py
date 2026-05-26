"""Phase 2a: 扩展数据采集 — HS300+CSI500, 6年K线, daily_basic, sector, market_index"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.engine.data.schema import get_connection, init_db
from backend.engine.data.collector import (
    fetch_hs300_stocks, fetch_csi500_stocks, fetch_all_stocks,
    fetch_stock_daily_basic_snapshot, fetch_sector_classification, fetch_market_index,
)
from backend.config import DATA_YEARS


def main():
    conn = get_connection()
    init_db()

    # 1. 获取沪深300 + 中证500 成分股
    print("=" * 50)
    print("Step 1: Fetching HS300 stocks...")
    hs300 = fetch_hs300_stocks()
    print(f"  Got {len(hs300)} HS300 stocks")

    print("Step 2: Fetching CSI500 stocks...")
    csi500 = fetch_csi500_stocks()
    print(f"  Got {len(csi500)} CSI500 stocks")

    # 合并去重
    all_codes = {s["ts_code"] for s in hs300}
    csi500_new = [s for s in csi500 if s["ts_code"] not in all_codes]
    all_stocks = hs300 + csi500_new
    print(f"  Total unique stocks: {len(all_stocks)}")

    # 2. 拉取K线
    print("=" * 50)
    print(f"Step 3: Fetching {DATA_YEARS} years daily K-line for {len(all_stocks)} stocks...")
    fetch_all_stocks(conn, all_stocks, delay=0.3)

    # 3. 快照式基本面数据（eastmoney 被封，用 Sina spot 快照）
    print("=" * 50)
    print("Step 4: Fetching fundamental snapshot (PE/PB/MV via Sina spot)...")
    n_basic = fetch_stock_daily_basic_snapshot(conn, all_stocks)
    print(f"  Inserted {n_basic} stock fundamentals")

    # 4. 拉取行业分类
    print("=" * 50)
    print("Step 5: Fetching SW sector classification...")
    n_sector = fetch_sector_classification(conn)
    print(f"  Inserted {n_sector} sector mappings")

    # 5. 拉取市场指数
    print("=" * 50)
    print("Step 6: Fetching market index data...")
    start = f"{2026 - DATA_YEARS}0101"
    end = "20260530"
    fetch_market_index(conn, start, end)

    # 6. 汇总统计
    n_kline = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    n_basic = conn.execute("SELECT COUNT(*) FROM stock_daily_basic").fetchone()[0]
    n_sector = conn.execute("SELECT COUNT(*) FROM stock_sector").fetchone()[0]
    n_market = conn.execute("SELECT COUNT(*) FROM market_index").fetchone()[0]
    print("=" * 50)
    print("Summary:")
    print(f"  daily_kline rows: {n_kline:,}")
    print(f"  stock_daily_basic rows: {n_basic:,}")
    print(f"  stock_sector rows: {n_sector:,}")
    print(f"  market_index rows: {n_market:,}")

    conn.close()
    print("All done!")


if __name__ == "__main__":
    main()
