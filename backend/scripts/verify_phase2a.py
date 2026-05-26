"""Phase 2a 验证脚本: 因子库 + Walk-Forward 验证"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

from backend.engine.factors.library import compute_all_factors, ALL_FACTORS
from backend.engine.backtest.validation import WalkForwardValidator

# 1. Factor library
print("=== Factor Library ===")
print(f"Total factors: {len(ALL_FACTORS)}")

# Test with synthetic data
df = pd.DataFrame({
    "open": 10 + np.random.randn(200) * 0.5,
    "high": 10.5 + np.random.randn(200) * 0.5,
    "low": 9.5 + np.random.randn(200) * 0.5,
    "close": 10 + np.random.randn(200).cumsum() * 0.1,
    "volume": 1e7 + np.random.randn(200) * 1e6,
    "amount": 1e8 + np.random.randn(200) * 1e7,
    "turnover": np.random.rand(200) * 5,
    "pct_chg": np.random.randn(200),
})
df["high"] = df[["open", "high", "low", "close"]].max(axis=1) + 0.2
df["low"] = df[["open", "high", "low", "close"]].min(axis=1) - 0.2

factors = compute_all_factors(df)
print(f"Factor DataFrame shape: {factors.shape}")
non_null = factors.iloc[-1].notna().sum()
print(f"Non-null factors (last row): {non_null}/{len(ALL_FACTORS)}")

# 2. Walk-Forward validator
print("\n=== Walk-Forward Validator ===")
wf_df = pd.DataFrame({
    "f1": np.random.randn(1500),
    "f2": np.random.randn(1500),
    "label": (np.random.randn(1500) > 0).astype(int),
})

wf = WalkForwardValidator(train_years=3, test_months=6, step_months=3)
splits = wf.split(wf_df)
print(f"Splits: {len(splits)}")

result = wf.evaluate(lambda: LogisticRegression(), wf_df, ["f1", "f2"], "label")
print(f"n_splits: {result['n_splits']}, mean_auc: {result['mean_auc']:.4f}")

print("\n=== Phase 2a Verification PASSED ===")
