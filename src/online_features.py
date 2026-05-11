"""
online_features.py
------------------
Online feature store backed by Redis.
Provides low-latency (<10ms) feature lookup for real-time inference.
Keeps features in sync with the offline store to detect training-serving skew.
"""

import json
import os
import time
from datetime import datetime

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
TTL_SECONDS = 3600  # features expire after 1 hour


def get_redis() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                       decode_responses=True)


# ── write helpers ─────────────────────────────────────────────────────────────

def write_user_features(r: redis.Redis, user_id: str,
                        features: dict) -> None:
    key = f"user:{user_id}:features"
    payload = {**features, "_updated_at": datetime.utcnow().isoformat()}
    r.setex(key, TTL_SECONDS, json.dumps(payload))


def write_video_features(r: redis.Redis, video_id: str,
                         features: dict) -> None:
    key = f"video:{video_id}:features"
    payload = {**features, "_updated_at": datetime.utcnow().isoformat()}
    r.setex(key, TTL_SECONDS, json.dumps(payload))


def write_creator_features(r: redis.Redis, creator_id: str,
                            features: dict) -> None:
    key = f"creator:{creator_id}:features"
    payload = {**features, "_updated_at": datetime.utcnow().isoformat()}
    r.setex(key, TTL_SECONDS, json.dumps(payload))


# ── read helpers ──────────────────────────────────────────────────────────────

def get_user_features(r: redis.Redis, user_id: str) -> dict:
    raw = r.get(f"user:{user_id}:features")
    return json.loads(raw) if raw else {}


def get_video_features(r: redis.Redis, video_id: str) -> dict:
    raw = r.get(f"video:{video_id}:features")
    return json.loads(raw) if raw else {}


def get_online_feature_vector(r: redis.Redis,
                               user_id: str,
                               video_id: str) -> dict:
    """
    Fetch full feature vector for a (user, video) pair.
    Used at inference time. Target latency: <10ms.
    """
    t0 = time.perf_counter()

    user_feats  = get_user_features(r, user_id)
    video_feats = get_video_features(r, video_id)

    latency_ms = (time.perf_counter() - t0) * 1000

    return {
        "user_click_rate_7d":         user_feats.get("click_rate_7d", 0.0),
        "user_avg_watch_time_7d":     user_feats.get("avg_watch_time_7d", 0.0),
        "video_ctr_24h":              video_feats.get("ctr_24h", 0.0),
        "creator_engagement_7d":      video_feats.get("creator_engagement_7d", 0.0),
        "user_category_affinity_30d": user_feats.get("category_affinity_30d", 0.0),
        "video_freshness_hours":      video_feats.get("freshness_hours", 168.0),
        "_feature_latency_ms":        round(latency_ms, 3),
    }


# ── bulk population from offline store ───────────────────────────────────────

def populate_from_offline(offline_df, r: redis.Redis | None = None) -> int:
    """
    Seed the online store from the offline feature parquet.
    In production this would be run by a feature pipeline job.
    Returns number of keys written.
    """
    if r is None:
        r = get_redis()

    written = 0
    for _, row in offline_df.iterrows():
        uid = row["user_id"]
        vid = row["video_id"]

        write_user_features(r, uid, {
            "click_rate_7d":       float(row["user_click_rate_7d"]),
            "avg_watch_time_7d":   float(row["user_avg_watch_time_7d"]),
            "category_affinity_30d": float(row["user_category_affinity_30d"]),
        })
        write_video_features(r, vid, {
            "ctr_24h":               float(row["video_ctr_24h"]),
            "creator_engagement_7d": float(row["creator_engagement_7d"]),
            "freshness_hours":       float(row["video_freshness_hours"]),
        })
        written += 2

    print(f"Populated online store: {written:,} keys written to Redis")
    return written


# ── skew injection (for demo purposes) ────────────────────────────────────────

def inject_skew(r: redis.Redis, user_ids: list[str],
                skew_factor: float = 0.3) -> None:
    """
    Deliberately perturb online features to simulate training-serving skew.
    Used for demo/monitoring testing.
    """
    import random
    for uid in random.sample(user_ids, k=min(50, len(user_ids))):
        feats = get_user_features(r, uid)
        if feats:
            feats["click_rate_7d"] = max(
                0.0,
                feats.get("click_rate_7d", 0.1) * (1 + random.uniform(-skew_factor, skew_factor))
            )
            write_user_features(r, uid, feats)
    print(f"Injected skew into {min(50, len(user_ids))} user feature records")
