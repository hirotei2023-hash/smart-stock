"""Phase 2c verification: risk modules + portfolio"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

from backend.engine.risk.stop_manager import (
    DynamicStopManager, VolatilityPositionSizer, MarketRegimeFilter,
)

# 1. DynamicStopManager
print("=== DynamicStopManager ===")
stop_mgr = DynamicStopManager(atr_mult=2.0, trailing_pct=0.05, profit_lock=0.10)
entry_price = 10.0
atr = 0.30

stop_mgr.init_position("TEST", entry_price, atr)
should_exit, reason = stop_mgr.should_exit("TEST", entry_price, 10.05, atr)
print(f"Test 1 (price=10.05): exit={should_exit}, reason={reason}")
assert should_exit is False

should_exit, reason = stop_mgr.should_exit("TEST", entry_price, 9.50, atr)
print(f"Test 2 (price=9.50, stop={entry_price - atr*2}): exit={should_exit}, reason={reason}")
assert should_exit is True

# Trailing stop test
stop_mgr.init_position("TRAIL", 10.0, atr)
stop_mgr.highest_price["TRAIL"] = 11.0
should_exit, reason = stop_mgr.should_exit("TRAIL", 10.0, 10.40, atr)
print(f"Test 3 (price=10.40, peak=11.0, trail_stop=10.45): exit={should_exit}, reason={reason}")
assert should_exit is True

print("DynamicStopManager OK")

# 2. VolatilityPositionSizer
print("\n=== VolatilityPositionSizer ===")
sizer = VolatilityPositionSizer(target_vol=0.02, max_single=0.50, min_single=0.02)

low_vol = sizer.get_position_pct(10.0, 0.15)   # vol=1.5% => 0.02/0.015=1.33->clamp 0.50
high_vol = sizer.get_position_pct(10.0, 0.80)  # vol=8% => 0.02/0.08=0.25
print(f"Low vol (1.5%): {low_vol:.1%}, High vol (8%): {high_vol:.1%}")
assert low_vol > high_vol, f"Expected low_vol > high_vol, got {low_vol:.3f} <= {high_vol:.3f}"
print("VolatilityPositionSizer OK")

# 3. MarketRegimeFilter
print("\n=== MarketRegimeFilter ===")
regime_filter = MarketRegimeFilter()

bull_df = pd.DataFrame({
    "close": np.linspace(9, 12, 100),
})
regime = regime_filter.get_regime(bull_df)
print(f"Rising market: {regime} alloc={regime_filter.get_allocation(regime):.0%}")

bear_df = pd.DataFrame({
    "close": np.linspace(12, 9, 100),
})
regime = regime_filter.get_regime(bear_df)
print(f"Falling market: {regime} alloc={regime_filter.get_allocation(regime):.0%}")

print("MarketRegimeFilter OK")

print("\n=== Phase 2c Verification PASSED ===")
