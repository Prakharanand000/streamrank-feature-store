"""
run_pipeline.py - StreamRank full pipeline (force-flushed, xgboost-first)
"""

import sys
import os
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

print("[1] Importing xgboost FIRST...", flush=True)
import xgboost as xgb
print(f"    xgboost {xgb.__version__} loaded", flush=True)

print("[2] Importing other heavy libs...", flush=True)
import pandas as pd
import numpy as np
import sklearn
print(f"    pandas {pd.__version__} | numpy {np.__version__} | sklearn {sklearn.__version__}", flush=True)

import traceback

print("[3] Setting up paths...", flush=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_PATH)
os.chdir(BASE_DIR)
print(f"    BASE_DIR: {BASE_DIR}", flush=True)
print(f"    SRC_PATH: {SRC_PATH}", flush=True)

os.makedirs("data",   exist_ok=True)
os.makedirs("models", exist_ok=True)
print("    Directories ready: data/ models/", flush=True)

print("\n[4] Importing project modules...", flush=True)
for mod_name, what in [
    ("event_generator",  "generate_batch"),
    ("offline_features", "build_offline_features"),
    ("train_model",      "train, SHADOW_PATH, MODEL_PATH"),
    ("skew_monitor",     "compute_skew, get_event_delay_stats"),
    ("online_features",  "populate_from_offline, get_redis, inject_skew"),
]:
    print(f"    -> {mod_name}...", flush=True)
    try:
        exec(f"from {mod_name} import {what}", globals())
        print("       OK", flush=True)
    except BaseException as e:
        print(f"       FAIL: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(); sys.exit(1)

print("\nAll imports succeeded.\n", flush=True)

# ── Step 1 ────────────────────────────────────────────────────────────────────
print("=" * 60, flush=True)
print("Step 1/5  Generate 50,000 synthetic events (spread over 30 days)", flush=True)
print("=" * 60, flush=True)
events = generate_batch(n=50_000)
print(f"Generated {len(events):,} events", flush=True)
delay_stats = get_event_delay_stats(events)
print(f"Avg delay: {delay_stats.get('mean_delay_sec',0):.1f}s  "
      f"P95: {delay_stats.get('p95_delay_sec',0):.1f}s  "
      f"Max: {delay_stats.get('max_delay_sec',0):.1f}s", flush=True)

# ── Step 2 ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60, flush=True)
print("Step 2/5  Build offline feature store (point-in-time joins)", flush=True)
print("          ~3-5 min - computing features per row...", flush=True)
print("=" * 60, flush=True)
try:
    offline_df = build_offline_features(events)
    print(f"Feature rows : {len(offline_df):,}", flush=True)
    print(f"Click rate   : {offline_df['label'].mean():.2%}", flush=True)
except BaseException as e:
    print(f"FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc(); sys.exit(1)

# ── Step 3 ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60, flush=True)
print("Step 3/5  Train XGBoost production + shadow models", flush=True)
print("=" * 60, flush=True)
try:
    m_prod   = train(offline_df, shadow=False)
    m_shadow = train(offline_df, model_path=SHADOW_PATH, shadow=True)
    print(f"Production : AUC={m_prod['auc']}  NDCG@10={m_prod['ndcg_at_10']}", flush=True)
    print(f"Shadow     : AUC={m_shadow['auc']}  NDCG@10={m_shadow['ndcg_at_10']}", flush=True)
except BaseException as e:
    print(f"FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc(); sys.exit(1)

# ── Step 4 ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60, flush=True)
print("Step 4/5  Populate Redis online store", flush=True)
print("=" * 60, flush=True)
redis_ok = False
try:
    r = get_redis()
    r.ping()
    print("Redis connected OK", flush=True)
    populate_from_offline(offline_df, r)
    user_ids = offline_df["user_id"].unique().tolist()
    inject_skew(r, user_ids, skew_factor=0.35)
    print("Skew injected for demo monitoring", flush=True)
    redis_ok = True
except BaseException as e:
    print(f"Redis error: {e}", flush=True)
    print("Skipping Redis steps - run 'docker-compose up -d' first", flush=True)

# ── Step 5 ────────────────────────────────────────────────────────────────────
if redis_ok:
    print("\n" + "=" * 60, flush=True)
    print("Step 5/5  Compute training-serving skew", flush=True)
    print("=" * 60, flush=True)
    try:
        r = get_redis()
        skew = compute_skew(offline_df, r)
        print(f"Overall Health : {skew['overall_health']}", flush=True)
        print(f"Flagged        : {skew['n_flagged_features']} / "
              f"{len(skew['features'])} features", flush=True)
        print(flush=True)
        for feat, vals in skew["features"].items():
            flag = "FLAGGED" if vals["flagged"] else "OK     "
            print(f"  [{flag}]  {feat:<35}  "
                  f"skew={vals['skew_pct']:.1%}  PSI={vals['psi']:.3f}", flush=True)
    except BaseException as e:
        print(f"Skew compute error: {e}", flush=True)

# ── Done ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60, flush=True)
print("Pipeline complete!", flush=True)
print("=" * 60, flush=True)
print()
print("To launch the dashboard:", flush=True)
print("  Terminal 1: cd src && uvicorn inference_api:app --reload --port 8000", flush=True)
print("  Terminal 2: cd frontend && npm install && npm run dev", flush=True)
