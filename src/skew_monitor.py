"""
skew_monitor.py
---------------
Computes training-serving skew by comparing offline feature distributions
against online (Redis) feature values.

Metrics:
  - Per-feature skew % (mean absolute deviation)
  - PSI (Population Stability Index) for drift detection
  - Missing feature rate
  - Stale feature rate
  - Event delay distribution stats
"""

import json
import os
import numpy as np
import pandas as pd
import redis as redis_lib
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SKEW_THRESHOLD = float(os.getenv("SKEW_THRESHOLD", 0.20))
METRICS_OUT    = "data/skew_metrics.json"

FEATURE_MAP = {
    "user_click_rate_7d":         ("user", "click_rate_7d"),
    "user_avg_watch_time_7d":     ("user", "avg_watch_time_7d"),
    "video_ctr_24h":              ("video", "ctr_24h"),
    "creator_engagement_7d":      ("video", "creator_engagement_7d"),
    "user_category_affinity_30d": ("user", "category_affinity_30d"),
    "video_freshness_hours":      ("video", "freshness_hours"),
}


def compute_psi(expected: np.ndarray, actual: np.ndarray,
                buckets: int = 10) -> float:
    """Population Stability Index. PSI > 0.2 signals significant drift."""
    expected = np.clip(expected, 1e-6, None)
    actual   = np.clip(actual,   1e-6, None)

    breakpoints = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    breakpoints[0]  = -np.inf
    breakpoints[-1] = np.inf

    e_pct = np.histogram(expected, bins=breakpoints)[0] / len(expected)
    a_pct = np.histogram(actual,   bins=breakpoints)[0] / len(actual)

    e_pct = np.clip(e_pct, 1e-6, None)
    a_pct = np.clip(a_pct, 1e-6, None)

    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def compute_skew(offline_df: pd.DataFrame,
                 r: redis_lib.Redis,
                 sample_size: int = 200) -> dict:
    """
    Sample rows from offline store, fetch matching online features,
    and compute per-feature skew statistics.
    """
    sample = offline_df.sample(n=min(sample_size, len(offline_df)),
                                random_state=42)

    skew_results = {}
    missing_count = 0
    stale_count   = 0
    total         = len(sample)

    offline_vals = {col: [] for col in FEATURE_MAP}
    online_vals  = {col: [] for col in FEATURE_MAP}

    for _, row in sample.iterrows():
        uid = row["user_id"]
        vid = row["video_id"]

        user_raw  = r.get(f"user:{uid}:features")
        video_raw = r.get(f"video:{vid}:features")

        user_online  = json.loads(user_raw)  if user_raw  else {}
        video_online = json.loads(video_raw) if video_raw else {}

        if not user_raw or not video_raw:
            missing_count += 1

        # Check staleness (>30 min old)
        for blob in [user_online, video_online]:
            updated = blob.get("_updated_at")
            if updated:
                age = (datetime.utcnow()
                       - datetime.fromisoformat(updated)).total_seconds()
                if age > 1800:
                    stale_count += 1
                    break

        for feat, (entity, redis_key) in FEATURE_MAP.items():
            off_val = float(row.get(feat, 0) or 0)
            if entity == "user":
                on_val = float(user_online.get(redis_key, 0) or 0)
            else:
                on_val = float(video_online.get(redis_key, 0) or 0)

            offline_vals[feat].append(off_val)
            online_vals[feat].append(on_val)

    for feat in FEATURE_MAP:
        off_arr = np.array(offline_vals[feat])
        on_arr  = np.array(online_vals[feat])

        denom    = np.abs(off_arr).mean()
        skew_pct = float(np.abs(off_arr - on_arr).mean() / max(denom, 1e-6))
        psi      = compute_psi(off_arr, on_arr)

        skew_results[feat] = {
            "offline_mean":   round(float(off_arr.mean()), 4),
            "online_mean":    round(float(on_arr.mean()),  4),
            "skew_pct":       round(skew_pct, 4),
            "psi":            round(psi, 4),
            "flagged":        skew_pct > SKEW_THRESHOLD or psi > 0.2,
        }

    result = {
        "computed_at":        datetime.utcnow().isoformat(),
        "sample_size":        total,
        "missing_rate":       round(missing_count / max(total, 1), 4),
        "stale_rate":         round(stale_count   / max(total, 1), 4),
        "features":           skew_results,
        "n_flagged_features": sum(1 for v in skew_results.values()
                                  if v["flagged"]),
        "overall_health":     (
            "DEGRADED" if any(v["flagged"] for v in skew_results.values())
            else "HEALTHY"
        ),
    }

    os.makedirs("data", exist_ok=True)
    with open(METRICS_OUT, "w") as f:
        json.dump(result, f, indent=2)

    return result


def get_event_delay_stats(events: list[dict]) -> dict:
    """Summarize event delay distribution (event_time vs processing_time)."""
    delays = []
    for e in events:
        try:
            et = datetime.fromisoformat(e["event_time"])
            pt = datetime.fromisoformat(e["processing_time"])
            delays.append((pt - et).total_seconds())
        except Exception:
            pass

    if not delays:
        return {}

    arr = np.array(delays)
    return {
        "mean_delay_sec":   round(float(arr.mean()), 2),
        "p50_delay_sec":    round(float(np.percentile(arr, 50)), 2),
        "p95_delay_sec":    round(float(np.percentile(arr, 95)), 2),
        "p99_delay_sec":    round(float(np.percentile(arr, 99)), 2),
        "max_delay_sec":    round(float(arr.max()), 2),
        "n_events":         len(delays),
    }
