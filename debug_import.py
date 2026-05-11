import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

print("Testing all imports...")

try:
    from train_model import train, SHADOW_PATH, MODEL_PATH
    print("  OK train_model")
except Exception as e:
    print(f"  FAIL train_model: {e}")
    import traceback; traceback.print_exc()

try:
    from skew_monitor import compute_skew, get_event_delay_stats
    print("  OK skew_monitor")
except Exception as e:
    print(f"  FAIL skew_monitor: {e}")
    import traceback; traceback.print_exc()

try:
    from online_features import populate_from_offline, get_redis, inject_skew
    print("  OK online_features")
except Exception as e:
    print(f"  FAIL online_features: {e}")
    import traceback; traceback.print_exc()
