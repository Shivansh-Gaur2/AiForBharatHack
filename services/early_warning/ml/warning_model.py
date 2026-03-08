"""Service-side ML wrapper for early-warning anomaly detection + severity.

Two-stage inference:
  1. IsolationForest: computes an anomaly score (0–100, higher = more anomalous)
  2. LightGBM:        maps features → severity (OK / WARNING / CRITICAL)

The service uses this when: os.getenv("EARLY_WARNING_ML_ENABLED", "false") == "true"

Returns None on model unavailability → caller falls back to heuristic build_alert().
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).parents[3] / "ml-pipeline" / "saved_models"

_iso_forest  = None
_lgbm_clf    = None
_features:   list[str] | None = None

# Maps integer class → AlertSeverity-compatible string
SEVERITY_NAMES = ["INFO", "WARNING", "CRITICAL"]   # 0=OK→INFO, 1=WARNING, 2=CRITICAL


def _ensure_loaded() -> bool:
    global _iso_forest, _lgbm_clf, _features
    if _iso_forest is not None:
        return True

    iso_path  = _MODEL_DIR / "ew_isolation_forest.joblib"
    feat_path = _MODEL_DIR / "ew_features.joblib"

    if not iso_path.exists():
        logger.warning("Early warning ML model not found at %s — falling back to heuristic", iso_path)
        return False

    try:
        _iso_forest = joblib.load(iso_path)
        _features   = joblib.load(feat_path)

        lgbm_path = _MODEL_DIR / "ew_lgbm_classifier.joblib"
        if lgbm_path.exists():
            _lgbm_clf = joblib.load(lgbm_path)

        logger.info("Early warning ML models loaded from %s", _MODEL_DIR)
        return True
    except Exception as exc:
        logger.error("Failed to load early warning models: %s", exc)
        return False


def is_available() -> bool:
    return _ensure_loaded()


def predict(features_dict: dict) -> dict | None:
    """Predict alert severity from borrower stress features.

    Parameters
    ----------
    features_dict : dict
        Must contain the 12 feature keys from training.  Missing keys → 0.0.

    Returns
    -------
    dict | None
        {
          "anomaly_score":   float  (0–100; higher = more anomalous),
          "severity":        str    ("INFO" | "WARNING" | "CRITICAL"),
          "severity_index":  int    (0 / 1 / 2),
          "probability":     float  (classifier confidence),
          "model_version":   str,
        }
    """
    if not _ensure_loaded():
        return None

    try:
        fv = np.array(
            [float(features_dict.get(f, 0.0)) for f in _features],
            dtype=np.float32,
        ).reshape(1, -1)

        # ── Stage 1: anomaly score ────────────────────────────────────────────
        # score_samples() returns more-negative for anomalies; typical range [-0.5, 0.1]
        raw_score    = float(_iso_forest.score_samples(fv)[0])
        # Normalise to [0, 100] where 0 = normal, 100 = very anomalous
        anomaly_score = float(np.clip((raw_score + 0.5) * -200.0, 0.0, 100.0))

        # ── Stage 2: severity classification ─────────────────────────────────
        if _lgbm_clf is not None:
            proba        = _lgbm_clf.predict_proba(fv)[0]
            sev_idx      = int(np.argmax(proba))
            severity     = SEVERITY_NAMES[sev_idx]
            probability  = float(round(float(max(proba)), 4))
        else:
            # Threshold fallback from anomaly score alone
            if anomaly_score > 70:
                sev_idx, severity, probability = 2, "CRITICAL", 0.70
            elif anomaly_score > 35:
                sev_idx, severity, probability = 1, "WARNING",  0.65
            else:
                sev_idx, severity, probability = 0, "INFO",     0.80

        return {
            "anomaly_score":  round(anomaly_score, 2),
            "severity":       severity,
            "severity_index": sev_idx,
            "probability":    probability,
            "model_version":  "isolation-forest+lgbm-v1",
        }

    except Exception as exc:
        logger.error("Early warning ML prediction failed: %s", exc)
        return None
