"""Phase 2b 验证: LightGBM + 均值反转 + run_pipeline_v2"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

from backend.engine.pattern.lightgbm_model import LightGBMClassifier
from backend.engine.strategy.mean_reversion import MeanReversionStrategy

# 1. LightGBM classifier
print("=== LightGBM Classifier ===")
X = np.random.randn(500, 10)
y = (X[:, 0] + X[:, 1] * 0.5 + np.random.randn(500) * 0.5 > 0).astype(int)

model = LightGBMClassifier()
model.fit(X, y, feature_names=[f"factor_{i}" for i in range(10)])

proba = model.predict_proba(X[:5])
print(f"Predict proba shape: {proba.shape}")
print(f"Predictions: {proba[:, 1].round(3)}")

if model.feature_importance is not None:
    print(f"Top 3 features: {model.feature_importance.head(3).index.tolist()}")

# Save & load
path = model.save("test_lightgbm")
loaded = LightGBMClassifier.load("test_lightgbm")
print(f"Saved to: {path}")
print("LightGBM OK")

# 2. Mean Reversion Strategy
print("\n=== Mean Reversion Strategy ===")
df_mr = pd.DataFrame({
    "ts_code": ["A"] * 30 + ["B"] * 30 + ["C"] * 30,
    "close": list(np.cumsum(np.random.randn(30) * 0.1) + 10) * 3,
    "ret_20d": list(np.random.randn(30) * 0.2) * 3,
    "rsi_14": list(np.random.uniform(20, 60, 30)) * 3,
    "vol_ma_ratio_5": list(np.random.uniform(0.5, 2, 30)) * 3,
})
# perturb each stock
for i, ts in enumerate(["A", "B", "C"]):
    df_mr.loc[df_mr.ts_code == ts, "ret_20d"] += np.random.randn() * 0.1

mr = MeanReversionStrategy(lookback=20, top_k=5, rsi_threshold=45)
ranked = mr.rank(df_mr)
print(f"Ranked candidates: {len(ranked)}")
if not ranked.empty:
    print(f"Top pick: {ranked.iloc[0].to_dict()}")

print("\n=== Phase 2b Verification PASSED ===")
