from functools import lru_cache

from django.conf import settings


FEATURE_NAMES = ("s1", "s2", "s3", "s4", "s5", "s6", "s7")


@lru_cache(maxsize=1)
def _load_policy_bundle():
    path = settings.AI_POLICY_MODEL_PATH
    if not path.exists():
        return None
    try:
        import joblib

        return joblib.load(path)
    except (ImportError, OSError, ValueError):
        return None


def choose_clarification_policy(configuration, signals, validation):
    configuration = configuration.upper()
    if configuration == "C1":
        return {
            "ask": bool(signals["s7"]),
            "probability": None,
            "fallback": None,
        }
    if configuration == "C2":
        return {
            "ask": bool(signals["s7"]),
            "probability": None,
            "fallback": None,
        }
    if configuration == "C3":
        return {
            "ask": signals["s4"] > 0 or signals["s3"] >= 2,
            "probability": None,
            "fallback": None,
        }
    if configuration == "C4":
        return {
            "ask": signals["s1"] < settings.AI_CONFIDENCE_THRESHOLD,
            "probability": signals["s1"],
            "fallback": None,
        }

    bundle = _load_policy_bundle()
    if not bundle:
        return {
            "ask": signals["s4"] > 0 or signals["s3"] >= 2,
            "probability": None,
            "fallback": "C5 model is not trained; C3 rules are being used.",
        }

    classifier = bundle["classifier"]
    threshold = float(bundle["threshold"])
    features = [[signals[name] for name in FEATURE_NAMES]]
    probability = float(classifier.predict_proba(features)[0][1])
    return {"ask": probability >= threshold, "probability": probability, "fallback": None}
