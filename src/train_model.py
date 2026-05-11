"""
train_model.py
--------------
Trains an XGBoost ranking model on offline features.
Supports shadow model (Model B) for A/B comparison.
"""

import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, ndcg_score
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH  = os.path.join(BASE_DIR, "models", "ranker.json")
SHADOW_PATH = os.path.join(BASE_DIR, "models", "ranker_shadow.json")
METRICS_PATH = os.path.join(BASE_DIR, "models", "metrics.json")

FEATURE_COLS = [
    "user_click_rate_7d",
    "user_avg_watch_time_7d",
    "video_ctr_24h",
    "creator_engagement_7d",
    "user_category_affinity_30d",
    "video_freshness_hours",
]


def train(df: pd.DataFrame, model_path: str = None,
          shadow: bool = False) -> dict:
    if model_path is None:
        model_path = MODEL_PATH

    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    X = df[FEATURE_COLS].fillna(0)
    y = df["label"].astype(int)

    # Need at least 2 classes
    if y.nunique() < 2:
        print("WARNING: only one class in labels, adding synthetic row")
        import pandas as pd
        synthetic = X.iloc[0:1].copy()
        X = pd.concat([X, synthetic], ignore_index=True)
        y = pd.concat([y, pd.Series([1 - y.iloc[0]])], ignore_index=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    params = dict(
        n_estimators=200, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="auc", random_state=42 if not shadow else 99,
    )
    if shadow:
        params.update(n_estimators=100, max_depth=4)

    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              verbose=False)

    y_prob = model.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)
    ndcg   = ndcg_score(
        y_test.values[:100].reshape(1, -1),
        y_prob[:100].reshape(1, -1),
        k=10,
    )

    metrics = {
        "auc":        round(float(auc),  4),
        "ndcg_at_10": round(float(ndcg), 4),
        "n_train":    int(len(X_train)),
        "n_test":     int(len(X_test)),
        "model":      "shadow" if shadow else "production",
        "features":   FEATURE_COLS,
        "importance": {
            k: round(float(v), 4)
            for k, v in zip(FEATURE_COLS, model.feature_importances_)
        },
    }

    model.save_model(model_path)
    label = "Shadow" if shadow else "Production"
    print(f"{label} model saved -> AUC={auc:.4f}  NDCG@10={ndcg:.4f}")

    if not shadow:
        with open(METRICS_PATH, "w") as f:
            json.dump(metrics, f, indent=2)

    return metrics


def load_model(path: str = None) -> xgb.XGBClassifier:
    if path is None:
        path = MODEL_PATH
    model = xgb.XGBClassifier()
    model.load_model(path)
    return model


def predict_scores(model: xgb.XGBClassifier,
                   feature_rows: list) -> list:
    df = pd.DataFrame(feature_rows)[FEATURE_COLS].fillna(0)
    return model.predict_proba(df)[:, 1].tolist()


if __name__ == "__main__":
    from offline_features import load_offline_features
    df = load_offline_features()
    print(f"Training on {len(df):,} rows...")
    train(df, shadow=False)
    train(df, model_path=SHADOW_PATH, shadow=True)
