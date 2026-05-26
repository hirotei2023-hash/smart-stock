"""LightGBM 分类器 — 替代 LSTM，用于 20 日涨跌概率预测"""
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from backend.config import MODEL_DIR


class LightGBMClassifier:
    def __init__(self, params: dict = None):
        self.params = params or {
            "objective": "binary",
            "metric": "auc",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_data_in_leaf": 50,
            "lambda_l1": 0.1,
            "lambda_l2": 1.0,
            "verbose": -1,
        }
        self.model = None
        self.feature_importance = None
        self.feature_names = None

    def fit(self, X, y, feature_names: list[str] = None, eval_set=None):
        import lightgbm as lgb

        self.feature_names = feature_names or (
            list(X.columns) if hasattr(X, "columns") else [f"f_{i}" for i in range(X.shape[1])]
        )

        if hasattr(X, "values"):
            X = X.values
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)

        train_data = lgb.Dataset(X, label=y, feature_name=self.feature_names)
        valid_sets = [train_data]
        if eval_set is not None:
            X_val, y_val = eval_set
            X_val = np.asarray(X_val.values if hasattr(X_val, "values") else X_val, dtype=np.float32)
            y_val = np.asarray(y_val, dtype=np.float32)
            valid_sets = [train_data, lgb.Dataset(X_val, label=y_val, feature_name=self.feature_names)]

        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=500,
            valid_sets=valid_sets,
            callbacks=[
                lgb.early_stopping(stopping_rounds=30),
                lgb.log_evaluation(period=0),
            ],
        )

        # Feature importance
        importance = self.model.feature_importance(importance_type="gain")
        self.feature_importance = pd.Series(importance, index=self.feature_names).sort_values(ascending=False)

        return self

    def predict_proba(self, X) -> np.ndarray:
        if hasattr(X, "values"):
            X = X.values
        X = np.asarray(X, dtype=np.float32)
        pos_idx = 1 if self.params.get("objective") == "binary" else 0
        proba_1 = self.model.predict(X)
        proba_0 = 1 - proba_1
        return np.column_stack([proba_0, proba_1])

    def predict(self, X) -> np.ndarray:
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)

    def save(self, name: str = "lightgbm"):
        path = Path(MODEL_DIR) / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(self, f)
        return path

    @classmethod
    def load(cls, name: str = "lightgbm"):
        path = Path(MODEL_DIR) / f"{name}.pkl"
        with open(path, "rb") as f:
            return pickle.load(f)
