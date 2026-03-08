# ML Pipeline — Rural Credit Risk & Cash Flow Platform

End-to-end machine learning infrastructure for training, evaluating, deploying,
and monitoring the four core models:

| Model | Algorithm | Service |
|---|---|---|
| Risk Scoring | XGBoost multi-class | `risk_assessment` (port 8003) |
| Cash Flow Prediction | Prophet + LSTM | `cashflow_service` (port 8004) |
| Early Warning | Isolation Forest + LightGBM | `early_warning` (port 8005) |
| Scenario Simulation | Monte Carlo + Regression | `early_warning` (port 8005) |

## Directory Layout

```
ml-pipeline/
├── data/
│   ├── synthetic/          # Synthetic training data generators
│   └── ingestion/          # External data fetchers (Agmarknet, IMD, NASA)
├── feature_store/          # SageMaker Feature Store setup
├── models/                 # Training & inference scripts per model
│   ├── risk_scoring/
│   ├── cashflow_prediction/
│   ├── early_warning/
│   └── scenario_simulation/
├── pipelines/              # SageMaker Pipeline DAGs
├── evaluation/             # Metrics, bias detection, backtesting
└── lambdas/                # Retraining triggers & notifications
```

## Quick Start (Local)

```bash
# Install dependencies
pip install -r requirements.txt

# Generate synthetic data
python -m ml-pipeline.data.synthetic.generate_synthetic_data --output data/output

# Train risk model locally
python -m ml-pipeline.models.risk_scoring.local_train

# Evaluate
python -m ml-pipeline.evaluation.evaluate_risk
```

## AWS Deployment

See `pipelines/` for SageMaker Pipeline definitions.
Trigger via EventBridge or manually from SageMaker Studio.
