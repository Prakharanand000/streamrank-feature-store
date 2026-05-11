"""
kafka_consumer.py
-----------------
Consumes user events from Kafka, computes rolling online features,
and writes them to Redis in real time.
"""

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

import redis
from kafka import KafkaConsumer
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC_EVENTS", "user-events")
REDIS_HOST      = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT      = int(os.getenv("REDIS_PORT", 6379))

# In-memory rolling windows (simplified - production would use Flink/Spark)
user_events:  dict[str, list] = defaultdict(list)
video_events: dict[str, list] = defaultdict(list)


def update_user_features(r: redis.Redis, user_id: str,
                          events: list[dict]) -> None:
    now     = datetime.utcnow()
    window  = [e for e in events
               if datetime.fromisoformat(e["event_time"])
               >= now - timedelta(days=7)]

    if not window:
        return

    click_rate    = sum(e.get("clicked", 0) for e in window) / len(window)
    avg_watch     = sum(e.get("watch_time", 0) for e in window) / len(window)

    # Category affinity
    cats = [e.get("category", "") for e in window]
    top_cat_count = max(cats.count(c) for c in set(cats)) if cats else 0
    affinity = top_cat_count / max(len(window), 1)

    payload = json.dumps({
        "click_rate_7d":        round(click_rate, 4),
        "avg_watch_time_7d":    round(avg_watch, 2),
        "category_affinity_30d": round(affinity, 4),
        "_updated_at":          now.isoformat(),
    })
    r.setex(f"user:{user_id}:features", 3600, payload)


def update_video_features(r: redis.Redis, video_id: str,
                           events: list[dict]) -> None:
    now    = datetime.utcnow()
    last24 = [e for e in events
              if datetime.fromisoformat(e["event_time"])
              >= now - timedelta(hours=24)]

    if not last24:
        return

    ctr        = sum(e.get("clicked", 0) for e in last24) / len(last24)
    engagement = (
        sum(e.get("clicked", 0) + e.get("liked", 0) for e in last24)
        / len(last24)
    )

    oldest = min(datetime.fromisoformat(e["event_time"]) for e in events)
    freshness = (now - oldest).total_seconds() / 3600

    payload = json.dumps({
        "ctr_24h":               round(ctr, 4),
        "creator_engagement_7d": round(engagement, 4),
        "freshness_hours":       round(freshness, 2),
        "_updated_at":           now.isoformat(),
    })
    r.setex(f"video:{video_id}:features", 3600, payload)


def run_consumer() -> None:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="streamrank-feature-consumer",
    )

    print(f"Consuming from '{KAFKA_TOPIC}'...")
    processed = 0

    for msg in consumer:
        event   = msg.value
        uid     = event.get("user_id")
        vid     = event.get("video_id")

        if not uid or not vid:
            continue

        # Skip duplicates (simple dedup by event_id)
        eid = event.get("event_id", "")
        if eid and r.get(f"seen:{eid}"):
            continue
        if eid:
            r.setex(f"seen:{eid}", 300, "1")

        user_events[uid].append(event)
        video_events[vid].append(event)

        # Trim windows to last 30 days
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        user_events[uid]  = [e for e in user_events[uid]
                              if e.get("event_time", "") >= cutoff]
        video_events[vid] = [e for e in video_events[vid]
                              if e.get("event_time", "") >= cutoff]

        update_user_features(r, uid, user_events[uid])
        update_video_features(r, vid, video_events[vid])

        processed += 1
        if processed % 100 == 0:
            print(f"Processed {processed:,} events")


if __name__ == "__main__":
    run_consumer()
