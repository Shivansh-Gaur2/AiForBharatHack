# AWS ML Model Deployment Guide

This guide covers every step needed to move the four ML models from their local
`ml-pipeline/saved_models/` path into production on AWS.  
One section per model, plus a shared infrastructure section at the start.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Shared Infrastructure](#2-shared-infrastructure)
3. [Model 1 — Risk Scoring (XGBoost)](#3-model-1--risk-scoring-xgboost)
4. [Model 2 — Cashflow Prediction (Ridge)](#4-model-2--cashflow-prediction-ridge)
5. [Model 3 — Early Warning (IsolationForest + LightGBM)](#5-model-3--early-warning-isolationforest--lightgbm)
6. [Model 4 — Scenario Simulation (Monte Carlo)](#6-model-4--scenario-simulation-monte-carlo)
7. [Environment Variable Reference](#7-environment-variable-reference)
8. [CI/CD: Retraining & Artifact Promotion](#8-cicd-retraining--artifact-promotion)

---

## 1. Architecture Overview

```
┌──────────────┐   joblib/json    ┌──────────────────────┐
│  ML Pipeline │ ─────────────►  │  S3 Bucket           │
│  (training)  │                 │  rural-credit-models/ │
└──────────────┘                 └──────────┬───────────┘
                                            │  download on cold-start
                          ┌─────────────────┼─────────────────┐
                          │                 │                 │
                   ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
                   │  Risk       │  │  Cashflow   │  │  Early Warn │
                   │  Service    │  │  Service    │  │  + Scenario │
                   │  :8001      │  │  :8004      │  │  :8005      │
                   │  (Lambda /  │  │  (Lambda /  │  │  (Lambda /  │
                   │   ECS)      │  │   ECS)      │  │   ECS)      │
                   └─────────────┘  └─────────────┘  └─────────────┘
```

Each service already has a lazy-load `_ensure_loaded()` function.  
On AWS you modify that function to download from S3 into `/tmp` **once per
cold start** instead of reading from the local `ml-pipeline/saved_models/` path.

---

## 2. Shared Infrastructure

### 2.1 S3 Bucket Layout

Create **one bucket** shared across all services (or one per service if you
need independent IAM policies).

```
s3://rural-credit-models/
├── risk/
│   ├── v1/
│   │   ├── risk_model.joblib          (6.1 MB)
│   │   ├── risk_explainer.joblib      (25.4 MB)
│   │   ├── risk_features.joblib
│   │   └── risk_label_names.joblib
│   └── latest -> v1/                  (S3 alias via env var, not a real symlink)
├── cashflow/
│   └── v1/
│       ├── cashflow_inflow_model.joblib
│       └── cashflow_outflow_model.joblib
├── early_warning/
│   └── v1/
│       ├── ew_isolation_forest.joblib
│       ├── ew_lgbm_classifier.joblib
│       └── ew_features.joblib
└── scenario/
    └── v1/
        ├── scenario_dist_params.json
        └── scenario_seasonal.json
```

**Upload command (after training):**

```bash
aws s3 sync ml-pipeline/saved_models/ s3://rural-credit-models/ \
  --exclude "*" \
  --include "risk_model.joblib" \
  --include "risk_explainer.joblib" \
  --include "risk_features.joblib" \
  --include "risk_label_names.joblib" \
  --include "cashflow_inflow_model.joblib" \
  --include "cashflow_outflow_model.joblib" \
  --include "ew_isolation_forest.joblib" \
  --include "ew_lgbm_classifier.joblib" \
  --include "ew_features.joblib" \
  --include "scenario_dist_params.json" \
  --include "scenario_seasonal.json"
```

### 2.2 IAM Policy (attach to Lambda role / ECS task role)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadModels",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:HeadObject"],
      "Resource": "arn:aws:s3:::rural-credit-models/*"
    }
  ]
}
```

### 2.3 Shared S3 Download Helper

Add this to `services/shared/ml_utils.py`:

```python
"""Shared AWS helpers for ML model loading."""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Local cache directory – /tmp on Lambda, configurable elsewhere
_LOCAL_CACHE = Path(os.getenv("MODEL_CACHE_DIR", "/tmp/models"))


def download_model(s3_key: str) -> Path:
    """Download an S3 model artifact to the local cache if not already present.

    Parameters
    ----------
    s3_key : str
        Full S3 key, e.g. "risk/v1/risk_model.joblib"

    Returns
    -------
    Path
        Local file path of the downloaded artifact.
    """
    import boto3

    bucket = os.environ["MODEL_S3_BUCKET"]          # REQUIRED
    local_path = _LOCAL_CACHE / s3_key
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if local_path.exists():
        return local_path                            # already cached this cold-start

    logger.info("Downloading s3://%s/%s → %s", bucket, s3_key, local_path)
    s3 = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))
    s3.download_file(bucket, s3_key, str(local_path))
    return local_path
```

---

## 3. Model 1 — Risk Scoring (XGBoost)

**Service:** `services/risk_assessment/`  
**Artifacts:** `risk_model.joblib` (~6 MB), `risk_features.joblib`, `risk_label_names.joblib`, `risk_explainer.joblib` (~25 MB)  
**Algorithm:** XGBoost multi-class classifier → 4 classes (LOW / MEDIUM / HIGH / VERY_HIGH)

### 3.1 Environment Variables

| Variable | Where to set | Example value | Required? |
|---|---|---|---|
| `RISK_ML_ENABLED` | Lambda env / ECS task def | `true` | Yes — must be `true` to activate ML path |
| `MODEL_S3_BUCKET` | Lambda env / ECS task def | `rural-credit-models` | Yes |
| `RISK_MODEL_S3_PREFIX` | Lambda env / ECS task def | `risk/v1` | Yes |
| `MODEL_CACHE_DIR` | Lambda env | `/tmp/models` | No (defaults to `/tmp/models`) |
| `AWS_DEFAULT_REGION` | Lambda env / ECS task def | `ap-south-1` | No (defaults to `ap-south-1`) |

### 3.2 Updated `_ensure_loaded()` for AWS

Replace the current body of `_ensure_loaded()` in
`services/risk_assessment/ml/risk_model.py`:

```python
def _ensure_loaded() -> bool:
    global _model, _features, _label_names, _explainer
    if _model is not None:
        return True

    import os
    from services.shared.ml_utils import download_model

    prefix = os.getenv("RISK_MODEL_S3_PREFIX", "")

    # ── resolve paths (S3 download if prefix given, local fallback otherwise)
    def _path(filename: str) -> Path:
        if prefix:
            return download_model(f"{prefix}/{filename}")
        local = _MODEL_DIR / filename
        if not local.exists():
            raise FileNotFoundError(local)
        return local

    try:
        _model       = joblib.load(_path("risk_model.joblib"))
        _features    = joblib.load(_path("risk_features.joblib"))
        _label_names = joblib.load(_path("risk_label_names.joblib"))
        try:
            _explainer = joblib.load(_path("risk_explainer.joblib"))
        except Exception:
            _explainer = None  # explainer is optional
        logger.info("Risk ML model loaded (XGBoost)")
        return True
    except Exception as exc:
        logger.error("Failed to load risk model: %s", exc)
        return False
```

### 3.3 Lambda-specific Considerations

- **Memory:** Set Lambda memory to at least **1024 MB** (XGBoost + SHAP in RAM).
- **Ephemeral storage:** `/tmp` defaults to 512 MB; bump to **1024 MB** to fit
  `risk_explainer.joblib` (25 MB) plus the model (6 MB) plus overhead.
  In the Lambda console: Configuration → General → Ephemeral storage.
- **Cold start:** First invocation downloads ~32 MB from S3 (~2–4 s on Lambda).
  Subsequent invocations in the same execution context reuse the in-memory cache.
- **Timeout:** Set to at least **30 s** for cold-start S3 downloads.

### 3.4 AWS Console — Lambda Environment Variables

Navigate to:  
`Lambda → Functions → risk-assessment-fn → Configuration → Environment variables`

Add:

```
RISK_ML_ENABLED          = true
MODEL_S3_BUCKET          = rural-credit-models
RISK_MODEL_S3_PREFIX     = risk/v1
MODEL_CACHE_DIR          = /tmp/models
AWS_DEFAULT_REGION       = ap-south-1
```

### 3.5 AWS Console — ECS Task Definition (if using Fargate / ECS)

In the task definition JSON, under `containerDefinitions[].environment`:

```json
[
  { "name": "RISK_ML_ENABLED",      "value": "true" },
  { "name": "MODEL_S3_BUCKET",      "value": "rural-credit-models" },
  { "name": "RISK_MODEL_S3_PREFIX", "value": "risk/v1" },
  { "name": "AWS_DEFAULT_REGION",   "value": "ap-south-1" }
]
```

---

## 4. Model 2 — Cashflow Prediction (Ridge)

**Service:** `services/cashflow_service/`  
**Artifacts:** `cashflow_inflow_model.joblib` (~1 KB), `cashflow_outflow_model.joblib` (~1 KB)  
**Algorithm:** Ridge regression with seasonal features (month sin/cos, Kharif/Rabi/Zaid flags, irrigation flag)

### 4.1 Environment Variables

| Variable | Where to set | Example value | Required? |
|---|---|---|---|
| `CASHFLOW_ML_ENABLED` | Lambda env / ECS task def | `true` | Yes |
| `MODEL_S3_BUCKET` | Lambda env / ECS task def | `rural-credit-models` | Yes |
| `CASHFLOW_MODEL_S3_PREFIX` | Lambda env / ECS task def | `cashflow/v1` | Yes |
| `MODEL_CACHE_DIR` | Lambda env | `/tmp/models` | No |
| `AWS_DEFAULT_REGION` | Lambda env / ECS task def | `ap-south-1` | No |

### 4.2 Updated `_ensure_loaded()` for AWS

Replace the current body of `_ensure_loaded()` in
`services/cashflow_service/ml/cashflow_model.py`:

```python
def _ensure_loaded() -> bool:
    global _model_inflow, _model_outflow
    if _model_inflow is not None:
        return True

    import os
    from services.shared.ml_utils import download_model

    prefix = os.getenv("CASHFLOW_MODEL_S3_PREFIX", "")

    def _path(filename: str) -> Path:
        if prefix:
            return download_model(f"{prefix}/{filename}")
        local = _MODEL_DIR / filename
        if not local.exists():
            raise FileNotFoundError(local)
        return local

    try:
        _model_inflow  = joblib.load(_path("cashflow_inflow_model.joblib"))
        _model_outflow = joblib.load(_path("cashflow_outflow_model.joblib"))
        logger.info("Cashflow ML models loaded (Ridge-seasonal)")
        return True
    except Exception as exc:
        logger.error("Failed to load cashflow models: %s", exc)
        return False
```

### 4.3 Lambda-specific Considerations

- **Memory:** 256 MB is sufficient (Ridge models are tiny — under 1 KB each).
- **Ephemeral storage:** Default 512 MB is more than enough.
- **Cold start:** S3 download is under 1 KB — effectively instant.
- **Timeout:** 15 s is enough.

### 4.4 AWS Console — Lambda Environment Variables

```
CASHFLOW_ML_ENABLED          = true
MODEL_S3_BUCKET              = rural-credit-models
CASHFLOW_MODEL_S3_PREFIX     = cashflow/v1
MODEL_CACHE_DIR              = /tmp/models
AWS_DEFAULT_REGION           = ap-south-1
```

### 4.5 AWS Console — ECS Task Definition

```json
[
  { "name": "CASHFLOW_ML_ENABLED",      "value": "true" },
  { "name": "MODEL_S3_BUCKET",          "value": "rural-credit-models" },
  { "name": "CASHFLOW_MODEL_S3_PREFIX", "value": "cashflow/v1" },
  { "name": "AWS_DEFAULT_REGION",       "value": "ap-south-1" }
]
```

---

## 5. Model 3 — Early Warning (IsolationForest + LightGBM)

**Service:** `services/early_warning/`  
**Artifacts:** `ew_isolation_forest.joblib` (~3.4 MB), `ew_lgbm_classifier.joblib` (~1.5 MB), `ew_features.joblib`  
**Algorithm:**  
- Stage 1: `IsolationForest` → anomaly score 0–100  
- Stage 2: `LGBMClassifier` → severity (INFO / WARNING / CRITICAL)

### 5.1 Environment Variables

| Variable | Where to set | Example value | Required? |
|---|---|---|---|
| `EARLY_WARNING_ML_ENABLED` | Lambda env / ECS task def | `true` | Yes |
| `MODEL_S3_BUCKET` | Lambda env / ECS task def | `rural-credit-models` | Yes |
| `EW_MODEL_S3_PREFIX` | Lambda env / ECS task def | `early_warning/v1` | Yes |
| `MODEL_CACHE_DIR` | Lambda env | `/tmp/models` | No |
| `AWS_DEFAULT_REGION` | Lambda env / ECS task def | `ap-south-1` | No |

### 5.2 Updated `_ensure_loaded()` for AWS

Replace the current body of `_ensure_loaded()` in
`services/early_warning/ml/warning_model.py`:

```python
def _ensure_loaded() -> bool:
    global _iso_forest, _lgbm_clf, _features
    if _iso_forest is not None:
        return True

    import os
    from services.shared.ml_utils import download_model

    prefix = os.getenv("EW_MODEL_S3_PREFIX", "")

    def _path(filename: str) -> Path:
        if prefix:
            return download_model(f"{prefix}/{filename}")
        local = _MODEL_DIR / filename
        if not local.exists():
            raise FileNotFoundError(local)
        return local

    try:
        _iso_forest = joblib.load(_path("ew_isolation_forest.joblib"))
        _features   = joblib.load(_path("ew_features.joblib"))
        try:
            _lgbm_clf = joblib.load(_path("ew_lgbm_classifier.joblib"))
        except Exception:
            _lgbm_clf = None          # LightGBM is optional; IsoForest alone works
        logger.info("Early warning ML models loaded")
        return True
    except Exception as exc:
        logger.error("Failed to load early warning models: %s", exc)
        return False
```

### 5.3 Lambda-specific Considerations

- **Memory:** 512 MB recommended (IsolationForest can be memory-intensive at inference time with 3.4 MB model).
- **Ephemeral storage:** 512 MB default is fine (total download ≈ 5 MB).
- **Cold start:** S3 download ≈ 5 MB → under 1 s on Lambda.
- **LightGBM Lambda layer:** LightGBM requires system libraries (`libgomp`). Two options:
  - **Option A (recommended):** Use a pre-built public Lambda layer for LightGBM.  
    ARN (us-east-1): `arn:aws:lambda:ap-south-1:446751924810:layer:python-3-12-scikit-learn-lgbm:1`  
    (search for "lightgbm lambda layer" in Serverless Application Repository)
  - **Option B:** Bundle `libgomp1` in your Docker image if using a container image Lambda.

### 5.4 AWS Console — Lambda Environment Variables

```
EARLY_WARNING_ML_ENABLED  = true
MODEL_S3_BUCKET           = rural-credit-models
EW_MODEL_S3_PREFIX        = early_warning/v1
MODEL_CACHE_DIR           = /tmp/models
AWS_DEFAULT_REGION        = ap-south-1
```

### 5.5 AWS Console — ECS Task Definition

```json
[
  { "name": "EARLY_WARNING_ML_ENABLED", "value": "true" },
  { "name": "MODEL_S3_BUCKET",          "value": "rural-credit-models" },
  { "name": "EW_MODEL_S3_PREFIX",       "value": "early_warning/v1" },
  { "name": "AWS_DEFAULT_REGION",       "value": "ap-south-1" }
]
```

---

## 6. Model 4 — Scenario Simulation (Monte Carlo)

**Service:** `services/early_warning/` (same service as Model 3)  
**Artifacts:** `scenario_dist_params.json` (tiny), `scenario_seasonal.json` (tiny)  
**Algorithm:** Parametric Monte Carlo with log-normal income distributions; no gradient training

### 6.1 Environment Variables

| Variable | Where to set | Example value | Required? |
|---|---|---|---|
| `SCENARIO_ML_ENABLED` | Lambda env / ECS task def | `true` | Yes |
| `MODEL_S3_BUCKET` | Lambda env / ECS task def | `rural-credit-models` | Yes |
| `SCENARIO_MODEL_S3_PREFIX` | Lambda env / ECS task def | `scenario/v1` | Yes |
| `SCENARIO_N_SIMULATIONS` | Lambda env / ECS task def | `1000` | No (default 1000) |
| `MODEL_CACHE_DIR` | Lambda env | `/tmp/models` | No |
| `AWS_DEFAULT_REGION` | Lambda env / ECS task def | `ap-south-1` | No |

> **`SCENARIO_N_SIMULATIONS`:** Tunable knob for latency vs. accuracy trade-off.  
> 1000 draws takes ~5 ms in Python. Use 500 on Lambda to stay within p99 latency budgets.

### 6.2 Updated `_ensure_loaded()` for AWS

Replace the current body of `_ensure_loaded()` in
`services/early_warning/ml/scenario_model.py`:

```python
def _ensure_loaded() -> bool:
    global _dist_params, _seasonal_muls
    if _dist_params is not None:
        return True

    import os
    from services.shared.ml_utils import download_model

    prefix = os.getenv("SCENARIO_MODEL_S3_PREFIX", "")

    def _load_json(filename: str) -> dict | list:
        if prefix:
            local = download_model(f"{prefix}/{filename}")
        else:
            local = _MODEL_DIR / filename
        if not local.exists():
            raise FileNotFoundError(local)
        with open(local) as f:
            return json.load(f)

    try:
        _dist_params   = _load_json("scenario_dist_params.json")
        seasonal_data  = _load_json("scenario_seasonal.json")
        _seasonal_muls = seasonal_data.get(
            "monthly_inflow_multipliers", _DEFAULT_SEASONAL
        )
        logger.info("Scenario distribution params loaded")
        return True
    except FileNotFoundError:
        logger.warning("Scenario params not found — using hardcoded defaults")
        _dist_params   = _DEFAULT_DIST_PARAMS
        _seasonal_muls = _DEFAULT_SEASONAL
        return True   # this model degrades gracefully, always return True
    except Exception as exc:
        logger.error("Failed to load scenario params: %s", exc)
        _dist_params   = _DEFAULT_DIST_PARAMS
        _seasonal_muls = _DEFAULT_SEASONAL
        return True
```

Also update the `simulate()` call signature to read `SCENARIO_N_SIMULATIONS`:

```python
import os
# At the top of simulate():
n_simulations = int(os.getenv("SCENARIO_N_SIMULATIONS", str(n_simulations)))
```

### 6.3 Lambda-specific Considerations

- **Memory:** 256 MB is enough (numpy Monte Carlo with 1000 draws uses ~50 MB peak).
- **Timeout:** Monte Carlo at n=1000 finishes in under 50 ms; 10 s timeout is plenty.
- **Shared Lambda with EW model:** Both `warning_model.py` and `scenario_model.py`
  live in the same `early_warning` service, so they share the same Lambda function /
  ECS task. Set all four env vars on that single function.

### 6.4 AWS Console — Lambda Environment Variables (full set for early_warning service)

Since both Model 3 and Model 4 run in the same service, set all together:

```
EARLY_WARNING_ML_ENABLED   = true
SCENARIO_ML_ENABLED        = true
MODEL_S3_BUCKET            = rural-credit-models
EW_MODEL_S3_PREFIX         = early_warning/v1
SCENARIO_MODEL_S3_PREFIX   = scenario/v1
SCENARIO_N_SIMULATIONS     = 1000
MODEL_CACHE_DIR            = /tmp/models
AWS_DEFAULT_REGION         = ap-south-1
```

### 6.5 AWS Console — ECS Task Definition (early_warning service)

```json
[
  { "name": "EARLY_WARNING_ML_ENABLED",  "value": "true" },
  { "name": "SCENARIO_ML_ENABLED",       "value": "true" },
  { "name": "MODEL_S3_BUCKET",           "value": "rural-credit-models" },
  { "name": "EW_MODEL_S3_PREFIX",        "value": "early_warning/v1" },
  { "name": "SCENARIO_MODEL_S3_PREFIX",  "value": "scenario/v1" },
  { "name": "SCENARIO_N_SIMULATIONS",    "value": "1000" },
  { "name": "AWS_DEFAULT_REGION",        "value": "ap-south-1" }
]
```

---

## 7. Environment Variable Reference

Complete table of every ML-related env var across all services:

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `RISK_ML_ENABLED` | risk_assessment | `false` | Activate XGBoost; `false` → heuristic |
| `CASHFLOW_ML_ENABLED` | cashflow_service | `false` | Activate Ridge; `false` → heuristic |
| `EARLY_WARNING_ML_ENABLED` | early_warning | `false` | Activate IsoForest + LightGBM |
| `SCENARIO_ML_ENABLED` | early_warning | `false` | Activate Monte Carlo simulation |
| `MODEL_S3_BUCKET` | all three | *(none)* | S3 bucket name for artifacts |
| `RISK_MODEL_S3_PREFIX` | risk_assessment | *(none)* | S3 key prefix for risk artifacts |
| `CASHFLOW_MODEL_S3_PREFIX` | cashflow_service | *(none)* | S3 key prefix for cashflow artifacts |
| `EW_MODEL_S3_PREFIX` | early_warning | *(none)* | S3 key prefix for early-warning artifacts |
| `SCENARIO_MODEL_S3_PREFIX` | early_warning | *(none)* | S3 key prefix for scenario JSON files |
| `MODEL_CACHE_DIR` | all three | `/tmp/models` | Local directory to cache downloaded artifacts |
| `SCENARIO_N_SIMULATIONS` | early_warning | `1000` | Monte Carlo sample count (tune for latency) |
| `AWS_DEFAULT_REGION` | all three | `ap-south-1` | AWS region for boto3 S3 client |

### Where to set these on each AWS service

#### Lambda
1. Open Lambda console → select the function
2. Configuration tab → Environment variables → Edit
3. Add each key/value pair

Or with AWS CLI:
```bash
aws lambda update-function-configuration \
  --function-name risk-assessment-fn \
  --environment "Variables={RISK_ML_ENABLED=true,MODEL_S3_BUCKET=rural-credit-models,RISK_MODEL_S3_PREFIX=risk/v1,MODEL_CACHE_DIR=/tmp/models}"
```

#### ECS (Fargate)
In your task definition JSON, add to `containerDefinitions[n].environment`.  
Or in CDK/Terraform, set as environment map on the container definition.

#### AWS SAM (`template.yaml`)
Each service already has a `template.yaml`. Add to the `Globals` or per-function
`Environment` section:

```yaml
# services/risk_assessment/template.yaml
Globals:
  Function:
    Environment:
      Variables:
        RISK_ML_ENABLED: !Ref RiskMlEnabled          # SSM parameter ref
        MODEL_S3_BUCKET: !Ref ModelS3Bucket
        RISK_MODEL_S3_PREFIX: !Ref RiskModelS3Prefix
        MODEL_CACHE_DIR: /tmp/models

Parameters:
  RiskMlEnabled:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /rural-credit/risk/ml-enabled
  ModelS3Bucket:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /rural-credit/model-bucket
  RiskModelS3Prefix:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /rural-credit/risk/model-prefix
```

Store actual values in SSM Parameter Store so you can toggle ML on/off without a
redeploy:
```bash
aws ssm put-parameter --name /rural-credit/risk/ml-enabled      --value true      --type String --overwrite
aws ssm put-parameter --name /rural-credit/model-bucket         --value rural-credit-models --type String --overwrite
aws ssm put-parameter --name /rural-credit/risk/model-prefix    --value risk/v1   --type String --overwrite
```

---

## 8. CI/CD: Retraining & Artifact Promotion

When you retrain the models (e.g. weekly batch job on AWS Batch or SageMaker
Training Job), upload to a versioned S3 prefix and promote by updating the
SSM parameters — zero-downtime deployment:

```bash
# 1. Train
python ml-pipeline/train_all.py

# 2. Upload to a new version prefix
VERSION=$(date +%Y%m%d)
aws s3 cp ml-pipeline/saved_models/risk_model.joblib     s3://rural-credit-models/risk/v${VERSION}/risk_model.joblib
aws s3 cp ml-pipeline/saved_models/risk_explainer.joblib s3://rural-credit-models/risk/v${VERSION}/risk_explainer.joblib
aws s3 cp ml-pipeline/saved_models/risk_features.joblib  s3://rural-credit-models/risk/v${VERSION}/risk_features.joblib
aws s3 cp ml-pipeline/saved_models/risk_label_names.joblib s3://rural-credit-models/risk/v${VERSION}/risk_label_names.joblib
# ... repeat for the other models

# 3. Promote (triggers cold-start reload on next Lambda invocation)
aws ssm put-parameter --name /rural-credit/risk/model-prefix \
  --value risk/v${VERSION} --type String --overwrite

# 4. Force Lambda to pick up changes immediately (optional)
aws lambda update-function-configuration \
  --function-name risk-assessment-fn \
  --environment "Variables={RISK_MODEL_S3_PREFIX=risk/v${VERSION}, ...}"
```

For rollback, simply repoint the SSM parameter to the previous version prefix.
