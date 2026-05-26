"""每日自动更新: 拉取最新K线 → 扫描信号 → 覆盖写入"""
import sys, io, gc, time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.engine.data.schema import get_connection, init_db
from backend.engine.data.collector import fetch_daily_kline
from backend.engine.scoring.composite import scan_all_stocks, save_signals_to_db


def main():
    conn = get_connection()
    init_db()

    # 1. 获取所有已跟踪的股票
    stocks = conn.execute("SELECT ts_code, name FROM stock_basic").fetchall()
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 开始每日更新, {len(stocks)} 只股票")

    # 2. 拉取最近 7 天的K线（覆盖周末和假期）
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
    print(f"  拉取区间: {start_date} ~ {end_date}")

    new_dates = set()
    success = 0
    for i, (ts_code, name) in enumerate(stocks):
        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(stocks)}] 已拉取...")
        try:
            df = fetch_daily_kline(ts_code, start_date, end_date)
            if not df.empty:
                for _, row in df.iterrows():
                    trade_date = str(row["trade_date"])
                    new_dates.add(trade_date)
                    conn.execute(
                        """INSERT OR REPLACE INTO daily_kline
                           (ts_code, trade_date, open, high, low, close, volume, amount, turnover, pct_chg)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ts_code, trade_date, row["open"], row["high"],
                         row["low"], row["close"], row["volume"],
                         row.get("amount"), row.get("turnover"), row.get("pct_chg"))
                    )
                success += 1
        except Exception as e:
            print(f"  [WARN] {ts_code} {name}: {e}")
        time.sleep(0.3)  # 限速，避免被封

    conn.commit()
    print(f"  拉取完成: {success}/{len(stocks)} 成功, {len(new_dates)} 个新日期")

    # 3. 对新日期执行扫描
    if new_dates:
        already = set(
            r[0] for r in conn.execute(
                "SELECT DISTINCT trade_date FROM signals"
            ).fetchall()
        )
        todo = sorted(d for d in new_dates if d not in already)
        print(f"  需扫描 {len(todo)} 个新日期: {todo}")

        total_new = 0
        for date in todo:
            print(f"  扫描 {date}...")
            try:
                signals = scan_all_stocks(conn, date)
            except Exception as e:
                print(f"    ERROR: {e}")
                continue
            total_new += len(signals)
            if signals:
                conn.execute("DELETE FROM signals WHERE trade_date=?", (date,))
                save_signals_to_db(conn, signals)
            gc.collect()

        print(f"  新增 {total_new} 条信号")
    else:
        print(f"  无新数据，跳过扫描")

    # 4. 汇总
    final_count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    latest = conn.execute("SELECT MAX(trade_date) FROM signals").fetchone()[0]
    print(f"更新完成! 共 {final_count} 条信号, 最新日期 {latest}")
    conn.close()


if __name__ == "__main__":
    main()
