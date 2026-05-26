"""Historical scan V3: 全量历史扫描（每个交易日）"""
import sys, io, gc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend.engine.data.schema import get_connection, init_db
from backend.engine.scoring.composite import scan_all_stocks, save_signals_to_db


def main():
    conn = get_connection()
    init_db()

    all_dates = [
        row[0] for row in conn.execute(
            "SELECT DISTINCT trade_date FROM daily_kline "
            "WHERE trade_date >= '2025-10-09' ORDER BY trade_date"
        ).fetchall()
    ]
    print(f"Total trading days: {len(all_dates)} ({all_dates[0]} ~ {all_dates[-1]})")

    total_signals = 0
    for i, date in enumerate(all_dates):
        print(f"\n[{i+1}/{len(all_dates)}] {date}...")
        try:
            signals = scan_all_stocks(conn, date)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        total_signals += len(signals)
        print(f"  -> {len(signals)} signals (running total: {total_signals})")

        if signals:
            conn.execute("DELETE FROM signals WHERE trade_date=?", (date,))
            save_signals_to_db(conn, signals)

        if (i + 1) % 20 == 0:
            gc.collect()

    final = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    dc = conn.execute("SELECT COUNT(DISTINCT trade_date) FROM signals").fetchone()[0]
    print(f"\nDone! {final} signals across {dc} dates")
    conn.close()


if __name__ == "__main__":
    main()
