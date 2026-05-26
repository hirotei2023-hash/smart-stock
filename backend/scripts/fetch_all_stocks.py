"""补全全市场A股K线数据（排除科创板、北交所、ST）"""
import sys, io, time, gc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import akshare as ak
from backend.engine.data.schema import get_connection, init_db
from backend.engine.data.collector import fetch_daily_kline


def main():
    conn = get_connection()
    init_db()

    # 1. 获取全市场股票列表
    print("获取全市场股票列表...")
    all_stocks = ak.stock_info_a_code_name()
    print(f"全市场: {len(all_stocks)} 只")

    # 2. 过滤: 排除科创板(688)、北交所(8开头)、ST
    excluded = all_stocks[
        all_stocks['code'].str.startswith('688') |
        all_stocks['code'].str.match(r'^8[0-7]') |
        all_stocks['name'].str.contains('ST', na=False)
    ]
    target = all_stocks[
        ~all_stocks['code'].str.startswith('688') &
        ~all_stocks['code'].str.match(r'^8[0-7]') &
        ~all_stocks['name'].str.contains('ST', na=False)
    ]
    print(f"排除 {len(excluded)} 只 (科创/北交/ST), 目标 {len(target)} 只")

    # 3. 检查哪些已在库中
    existing = set(
        r[0] for r in conn.execute("SELECT ts_code FROM stock_basic").fetchall()
    )
    new_stocks = target[~target['code'].isin(existing)]
    print(f"已在库: {len(existing)}, 需新增: {len(new_stocks)}")

    if len(new_stocks) == 0:
        print("无需补充!")
        conn.close()
        return

    # 4. 写入 stock_basic
    for _, row in new_stocks.iterrows():
        conn.execute(
            "INSERT OR REPLACE INTO stock_basic (ts_code, name) VALUES (?, ?)",
            (row['code'], row['name'])
        )
    conn.commit()

    # 5. 逐只拉取K线
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=6*366)).strftime("%Y%m%d")

    total = len(new_stocks)
    success = 0
    fail = 0
    start_time = time.time()

    for i, (_, row) in enumerate(new_stocks.iterrows()):
        ts_code = row['code']
        name = row['name']

        elapsed = time.time() - start_time
        avg = elapsed / (i + 1) if i > 0 else 0
        eta = avg * (total - i - 1)
        if (i + 1) % 50 == 0 or i < 3:
            print(f"[{i+1}/{total}] {ts_code} {name} | 成功:{success} 失败:{fail} | ETA: {eta/60:.0f}min")

        try:
            df = fetch_daily_kline(ts_code, start_date, end_date)
            if not df.empty:
                for _, kr in df.iterrows():
                    conn.execute(
                        """INSERT OR REPLACE INTO daily_kline
                           (ts_code, trade_date, open, high, low, close, volume, amount, turnover, pct_chg)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ts_code, str(kr["trade_date"]), kr["open"], kr["high"],
                         kr["low"], kr["close"], kr["volume"],
                         kr.get("amount"), kr.get("turnover"), kr.get("pct_chg"))
                    )
                success += 1
            else:
                fail += 1
        except Exception as e:
            fail += 1
            if fail <= 5:
                print(f"  [ERR] {ts_code} {name}: {e}")

        if (i + 1) % 100 == 0:
            conn.commit()
            gc.collect()

        time.sleep(0.15)  # 限速

    conn.commit()

    # 6. 汇总
    final_stocks = conn.execute("SELECT COUNT(*) FROM stock_basic").fetchone()[0]
    final_kline = conn.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    latest = conn.execute("SELECT MAX(trade_date) FROM daily_kline").fetchone()[0]

    elapsed = time.time() - start_time
    print(f"\n完成! {elapsed/60:.1f}分钟")
    print(f"股票: {final_stocks} | K线: {final_kline}行 | 最新: {latest}")
    print(f"成功: {success}, 失败: {fail}")
    conn.close()


if __name__ == "__main__":
    main()
