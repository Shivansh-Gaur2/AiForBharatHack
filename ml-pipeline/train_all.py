"""Master training script — generates synthetic data and trains all 4 ML models.

Usage (from workspace root):
    python ml-pipeline/train_all.py

What it does:
  1. Generate synthetic training data (risk, cashflow, early_warning CSVs)
  2. Train XGBoost risk-scoring model
  3. Train Ridge cashflow prediction model
  4. Train IsolationForest + LightGBM early-warning models
  5. Fit log-normal distribution params for scenario simulation

All artefacts are saved to ml-pipeline/saved_models/ and the services
pick them up automatically at boot when the ML flags are set:

    RISK_ML_ENABLED=true
    CASHFLOW_ML_ENABLED=true
    EARLY_WARNING_ML_ENABLED=true
    SCENARIO_ML_ENABLED=true
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT    = Path(__file__).parent.parent    # workspace root
MLDIR   = Path(__file__).parent           # ml-pipeline/
PYTHON  = sys.executable


def run(script: Path, label: str) -> None:
    bar = "─" * 60
    print(f"\n{bar}")
    print(f"  {label}")
    print(bar)
    t0 = time.perf_counter()
    result = subprocess.run([PYTHON, str(script)], cwd=str(ROOT))
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        print(f"\n[ERROR] {label} failed (exit code {result.returncode})")
        sys.exit(result.returncode)
    print(f"  ✓ Done in {elapsed:.1f}s")


def main() -> None:
    total_start = time.perf_counter()

    run(MLDIR / "data"   / "synthetic"         / "generate_synthetic_data.py", "Step 1/5 — Generating synthetic data")
    run(MLDIR / "models" / "risk_scoring"       / "local_train.py",            "Step 2/5 — Training Risk Scoring (XGBoost)")
    run(MLDIR / "models" / "cashflow_prediction"/ "local_train.py",            "Step 3/5 — Training Cash Flow (Ridge seasonal)")
    run(MLDIR / "models" / "early_warning"      / "local_train.py",            "Step 4/5 — Training Early Warning (IF + LightGBM)")
    run(MLDIR / "models" / "scenario_simulation"/ "local_train.py",            "Step 5/5 — Fitting Scenario distributions")

    elapsed   = time.perf_counter() - total_start
    saved     = MLDIR / "saved_models"
    artefacts = sorted(saved.glob("*")) if saved.exists() else []

    print(f"\n{'═' * 60}")
    print(f"  ALL MODELS TRAINED  ({elapsed:.1f}s total)")
    print(f"{'═' * 60}")
    print(f"\nArtefacts in {saved.relative_to(ROOT)}:")
    for p in artefacts:
        size_kb = p.stat().st_size // 1024
        print(f"  {p.name:<45} {size_kb:>6} KB")

    print("\nTo enable ML inference, set environment variables:")
    print("  RISK_ML_ENABLED=true")
    print("  CASHFLOW_ML_ENABLED=true")
    print("  EARLY_WARNING_ML_ENABLED=true")
    print("  SCENARIO_ML_ENABLED=true")


if __name__ == "__main__":
    main()
