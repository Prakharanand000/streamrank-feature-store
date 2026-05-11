"""
inference_api.py
----------------
FastAPI real-time ranking endpoint.
Run from the src/ directory:
  uvicorn inference_api:app --reload --port 8000

Resilience:
- /rank works WITHOUT Redis. If Redis is unreachable or a key is missing,
  features fall back to deterministic demo values derived from user_id/video_id
  so rankings stay coherent across calls in demo mode.
- /metrics/model and /metrics/skew read committed demo JSON files if the
  pipeline hasn't been run yet.
"""

import hashlib
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import redis
import xgboost as xgb
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REDIS_HOST  = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT  = int(os.getenv("REDIS_PORT", 6379))
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH  = os.path.join(BASE_DIR, "models", "ranker.json")
SHADOW_PATH = os.path.join(BASE_DIR, "models", "ranker_shadow.json")

FEATURE_COLS = [
    "user_click_rate_7d",
    "user_avg_watch_time_7d",
    "video_ctr_24h",
    "creator_engagement_7d",
    "user_category_affinity_30d",
    "video_freshness_hours",
]

_redis_client      = None
_redis_available   = False
_model             = None
_shadow_model      = None
_request_log: list = []


# ── deterministic demo features ──────────────────────────────────────────────
def _hash_float(*parts: str, salt: str = "", lo: float = 0.0, hi: float = 1.0
                ) -> float:
    """Hash inputs to a stable float in [lo, hi]. Same inputs => same output."""
    h = hashlib.md5("|".join([*parts, salt]).encode()).hexdigest()
    # Use first 8 hex chars => int => normalize to [0, 1)
    return lo + (hi - lo) * (int(h[:8], 16) / 0xFFFFFFFF)


def _demo_features(user_id: str, video_id: str) -> dict:
    """
    Deterministic demo feature values used when Redis is unavailable.
    Same (user, video) pair always returns the same features, so rankings
    are stable across calls in demo mode.
    """
    return {
        "user_click_rate_7d":         round(_hash_float(user_id, salt="ucr",  lo=0.02, hi=0.35), 4),
        "user_avg_watch_time_7d":     round(_hash_float(user_id, salt="uawt", lo=15.0, hi=180.0), 2),
        "video_ctr_24h":              round(_hash_float(video_id, salt="vctr", lo=0.01, hi=0.25), 4),
        "creator_engagement_7d":      round(_hash_float(video_id, salt="ceng", lo=0.05, hi=0.40), 4),
        "user_category_affinity_30d": round(_hash_float(user_id, video_id, salt="ucaf", lo=0.0, hi=0.6), 4),
        "video_freshness_hours":      round(_hash_float(video_id, salt="vfr", lo=2.0, hi=240.0), 2),
    }


def _try_redis_features(user_id: str, video_id: str) -> Optional[dict]:
    """Return real features from Redis or None if anything fails / is missing."""
    if not _redis_available or _redis_client is None:
        return None
    try:
        user_raw  = _redis_client.get(f"user:{user_id}:features")
        video_raw = _redis_client.get(f"video:{video_id}:features")
    except Exception:
        return None

    if not user_raw or not video_raw:
        return None

    try:
        u = json.loads(user_raw)
        v = json.loads(video_raw)
    except Exception:
        return None

    return {
        "user_click_rate_7d":         u.get("click_rate_7d"),
        "user_avg_watch_time_7d":     u.get("avg_watch_time_7d"),
        "video_ctr_24h":              v.get("ctr_24h"),
        "creator_engagement_7d":      v.get("creator_engagement_7d"),
        "user_category_affinity_30d": u.get("category_affinity_30d"),
        "video_freshness_hours":      v.get("freshness_hours"),
    }


def _get_features(user_id: str, video_id: str) -> tuple[dict, str]:
    """
    Get features for (user, video). Returns (features, source) where source
    is 'redis', 'demo', or 'mixed'.
    """
    demo    = _demo_features(user_id, video_id)
    real    = _try_redis_features(user_id, video_id)
    if real is None:
        return demo, "demo"

    # If Redis returned partial data, fill gaps from demo (mixed mode)
    merged   = {k: (real[k] if real[k] is not None else demo[k]) for k in demo}
    used_any = any(real[k] is None for k in real)
    return merged, "mixed" if used_any else "redis"


# ── lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client, _redis_available, _model, _shadow_model

    # Redis (best effort)
    _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                decode_responses=True,
                                socket_connect_timeout=1)
    try:
        _redis_client.ping()
        _redis_available = True
        print("Redis: connected")
    except Exception as e:
        _redis_available = False
        print(f"Redis: not available ({e}) - using demo feature fallback")

    # Production model
    try:
        _model = xgb.XGBClassifier()
        _model.load_model(MODEL_PATH)
        print("Production model: loaded")
    except Exception as e:
        _model = None
        print(f"Production model: NOT loaded ({e})")

    # Shadow model
    try:
        _shadow_model = xgb.XGBClassifier()
        _shadow_model.load_model(SHADOW_PATH)
        print("Shadow model: loaded")
    except Exception:
        _shadow_model = None
        print("Shadow model: not loaded (optional)")

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


# ── schemas ───────────────────────────────────────────────────────────────────
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
    feature_source:     str = "redis"
    model_version:      str = "production"


# ── /rank ─────────────────────────────────────────────────────────────────────
@app.post("/rank", response_model=RankResponse)
async def rank(req: RankRequest):
    import pandas as pd

    if _model is None:
        # Model missing - rare, but degrade gracefully with random scores
        ranked = [(vid, _hash_float(req.user_id, vid, lo=0.05, hi=0.95), None)
                  for vid in req.candidate_video_ids]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return RankResponse(
            user_id=req.user_id,
            ranked_videos=[
                VideoScore(video_id=vid, score=round(s, 4))
                for vid, s, _ in ranked
            ],
            latency_ms=0.0, feature_latency_ms=0.0,
            feature_source="demo", model_version="fallback-hash",
        )

    t0 = time.perf_counter()

    # Fetch features (Redis if available, else deterministic demo)
    ft0 = time.perf_counter()
    feature_rows  = []
    sources_seen  = set()
    for vid in req.candidate_video_ids:
        feats, src = _get_features(req.user_id, vid)
        feature_rows.append(feats)
        sources_seen.add(src)
    feature_latency = (time.perf_counter() - ft0) * 1000

    feature_source = (
        "redis" if sources_seen == {"redis"}
        else "demo" if sources_seen == {"demo"}
        else "mixed"
    )

    df     = pd.DataFrame(feature_rows)[FEATURE_COLS].fillna(0)
    scores = _model.predict_proba(df)[:, 1].tolist()
    shadow = (_shadow_model.predict_proba(df)[:, 1].tolist()
              if _shadow_model and req.return_shadow else None)

    ranked = sorted(
        zip(req.candidate_video_ids, scores,
            shadow or [None] * len(scores)),
        key=lambda x: x[1], reverse=True,
    )

    latency_ms = (time.perf_counter() - t0) * 1000
    _request_log.append({
        "user_id":        req.user_id,
        "latency_ms":     round(latency_ms, 2),
        "n_candidates":   len(req.candidate_video_ids),
        "top_score":      round(ranked[0][1], 4) if ranked else 0,
        "feature_source": feature_source,
    })
    if len(_request_log) > 1000:
        _request_log.pop(0)

    return RankResponse(
        user_id=req.user_id,
        ranked_videos=[
            VideoScore(video_id=vid, score=round(s, 4),
                       shadow_score=round(ss, 4) if ss is not None else None)
            for vid, s, ss in ranked
        ],
        latency_ms=round(latency_ms, 2),
        feature_latency_ms=round(feature_latency, 2),
        feature_source=feature_source,
    )


# ── /health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    redis_ok = False
    if _redis_client is not None:
        try:
            _redis_client.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
    return {
        "status":       "ok" if (redis_ok and _model) else "degraded",
        "redis":        redis_ok,
        "model":        _model is not None,
        "shadow_model": _shadow_model is not None,
        "rank_ready":   _model is not None,  # /rank still works without redis
    }


# ── /metrics/latency ──────────────────────────────────────────────────────────
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


# ── /metrics/skew ─────────────────────────────────────────────────────────────
@app.get("/metrics/skew")
async def skew_metrics():
    live = os.path.join(BASE_DIR, "data", "skew_metrics.json")
    demo = os.path.join(BASE_DIR, "data", "skew_metrics.demo.json")
    for path in (live, demo):
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return {"message": "No skew data available. Run python run_pipeline.py."}


# ── /metrics/model ────────────────────────────────────────────────────────────
@app.get("/metrics/model")
async def model_metrics():
    live = os.path.join(BASE_DIR, "models", "metrics.json")
    demo = os.path.join(BASE_DIR, "models", "metrics.demo.json")
    for path in (live, demo):
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return {"message": "No model metrics available. Run python run_pipeline.py."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("inference_api:app", host="0.0.0.0", port=8000, reload=True)
