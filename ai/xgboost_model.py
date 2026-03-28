"""
XGBoost 预测模型：基于历史赔率特征预测比赛结果（主胜/平/客胜）。
支持训练、保存/加载、预测，以及特征重要性分析。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, log_loss
from sklearn.model_selection import TimeSeriesSplit

from ai.features import build_dataset, get_feature_columns

LABEL_MAP = {0: "H", 1: "D", 2: "A"}
LABEL_NAMES = ["主胜(H)", "平(D)", "客胜(A)"]

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"


def default_xgb_params() -> dict[str, Any]:
    return {
        "objective": "multi:softprob",
        "num_class": 3,
        "eval_metric": "mlogloss",
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "gamma": 0.1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "seed": 42,
        "verbosity": 0,
    }


class MatchPredictor:
    """足彩比赛结果预测器。"""

    def __init__(self, params: dict | None = None, n_rounds: int = 500):
        self.params = params or default_xgb_params()
        self.n_rounds = n_rounds
        self.model: xgb.Booster | None = None
        self.feature_names: list[str] = []
        self.metadata: dict[str, Any] = {}

    def train(self, df: pd.DataFrame, feature_cols: list[str] | None = None,
              eval_ratio: float = 0.15) -> dict[str, Any]:
        """
        训练模型。df 必须包含 'target' 列和特征列。
        按时间顺序划分训练/验证集（不能随机打乱，因为是时间序列）。
        返回训练结果摘要。
        """
        if feature_cols is None:
            feature_cols = get_feature_columns(df)

        self.feature_names = feature_cols
        valid = df.dropna(subset=["target"])

        X = valid[feature_cols].copy()
        y = valid["target"].values.astype(int)

        X = X.fillna(-999)
        X = X.replace([np.inf, -np.inf], -999)

        # 时间序列划分（最后 eval_ratio 作为验证集）
        split_idx = int(len(X) * (1 - eval_ratio))
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_cols)
        dval = xgb.DMatrix(X_val, label=y_val, feature_names=feature_cols)

        evals_result: dict = {}
        self.model = xgb.train(
            self.params,
            dtrain,
            num_boost_round=self.n_rounds,
            evals=[(dtrain, "train"), (dval, "eval")],
            evals_result=evals_result,
            early_stopping_rounds=50,
            verbose_eval=False,
        )

        # 验证集评估
        val_probs = self.model.predict(dval)
        val_preds = np.argmax(val_probs, axis=1)
        acc = accuracy_score(y_val, val_preds)
        ll = log_loss(y_val, val_probs)

        report = classification_report(y_val, val_preds, target_names=LABEL_NAMES, output_dict=True)

        self.metadata = {
            "train_size": len(X_train),
            "val_size": len(X_val),
            "feature_count": len(feature_cols),
            "best_iteration": self.model.best_iteration,
            "val_accuracy": acc,
            "val_logloss": ll,
            "val_report": report,
        }

        return self.metadata

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """预测概率。返回 (n_samples, 3) 的数组，列为 [主胜, 平, 客胜]。"""
        if self.model is None:
            raise RuntimeError("模型未训练或未加载")
        available = [c for c in self.feature_names if c in df.columns]
        missing = [c for c in self.feature_names if c not in df.columns]
        X = df[available].copy()
        for c in missing:
            X[c] = -999
        X = X[self.feature_names].fillna(-999).replace([np.inf, -np.inf], -999)
        for c in X.columns:
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(-999)
        dmat = xgb.DMatrix(X, feature_names=self.feature_names)
        return self.model.predict(dmat)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """预测并返回带概率和推荐结果的 DataFrame。"""
        probs = self.predict_proba(df)
        result = df[["match_id", "home_team", "away_team", "match_date", "division"]].copy()
        result["prob_home"] = probs[:, 0]
        result["prob_draw"] = probs[:, 1]
        result["prob_away"] = probs[:, 2]
        result["pred_idx"] = np.argmax(probs, axis=1)
        result["pred_label"] = result["pred_idx"].map(LABEL_MAP)
        result["confidence"] = np.max(probs, axis=1)
        return result

    def feature_importance(self, importance_type: str = "gain") -> pd.DataFrame:
        """返回特征重要性排名。"""
        if self.model is None:
            raise RuntimeError("模型未训练")
        scores = self.model.get_score(importance_type=importance_type)
        imp = pd.DataFrame([
            {"feature": k, "importance": v} for k, v in scores.items()
        ]).sort_values("importance", ascending=False).reset_index(drop=True)
        return imp

    def save(self, path: str | Path | None = None) -> Path:
        """保存模型和元数据。"""
        if self.model is None:
            raise RuntimeError("模型未训练")
        d = Path(path) if path else DEFAULT_MODEL_DIR
        d.mkdir(parents=True, exist_ok=True)
        model_path = d / "xgb_match_predictor.json"
        meta_path = d / "xgb_metadata.json"
        features_path = d / "xgb_features.json"

        self.model.save_model(str(model_path))

        meta = {k: v for k, v in self.metadata.items() if k != "val_report"}
        meta["val_report_summary"] = {
            k: {"precision": v.get("precision", 0), "recall": v.get("recall", 0), "f1-score": v.get("f1-score", 0)}
            for k, v in self.metadata.get("val_report", {}).items()
            if isinstance(v, dict) and "precision" in v
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

        with open(features_path, "w", encoding="utf-8") as f:
            json.dump(self.feature_names, f)

        return model_path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "MatchPredictor":
        """加载已保存的模型。"""
        d = Path(path) if path else DEFAULT_MODEL_DIR
        model_path = d / "xgb_match_predictor.json"
        meta_path = d / "xgb_metadata.json"
        features_path = d / "xgb_features.json"

        predictor = cls()
        predictor.model = xgb.Booster()
        predictor.model.load_model(str(model_path))

        with open(features_path, "r") as f:
            predictor.feature_names = json.load(f)

        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                predictor.metadata = json.load(f)

        return predictor
