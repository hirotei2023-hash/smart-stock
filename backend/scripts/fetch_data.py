"""一键拉取沪深300日线数据"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

from backend.engine.data.schema import get_connection, init_db
from backend.engine.data.collector import fetch_all_hs300

if __name__ == "__main__":
    init_db()
    conn = get_connection()
    stocks = fetch_all_hs300(conn, delay=0.5)
    print(f"\nDone. {len(stocks)} stocks fetched.")
    conn.close()
