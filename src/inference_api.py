"""
inference_api.py
----------------
FastAPI real-time ranking endpoint.
Run from the src/ directory:
  uvicorn inference_api:app --reload --port 8000
"""

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

import redis
import xgboost as xgb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REDIS_HOST  = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT  = int(os.getenv("REDIS_PORT", 6379))
MODEL_PATH  = os.path.join(os.path.dirname(__file__), "..", "models", "ranker.json")
SHADOW_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "ranker_shadow.json")

FEATURE_COLS = [
    "user_click_rate_7d",
    "user_avg_watch_time_7d",
    "video_ctr_24h",
    "creator_engagement_7d",
    "user_category_affinity_30d",
    "video_freshness_hours",
]

_redis_client = None
_model        = None
_shadow_model = None
_request_log  = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client, _model, _shadow_model
    _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                decode_responses=True)
    _model = xgb.XGBClassifier()
    _model.load_model(MODEL_PATH)
    try:
        _shadow_model = xgb.XGBClassifier()
        _shadow_model.load_model(SHADOW_PATH)
        print("Shadow model loaded.")
    except Exception:
        _shadow_model = None
        print("No shadow model found.")
    print("StreamRank API ready.")
    yield


app = FastAPI(title="StreamRank Inference API", version="1.0.0",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RankRequest(BaseModel):
    user_id: str
    candidate_video_ids: list[str]
    return_shadow: bool = False


class VideoScore(BaseModel):
    video_id: str
    score: float
    shadow_score: Optional[float] = None


class RankResponse(BaseModel):
    user_id:            str
    ranked_videos:      list[VideoScore]
    latency_ms:         float
    feature_latency_ms: float
    model_version:      str = "production"


def _get_features(user_id: str, video_id: str) -> dict:
    user_raw  = _redis_client.get(f"user:{user_id}:features")
    video_raw = _redis_client.get(f"video:{video_id}:features")
    user_feats  = json.loads(user_raw)  if user_raw  else {}
    video_feats = json.loads(video_raw) if video_raw else {}
    return {
        "user_click_rate_7d":         user_feats.get("click_rate_7d",        0.1),
        "user_avg_watch_time_7d":     user_feats.get("avg_watch_time_7d",    60.0),
        "video_ctr_24h":              video_feats.get("ctr_24h",             0.05),
        "creator_engagement_7d":      video_feats.get("creator_engagement_7d", 0.1),
        "user_category_affinity_30d": user_feats.get("category_affinity_30d", 0.1),
        "video_freshness_hours":      video_feats.get("freshness_hours",     48.0),
    }


@app.post("/rank", response_model=RankResponse)
async def rank(req: RankRequest):
    import pandas as pd

    t0 = time.perf_counter()

    ft0 = time.perf_counter()
    feature_rows = [_get_features(req.user_id, vid)
                    for vid in req.candidate_video_ids]
    feature_latency = (time.perf_counter() - ft0) * 1000

    df     = pd.DataFrame(feature_rows)[FEATURE_COLS].fillna(0)
    scores = _model.predict_proba(df)[:, 1].tolist()
    shadow = (_shadow_model.predict_proba(df)[:, 1].tolist()
              if _shadow_model and req.return_shadow else None)

    ranked = sorted(
        zip(req.candidate_video_ids, scores,
            shadow or [None] * len(scores)),
        key=lambda x: x[1], reverse=True
    )

    latency_ms = (time.perf_counter() - t0) * 1000
    _request_log.append({
        "user_id":      req.user_id,
        "latency_ms":   round(latency_ms, 2),
        "n_candidates": len(req.candidate_video_ids),
        "top_score":    round(ranked[0][1], 4) if ranked else 0,
    })
    if len(_request_log) > 1000:
        _request_log.pop(0)

    return RankResponse(
        user_id=req.user_id,
        ranked_videos=[
            VideoScore(video_id=vid, score=round(s, 4),
                       shadow_score=round(ss, 4) if ss else None)
            for vid, s, ss in ranked
        ],
        latency_ms=round(latency_ms, 2),
        feature_latency_ms=round(feature_latency, 2),
    )


@app.get("/health")
async def health():
    try:
        _redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status":       "ok" if redis_ok else "degraded",
        "redis":        redis_ok,
        "model":        _model is not None,
        "shadow_model": _shadow_model is not None,
    }


@app.get("/metrics/latency")
async def latency_metrics():
    if not _request_log:
        return {"message": "No requests yet"}
    import numpy as np
    lats = [r["latency_ms"] for r in _request_log]
    return {
        "n_requests": len(lats),
        "mean_ms":    round(float(np.mean(lats)), 2),
        "p50_ms":     round(float(np.percentile(lats, 50)), 2),
        "p95_ms":     round(float(np.percentile(lats, 95)), 2),
        "p99_ms":     round(float(np.percentile(lats, 99)), 2),
        "recent":     _request_log[-20:],
    }


@app.get("/metrics/skew")
async def skew_metrics():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "skew_metrics.json")
    if not os.path.exists(path):
        return {"message": "Run python run_pipeline.py first."}
    with open(path) as f:
        return json.load(f)


@app.get("/metrics/model")
async def model_metrics():
    path = os.path.join(os.path.dirname(__file__), "..", "models", "metrics.json")
    if not os.path.exists(path):
        return {"message": "Run python run_pipeline.py first."}
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.inference_api:app", host="0.0.0.0", port=8000, reload=True)
