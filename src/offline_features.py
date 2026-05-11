"""
offline_features.py
-------------------
Builds the offline feature store using point-in-time correct joins.
Prevents data leakage by only using data available before each prediction time.

Features computed:
  - user_click_rate_7d
  - user_avg_watch_time_7d
  - video_ctr_24h
  - creator_engagement_7d
  - user_category_affinity_30d
  - video_freshness_hours
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

OFFLINE_STORE = os.getenv("OFFLINE_STORE_PATH", "data/offline_features.parquet")


def build_offline_features(events: list[dict]) -> pd.DataFrame:
    """
    Build point-in-time correct feature rows from raw events.
    For each event, features are computed using ONLY data before event_time.
    This is the core anti-leakage guarantee of the offline store.
    """
    df = pd.DataFrame(events)
    df["event_time"]      = pd.to_datetime(df["event_time"])
    df["processing_time"] = pd.to_datetime(df["processing_time"])
    df["watch_time"]      = df["watch_time"].fillna(0).astype(float)
    df = df.drop_duplicates(subset=["event_id"])
    df = df.sort_values("event_time").reset_index(drop=True)

    print(f"Building offline features for {len(df):,} events...")
    rows = []

    # Sample a subset for training rows (every 10th event per user)
    training_rows = df.groupby("user_id").apply(
        lambda g: g.iloc[::10]
    ).reset_index(drop=True)

    for _, row in training_rows.iterrows():
        t          = row["event_time"]
        uid        = row["user_id"]
        vid        = row["video_id"]
        creator_id = row["creator_id"]
        category   = row["category"]

        # Only use history BEFORE this event (point-in-time correct)
        hist      = df[df["event_time"] < t]
        user_hist = hist[hist["user_id"] == uid]
        vid_hist  = hist[hist["video_id"] == vid]
        cr_hist   = hist[hist["creator_id"] == creator_id]

        # ── user features (7-day window) ──────────────────────────────────
        user_7d = user_hist[user_hist["event_time"] >= t - timedelta(days=7)]
        user_click_rate_7d  = (user_7d["clicked"].mean()
                                if len(user_7d) > 0 else 0.0)
        user_avg_watch_7d   = (user_7d["watch_time"].mean()
                                if len(user_7d) > 0 else 0.0)

        # ── video features (24h window) ───────────────────────────────────
        vid_24h     = vid_hist[vid_hist["event_time"] >= t - timedelta(hours=24)]
        video_ctr_24h = (vid_24h["clicked"].mean()
                          if len(vid_24h) > 0 else 0.0)

        # ── creator features (7-day window) ───────────────────────────────
        cr_7d = cr_hist[cr_hist["event_time"] >= t - timedelta(days=7)]
        creator_engagement_7d = (
            (cr_7d["clicked"].sum() + cr_7d["liked"].sum()) / max(len(cr_7d), 1)
        )

        # ── user-category affinity (30-day window) ─────────────────────────
        user_30d = user_hist[user_hist["event_time"] >= t - timedelta(days=30)]
        cat_views = user_30d[user_30d["category"] == category]
        user_category_affinity_30d = (
            len(cat_views) / max(len(user_30d), 1)
        )

        # ── video freshness ───────────────────────────────────────────────
        upload_str = df[df["video_id"] == vid]["event_time"].min()
        video_freshness_hours = (
            (t - upload_str).total_seconds() / 3600
            if pd.notna(upload_str) else 168.0
        )

        rows.append({
            "user_id":                    uid,
            "video_id":                   vid,
            "event_time":                 t,
            "label":                      int(row["clicked"]),
            "user_click_rate_7d":         round(user_click_rate_7d, 4),
            "user_avg_watch_time_7d":     round(user_avg_watch_7d, 2),
            "video_ctr_24h":              round(video_ctr_24h, 4),
            "creator_engagement_7d":      round(creator_engagement_7d, 4),
            "user_category_affinity_30d": round(user_category_affinity_30d, 4),
            "video_freshness_hours":      round(video_freshness_hours, 2),
        })

    features_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OFFLINE_STORE) or "data", exist_ok=True)
    features_df.to_parquet(OFFLINE_STORE, index=False)
    print(f"Saved {len(features_df):,} feature rows to {OFFLINE_STORE}")
    return features_df


def load_offline_features() -> pd.DataFrame:
    return pd.read_parquet(OFFLINE_STORE)


FEATURE_COLS = [
    "user_click_rate_7d",
    "user_avg_watch_time_7d",
    "video_ctr_24h",
    "creator_engagement_7d",
    "user_category_affinity_30d",
    "video_freshness_hours",
]
