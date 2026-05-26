"""Walk-Forward (滚动前向) 验证框架

将时间序列数据切分为多个 train/test split，每次用历史数据训练、未来数据测试，
避免前视偏差（look-ahead bias）。

核心设计原则：
- 按自然月切分，而非交易日天数（交易日天数在不同年份分布不均）
- 每个 split 独立做特征标准化，杜绝数据泄露
- 支持 model_builder 返回 (model, scaler) 或单纯 model
"""

from typing import Any, Callable, Optional, Union

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class WalkForwardValidator:
    """Walk-forward (滚动前向) 验证框架

    将时间序列数据切分为多个 train/test split，每次用历史数据训练、未来数据测试，
    避免前视偏差（look-ahead bias）。

    示例: train_years=3, test_months=6, step_months=3

    - Split 1: train=[2019-01 to 2021-12], test=[2022-01 to 2022-06]
    - Split 2: train=[2019-04 to 2022-03], test=[2022-04 to 2022-09]
    - Split 3: train=[2019-07 to 2022-06], test=[2022-07 to 2022-12]
    - ...
    """

    def __init__(
        self,
        train_years: int = 3,
        test_months: int = 6,
        step_months: int = 3,
    ):
        """初始化 Walk-Forward 验证器。

        参数:
            train_years: 训练窗口长度（年），例如 3 表示用过去 3 年的数据训练
            test_months: 测试窗口长度（月），例如 6 表示预测未来 6 个月
            step_months: 每次窗口滑动的步长（月），例如 3 表示每季度滚动一次
        """
        if train_years < 1:
            raise ValueError(f"train_years 必须 >= 1，当前值: {train_years}")
        if test_months < 1:
            raise ValueError(f"test_months 必须 >= 1，当前值: {test_months}")
        if step_months < 1:
            raise ValueError(f"step_months 必须 >= 1，当前值: {step_months}")

        self.train_years = train_years
        self.test_months = test_months
        self.step_months = step_months

    # ── 公共 API ──────────────────────────────────────────────

    def split(
        self,
        df: pd.DataFrame,
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """按自然月切分时间序列为 train/test 窗口。

        每个 split 的 test 时间段严格在 train 时间段之后，
        杜绝前视偏差。

        参数:
            df: 包含 trade_date 列的 DataFrame，应按日期升序排列

        返回:
            [(train_df, test_df), ...]
            每个元组的 train 和 test 按时间严格分离（test 在 train 之后）
        """
        if len(df) == 0:
            return []

        df = df.copy()

        # 统一 trade_date 为 datetime 类型
        if not pd.api.types.is_datetime64_any_dtype(df["trade_date"]):
            df["trade_date"] = pd.to_datetime(df["trade_date"])

        # 按自然月分组
        df["_ym"] = df["trade_date"].dt.to_period("M")
        months = sorted(df["_ym"].unique())

        train_months = self.train_years * 12
        splits: list[tuple[pd.DataFrame, pd.DataFrame]] = []

        # 滑动窗口：从第 train_months 个月开始作为第一个测试窗口的起点
        test_start_pos = train_months

        while test_start_pos + self.test_months <= len(months):
            # train 窗口：[test_start - train_months, test_start - 1]
            train_start_month = months[test_start_pos - train_months]
            train_end_month = months[test_start_pos - 1]

            # test 窗口：[test_start, test_start + test_months - 1]
            test_start_month = months[test_start_pos]
            test_end_month = months[test_start_pos + self.test_months - 1]

            # 按月份区间筛选数据
            train_df = df[
                (df["_ym"] >= train_start_month)
                & (df["_ym"] <= train_end_month)
            ].drop(columns=["_ym"])

            test_df = df[
                (df["_ym"] >= test_start_month)
                & (df["_ym"] <= test_end_month)
            ].drop(columns=["_ym"])

            splits.append((train_df, test_df))

            # 窗口向前滑动
            test_start_pos += self.step_months

        return splits

    def evaluate(
        self,
        model_builder: Callable[[], Any],
        df: pd.DataFrame,
        feature_cols: list[str],
        label_col: str,
        min_train_samples: int = 100,
        min_test_samples: int = 20,
    ) -> dict:
        """对每个 split 执行训练+预测，汇总所有样本外预测结果。

        参数:
            model_builder: 可调用对象，每次调用返回一个新模型实例。
                           - 返回 model: 直接使用原始特征训练和预测
                           - 返回 (model, scaler): 用 train 数据 fit scaler，
                             然后 transform train 和 test，再训练和预测
            df: 包含特征列和标签列的完整 DataFrame（需含 trade_date 列）
            feature_cols: 特征列名列表
            label_col: 标签列名
            min_train_samples: 单个 split 的 train 集最少样本数，不足则跳过
            min_test_samples: 单个 split 的 test 集最少样本数，不足则跳过

        返回:
            dict:
                - y_true: np.ndarray, 所有 test 样本的真实标签拼接
                - y_pred: np.ndarray, 所有 test 样本的预测标签拼接
                - y_prob: np.ndarray 或 None, 所有 test 样本的预测概率拼接
                - splits: list[dict], 每个 split 的详细指标
                - metrics: dict, 汇总指标 {accuracy, precision, recall, f1, auc}
        """
        splits = self.split(df)

        y_true_all: list[float] = []
        y_pred_all: list[float] = []
        y_prob_all: list[float] = []
        split_details: list[dict] = []

        for i, (train_df, test_df) in enumerate(splits):
            # 跳过样本量不足的 split
            if len(train_df) < min_train_samples or len(test_df) < min_test_samples:
                continue

            # 提取特征和标签
            X_train = train_df[feature_cols].values
            y_train = train_df[label_col].values
            X_test = test_df[feature_cols].values
            y_test = test_df[label_col].values

            # 丢弃包含 NaN 的行
            train_mask = ~np.isnan(X_train).any(axis=1)
            X_train = X_train[train_mask]
            y_train = y_train[train_mask]

            test_mask = ~np.isnan(X_test).any(axis=1)
            X_test = X_test[test_mask]
            y_test = y_test[test_mask]

            if (
                len(X_train) < min_train_samples
                or len(X_test) < min_test_samples
            ):
                continue

            # 构建模型（每次 split 独立构建，避免数据泄露）
            result = model_builder()

            if isinstance(result, tuple):
                # model_builder 返回 (model, scaler)
                model, scaler = result
                if scaler is not None:
                    X_train = scaler.fit_transform(X_train)
                    X_test = scaler.transform(X_test)
            else:
                model = result

            # 训练
            model.fit(X_train, y_train)

            # 预测
            y_pred = model.predict(X_test)

            # 尝试获取预测概率（分类器才有 predict_proba）
            y_prob: Optional[np.ndarray] = None
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X_test)
                # 二分类取正类概率，多分类保留全部分数
                if proba.shape[1] == 2:
                    y_prob = proba[:, 1]
                else:
                    y_prob = proba

            # 收集样本外预测
            y_true_all.extend(y_test.tolist())
            y_pred_all.extend(y_pred.tolist())
            if y_prob is not None:
                y_prob_all.extend(
                    y_prob.tolist()
                    if y_prob.ndim > 0
                    else [y_prob.tolist()]
                )

            # 计算当前 split 的指标
            split_metrics = self._compute_metrics(y_test, y_pred, y_prob)
            split_metrics["split"] = i
            split_metrics["train_dates"] = self._format_date_range(train_df)
            split_metrics["test_dates"] = self._format_date_range(test_df)
            split_metrics["train_size"] = len(train_df)
            split_metrics["test_size"] = len(test_df)
            split_details.append(split_metrics)

        # 汇总所有 split 的结果
        y_true_arr = np.array(y_true_all)
        y_pred_arr = np.array(y_pred_all)
        y_prob_arr = np.array(y_prob_all) if y_prob_all else None

        overall_metrics = self._compute_metrics(y_true_arr, y_pred_arr, y_prob_arr)
        overall_metrics["n_splits"] = len(split_details)
        overall_metrics["total_samples"] = len(y_true_arr)

        return {
            "y_true": y_true_arr,
            "y_pred": y_pred_arr,
            "y_prob": y_prob_arr,
            "splits": split_details,
            "metrics": overall_metrics,
        }

    # ── 内部方法 ──────────────────────────────────────────────

    @staticmethod
    def _compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: Optional[np.ndarray] = None,
    ) -> dict:
        """计算分类指标。

        参数:
            y_true: 真实标签
            y_pred: 预测标签
            y_prob: 预测概率（可选，用于 AUC）

        返回:
            dict: {accuracy, precision, recall, f1, auc}
        """
        if len(y_true) == 0:
            return {
                "accuracy": None,
                "precision": None,
                "recall": None,
                "f1": None,
                "auc": None,
            }

        labels = set(y_true)
        is_binary = len(labels) <= 2

        metrics: dict = {}
        metrics["accuracy"] = float(accuracy_score(y_true, y_pred))

        if is_binary:
            metrics["precision"] = float(
                precision_score(y_true, y_pred, zero_division=0)
            )
            metrics["recall"] = float(
                recall_score(y_true, y_pred, zero_division=0)
            )
            metrics["f1"] = float(f1_score(y_true, y_pred, zero_division=0))
        else:
            # 多分类使用 macro 平均
            metrics["precision"] = float(
                precision_score(y_true, y_pred, average="macro", zero_division=0)
            )
            metrics["recall"] = float(
                recall_score(y_true, y_pred, average="macro", zero_division=0)
            )
            metrics["f1"] = float(
                f1_score(y_true, y_pred, average="macro", zero_division=0)
            )

        # AUC：仅二分类且有概率可用时计算
        if y_prob is not None and is_binary and len(labels) > 1:
            try:
                if y_prob.ndim > 1 and y_prob.shape[1] == 2:
                    prob_for_auc = y_prob[:, 1]
                else:
                    prob_for_auc = y_prob
                metrics["auc"] = float(roc_auc_score(y_true, prob_for_auc))
            except (ValueError, IndexError):
                metrics["auc"] = None
        else:
            metrics["auc"] = None

        return metrics

    @staticmethod
    def _format_date_range(df: pd.DataFrame) -> str:
        """格式化 DataFrame 的日期范围，用于显示 split 的时间跨度。"""
        if "trade_date" not in df.columns or len(df) == 0:
            return "N/A"

        dates = pd.to_datetime(df["trade_date"])
        start = dates.min().strftime("%Y-%m-%d")
        end = dates.max().strftime("%Y-%m-%d")
        return f"{start} -> {end}"
