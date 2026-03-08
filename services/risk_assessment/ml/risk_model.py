"""Service-side ML wrapper for risk scoring.

Loads the XGBoost model from ml-pipeline/saved_models/ at first call
and exposes a simple predict() interface.

The service uses this when:  os.getenv("RISK_ML_ENABLED", "false") == "true"

If the model file is missing or inference fails, returns None so
the caller can fall through to the heuristic compute_risk_score().
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).parents[3] / "ml-pipeline" / "saved_models"

# Lazy-loaded module-level cache
_model       = None
_features:   list[str] | None = None
_label_names: list[str] | None = None
_explainer   = None


def _ensure_loaded() -> bool:
    global _model, _features, _label_names, _explainer
    if _model is not None:
        return True

    model_path = _MODEL_DIR / "risk_model.joblib"
    if not model_path.exists():
        logger.warning(
            "Risk ML model not found at %s — falling back to heuristic", model_path,
        )
        return False

    try:
        _model       = joblib.load(model_path)
        _features    = joblib.load(_MODEL_DIR / "risk_features.joblib")
        _label_names = joblib.load(_MODEL_DIR / "risk_label_names.joblib")
        try:
            _explainer = joblib.load(_MODEL_DIR / "risk_explainer.joblib")
        except Exception:
            _explainer = None
        logger.info("Risk ML model loaded (XGBoost) from %s", model_path)
        return True
    except Exception as exc:
        logger.error("Failed to load risk model: %s", exc)
        return False


def is_available() -> bool:
    """Return True iff the model artefacts exist and loaded successfully."""
    return _ensure_loaded()


def predict(inp_dict: dict) -> dict | None:
    """Run XGBoost inference.

    Parameters
    ----------
    inp_dict : dict
        Must contain the 18 feature keys matching the training schema.
        Missing keys default to 0.0.

    Returns
    -------
    dict | None
        {
          "risk_score":               int (0–1000),
          "risk_category":            str ("LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH"),
          "confidence_level":         float (0–1),
          "probabilities":            dict {category: probability},
          "shap_feature_importances": dict {feature: shap_value},
          "model_version":            str,
        }
        Returns None if model unavailable or inference fails.
    """
    if not _ensure_loaded():
        return None

    try:
        feature_vector = np.array(
            [float(inp_dict.get(f, 0.0)) for f in _features],
            dtype=np.float32,
        ).reshape(1, -1)

        proba    = _model.predict_proba(feature_vector)[0]
        cat_idx  = int(np.argmax(proba))
        category = _label_names[cat_idx]

        # Map probabilities to 0–1000 score using class-midpoint weighting
        # LOW=0–249, MEDIUM=250–499, HIGH=500–749, VERY_HIGH=750–1000
        midpoints = [125, 375, 625, 875]
        score = int(np.dot(proba, midpoints))

        # SHAP per-feature attribution for the predicted class
        shap_dict: dict[str, float] = {}
        if _explainer is not None:
            try:
                shap_vals = _explainer.shap_values(feature_vector)
                # shap_vals is a list of arrays (one per class) for multi-class XGBoost
                if isinstance(shap_vals, list) and len(shap_vals) == len(_label_names):
                    class_shap = shap_vals[cat_idx][0]
                else:
                    class_shap = np.asarray(shap_vals).flatten()[:len(_features)]
                shap_dict = {
                    feat: round(float(val), 5)
                    for feat, val in zip(_features, class_shap)
                }
            except Exception as shap_err:
                logger.debug("SHAP computation skipped: %s", shap_err)

        return {
            "risk_score":               score,
            "risk_category":            category,
            "confidence_level":         float(round(float(max(proba)), 4)),
            "probabilities":            {n: float(round(p, 4)) for n, p in zip(_label_names, proba)},
            "shap_feature_importances": shap_dict,
            "model_version":            "xgboost-v1",
        }

    except Exception as exc:
        logger.error("Risk ML prediction failed: %s", exc)
        return None
