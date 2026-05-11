"""
event_generator.py
------------------
Generates synthetic consumer-scale user events with REAL signal.
Events span a 30-day window so rolling features (7d, 24h, 30d) work.
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta

import numpy as np
from kafka import KafkaProducer
from dotenv import load_dotenv
import os

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC_EVENTS", "user-events")

random.seed(42)
np.random.seed(42)

# Smaller pools = more events per user = denser feature windows
N_USERS    = 200
N_VIDEOS   = 800
N_CREATORS = 50
CATEGORIES = ["sports", "music", "gaming", "tech", "news",
              "cooking", "travel", "comedy", "education", "fitness"]
EVENT_TYPES = ["view", "click", "like", "skip", "search", "impression"]
DEVICES     = ["mobile", "desktop", "tablet", "tv"]
COUNTRIES   = ["US", "IN", "BR", "DE", "GB", "JP", "CA", "AU", "MX", "FR"]
AGE_GROUPS  = ["18-24", "25-34", "35-44", "45-54", "55+"]


def make_user_pool(n: int) -> list[dict]:
    return [
        {
            "user_id":      f"U{i:04d}",
            "age_group":    random.choice(AGE_GROUPS),
            "country":      random.choice(COUNTRIES),
            "device_type":  random.choice(DEVICES),
            "engagement":   random.betavariate(2, 4),
            "fav_category": random.choice(CATEGORIES),
            "fav_creators": random.sample(
                [f"C{j:03d}" for j in range(N_CREATORS)], k=8
            ),
        }
        for i in range(n)
    ]


def make_video_pool(n: int) -> list[dict]:
    return [
        {
            "video_id":     f"V{i:05d}",
            "category":     random.choice(CATEGORIES),
            "creator_id":   f"C{random.randint(0, N_CREATORS - 1):03d}",
            "duration_sec": random.randint(30, 3600),
            "quality":      random.betavariate(2, 3),
        }
        for i in range(n)
    ]


USERS  = make_user_pool(N_USERS)
VIDEOS = make_video_pool(N_VIDEOS)


def click_probability(user: dict, video: dict) -> float:
    p = 0.05
    p += user["engagement"] * 0.20
    p += video["quality"]   * 0.18
    if video["category"]   == user["fav_category"]:   p += 0.25
    if video["creator_id"] in user["fav_creators"]:   p += 0.15
    p += random.uniform(-0.02, 0.02)
    return max(0.001, min(0.95, p))


def generate_event(event_time: datetime, inject_anomaly: bool = False) -> dict:
    """Generate a single event at the given event_time."""
    user  = random.choice(USERS)
    video = random.choice(VIDEOS)

    delay_seconds = np.random.exponential(scale=30)
    if inject_anomaly and random.random() < 0.15:
        delay_seconds = random.uniform(300, 600)
    processing_time = event_time + timedelta(seconds=delay_seconds)

    p_click = click_probability(user, video)
    clicked = random.random() < p_click
    liked   = clicked and random.random() < (0.3 + video["quality"] * 0.3)
    watch_time = (random.uniform(0.3, 1.0) * video["duration_sec"]
                  if clicked else random.uniform(0, 8))

    event = {
        "event_id":        str(uuid.uuid4()),
        "user_id":         user["user_id"],
        "video_id":        video["video_id"],
        "category":        video["category"],
        "creator_id":      video["creator_id"],
        "event_type":      random.choice(EVENT_TYPES),
        "event_time":      event_time.isoformat(),
        "processing_time": processing_time.isoformat(),
        "delay_seconds":   round(delay_seconds, 2),
        "watch_time":      round(watch_time, 2),
        "clicked":         int(clicked),
        "liked":           int(liked),
        "device_type":     user["device_type"],
        "country":         user["country"],
    }
    if inject_anomaly and random.random() < 0.05:
        event["_duplicate"] = True
    if inject_anomaly and random.random() < 0.03:
        event.pop("watch_time", None)
    return event


def run_producer(n_events: int = 10_000, events_per_second: float = 50.0,
                 inject_anomalies: bool = True) -> None:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all", retries=3,
    )
    sleep_ms = 1.0 / events_per_second
    for i in range(n_events):
        event = generate_event(datetime.utcnow(),
                                inject_anomaly=inject_anomalies)
        producer.send(KAFKA_TOPIC, key=event["user_id"], value=event)
        if (i + 1) % 500 == 0:
            print(f"  Published {i + 1:,} / {n_events:,}")
        time.sleep(sleep_ms)
    producer.flush()
    producer.close()


def generate_batch(n: int = 50_000) -> list[dict]:
    """
    Generate events spread over a 30-day window so rolling features work.
    """
    now    = datetime.utcnow()
    start  = now - timedelta(days=30)
    span   = (now - start).total_seconds()

    # Generate uniformly spread timestamps over 30 days, then sort
    timestamps = sorted([
        start + timedelta(seconds=random.uniform(0, span))
        for _ in range(n)
    ])

    return [generate_event(ts, inject_anomaly=True) for ts in timestamps]


if __name__ == "__main__":
    run_producer(n_events=5_000, events_per_second=100)
