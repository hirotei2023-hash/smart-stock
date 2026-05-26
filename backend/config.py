from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "stock.db"
MODEL_DIR = ROOT / "models_saved"
MODEL_DIR.mkdir(exist_ok=True)

# 股票池：沪深300 + 中证500（Phase 2）
HS300_STOCKS: list[str] = []  # 运行时从 akshare 获取
CSI500_STOCKS: list[str] = []

# 数据参数
DATA_YEARS = 6
DATA_CYCLE = "daily"  # daily/weekly/monthly

# 模型参数
LSTM_SEQ_LEN = 60       # 输入序列长度（交易日）
LSTM_HIDDEN = 128
LSTM_LAYERS = 2
LSTM_DROPOUT = 0.2

# 回测参数
INITIAL_CAPITAL = 100_000  # 初始资金 10 万
COMMISSION_RATE = 0.00025  # 万 2.5
STAMP_TAX_RATE = 0.001    # 千 1 (卖出)
SLIPPAGE = 0.001          # 0.1%
SINGLE_POSITION_MAX = 0.2 # 单票最大 20%
TOTAL_POSITION_MAX = 0.8  # 总仓位最大 80%

# 预警阈值
ALERT_MA_PERIODS = [5, 10, 20, 60]
ALERT_VOLUME_RATIO = 2.0
ALERT_DROP_PCT = -0.03
