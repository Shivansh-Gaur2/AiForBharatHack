# ML Models — Research, Data Sources & AWS Implementation Plan

> **Context**: This document covers the full machine-learning strategy for the Rural Credit Risk & Cash Flow platform.  
> All four services currently run **rule-based heuristics**. This document defines the models that replace or augment them, the data required to train them, and how to operationalise everything on AWS.

---

## Table of Contents

1. [Current State — What the Heuristics Do](#1-current-state)
2. [ML Model Inventory — Which Models, Where, Why](#2-ml-model-inventory)
   - 2.1 [Risk Scoring Model (XGBoost)](#21-risk-scoring-model)
   - 2.2 [Cash Flow Prediction Model (Prophet + LSTM)](#22-cash-flow-prediction-model)
   - 2.3 [Early Warning / Anomaly Detection (Isolation Forest + Gradient Boosting)](#23-early-warning--anomaly-detection-model)
   - 2.4 [Scenario Impact Simulator (Monte Carlo + Regression)](#24-scenario-impact-simulator)
3. [Data Sources](#3-data-sources)
   - 3.1 [Primary Datasets](#31-primary-datasets)
   - 3.2 [External Real-Time APIs (already integrated)](#32-external-real-time-apis)
   - 3.3 [Synthetic Data Strategy](#33-synthetic-data-strategy)
4. [Feature Engineering Reference](#4-feature-engineering-reference)
5. [AWS Implementation Plan](#5-aws-implementation-plan)
   - 5.1 [Architecture Overview](#51-architecture-overview)
   - 5.2 [Data Ingestion & Storage (S3 + Glue)](#52-data-ingestion--storage)
   - 5.3 [Feature Store (SageMaker Feature Store)](#53-feature-store)
   - 5.4 [Training Pipelines (SageMaker Pipelines)](#54-training-pipelines)
   - 5.5 [Model Registry & Approval (SageMaker Model Registry)](#55-model-registry--approval)
   - 5.6 [Inference Endpoints](#56-inference-endpoints)
   - 5.7 [Monitoring & Drift Detection (SageMaker Model Monitor)](#57-monitoring--drift-detection)
   - 5.8 [Bias Detection (Clarify)](#58-bias-detection)
   - 5.9 [Retraining Triggers (EventBridge + Lambda)](#59-retraining-triggers)
   - 5.10 [GenAI Guidance Layer (Bedrock)](#510-genai-guidance-layer)
6. [Directory Layout in the Repository](#6-directory-layout)
7. [Phased Rollout Roadmap](#7-phased-rollout-roadmap)
8. [Model Cards (Summary Sheets)](#8-model-cards)

---

## 1. Current State

| Service | File | Current Approach | What's Missing |
|---|---|---|---|
| `risk_assessment` | `app/domain/models.py::compute_risk_score` | 8 weighted rule functions; fixed thresholds per factor (DTI>0.6 → score 60, etc.) | No learned weights; no interaction effects; no actual training data |
| `cashflow_service` | `app/domain/models.py::build_forecast` | `analyse_seasonal_patterns` averages historical months; `generate_projections` multiplies by weather/market adjustors | No trend learning; no external-data correlation; no confidence calibration |
| `early_warning` | `app/domain/models.py::build_alert` | Hard-coded stress thresholds on DTI, missed payments, income deviation ≥ 20 % | No learned separation boundary; no severity calibration; no leading-indicator detection |
| `early_warning` | `app/domain/models.py::simulate_scenario` | Linear scalar of weather_adjustment × base_income | No distributional uncertainty; no Monte Carlo; no non-linear crop-price interactions |

---

## 2. ML Model Inventory

### 2.1 Risk Scoring Model

**Codebase location**: `services/risk_assessment/ml/risk_model.py`  
**Replaces**: `compute_risk_score()` in `services/risk_assessment/app/domain/models.py`  
**Requirements**: Req 4.1–4.5 (comprehensive risk score across income volatility, debt exposure, repayment history, weather, market)

#### Why XGBoost?

Indian agricultural credit datasets are **tabular, sparse, and mixed-type** (boolean `has_irrigation`, categorical `crop_type`, continuous `DTI`). XGBoost consistently outperforms neural networks on such data because:
- Handles missing values natively (critical for missing-data estimation in Req 8)
- Provides SHAP feature importance — directly maps to the existing `RiskExplanation` model
- Trains on ≤ 10 k samples to a deployable model; scales gracefully to millions
- SageMaker has a first-class built-in XGBoost container (no Docker build needed)

#### Model specification

| Property | Value |
|---|---|
| Algorithm | `XGBoost 1.7` (SageMaker built-in) |
| Task | Multi-class classification (LOW / MEDIUM / HIGH / VERY_HIGH) + regression head for continuous `risk_score` (0–1000) |
| Loss | `multi:softprob` + auxiliary `reg:squarederror` for score head |
| Input schema | 18 features (see §4) |
| Output | Probability vector (4 classes) → argmax = category; weighted sum → score |
| Explainability | SHAP TreeExplainer → maps to `RiskFactor.score` override at inference time |

#### Feature set (18 features)

```
income_volatility_cv        float  coefficient of variation of monthly income
annual_income               float  rolling 12-month income (INR)
months_below_average        int    count of months below trailing average
debt_to_income_ratio        float  total EMI obligations / monthly income
total_outstanding           float  sum of active loan principals (INR)
active_loan_count           int    number of open loans
credit_utilisation          float  drawn / sanctioned across all loans
on_time_repayment_ratio     float  on-time payments / total due payments
has_defaults                bool   any loan ever 90+ DPD
seasonal_variance           float  std-dev of income across the 4 seasons
crop_diversification_index  float  Herfindahl index of crop revenue shares (0–1)
weather_risk_score          float  IMD district drought/flood percentile (0–100)
market_risk_score           float  MSP deviation percentile for primary crop (0–100)
dependents                  int    household members not earning
age                         int    borrower age in years
has_irrigation              bool   irrigated land (reduces seasonal variance)
land_holding_acres          float  total agricultural land in acres
soil_quality_score          float  NABARD / soil health card score (0–100)
```

#### Integration into existing service

```python
# services/risk_assessment/ml/risk_model.py   (NEW FILE)

import boto3, json
import numpy as np
from services.risk_assessment.app.domain.models import RiskInput, RiskAssessment

ENDPOINT_NAME = "rural-credit-risk-scoring-v1"

def predict_risk(inp: RiskInput) -> dict:
    """Call SageMaker real-time endpoint; return score + probabilities."""
    client = boto3.client("sagemaker-runtime", region_name="ap-south-1")
    payload = _to_feature_vector(inp)
    resp = client.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="text/csv",
        Body=",".join(map(str, payload)),
    )
    result = json.loads(resp["Body"].read())
    return result   # {"score": 342, "category": "MEDIUM", "probabilities": [...], "shap": {...}}

def _to_feature_vector(inp: RiskInput) -> list:
    return [
        inp.income_volatility_cv,
        inp.annual_income,
        inp.months_below_average,
        inp.debt_to_income_ratio,
        inp.total_outstanding,
        inp.active_loan_count,
        inp.credit_utilisation,
        inp.on_time_repayment_ratio,
        int(inp.has_defaults),
        inp.seasonal_variance,
        inp.crop_diversification_index,
        inp.weather_risk_score,
        inp.market_risk_score,
        inp.dependents,
        inp.age,
        int(inp.has_irrigation),
        getattr(inp, "land_holding_acres", 2.0),
        getattr(inp, "soil_quality_score", 50.0),
    ]
```

In `services/risk_assessment/app/domain/services.py`, `compute_risk_score(risk_input)` can be replaced with a flag-gated call:

```python
USE_ML_MODEL = os.getenv("RISK_ML_ENABLED", "false").lower() == "true"

assessment = (
    ml_risk_model.predict_risk(risk_input)
    if USE_ML_MODEL
    else compute_risk_score(risk_input)   # heuristic fallback
)
```

---

### 2.2 Cash Flow Prediction Model

**Codebase location**: `services/cashflow_service/ml/cashflow_model.py`  
**Replaces / augments**: `build_forecast()` projection logic in `services/cashflow_service/app/domain/models.py`  
**Requirements**: Req 3.1–3.5 (seasonal alignment, timing windows, repayment capacity, uncertainty bands)

#### Model choice: Facebook Prophet + optional LSTM upgrade

**Phase A — Prophet (fast to deploy, interpretable)**  
Prophet is ideal for the first iteration because:
- Designed for business time-series with strong **seasonality** (exactly the kharif/rabi/zaid cycle)
- Handles **missing months** gracefully (common in rural income records)
- Produces calibrated confidence intervals out-of-the-box → maps to `UncertaintyBand` model
- Train per-profile or on population clusters; SageMaker serverless inference handles low-traffic profiles

**Phase B — LSTM (when ≥ 24 months of per-profile history accumulates)**  
A two-layer LSTM captures non-linear dependencies between:
- Lagged income
- Rolling weather anomaly index
- MSP-to-actual price ratio for the primary crop

#### Model specification

| Property | Phase A (Prophet) | Phase B (LSTM) |
|---|---|---|
| Framework | `prophet==1.1.5` | `TensorFlow 2.15` / `PyTorch 2.2` |
| Input window | All available months | 24-month lookback |
| Output horizon | 12 months | 12 months |
| Output | Monthly (mean, lower_80, upper_80, lower_95, upper_95) | Same |
| Seasonality | Yearly + custom Kharif/Rabi regressors | Learned |
| External regressors | `weather_index`, `msp_deviation`, `diesel_price_index` | Same as features |
| Training granularity | Cluster-level (k-means on crop + district) then fine-tuned per profile | Per profile (transfer learning from cluster model) |
| SageMaker container | Custom Docker (prophet + pandas) | Built-in TensorFlow / PyTorch |

#### Seasonal regressors (India-specific)

```python
# Add custom seasonality aligned to Indian crop calendar
model.add_seasonality(name="kharif",  period=365.25, fourier_order=5)
model.add_seasonality(name="rabi",    period=365.25, fourier_order=5)
model.add_regressor("wheat_msp_deviation")      # from Agmarknet
model.add_regressor("southwest_monsoon_index")  # from IMD
model.add_regressor("diesel_retail_price")      # from PPAC
```

#### Integration into existing service

The `build_forecast()` currently calls `analyse_seasonal_patterns` and `generate_projections`. The ML wrapper produces the same `monthly_projections: list[MonthlyProjection]` signature:

```python
# services/cashflow_service/ml/cashflow_model.py   (NEW FILE)

def predict_cashflow(
    profile_id: str,
    records: list[CashFlowRecord],
    horizon_months: int = 12,
    weather_adjustment: float = 1.0,
    market_adjustment: float = 1.0,
) -> list[MonthlyProjection]:
    """Invoke Prophet endpoint and translate output to MonthlyProjection list."""
    ...
```

---

### 2.3 Early Warning / Anomaly Detection Model

**Codebase location**: `services/early_warning/ml/warning_model.py`  
**Replaces**: `build_alert()` and `compute_repayment_stress()` threshold logic  
**Requirements**: Req 5.1–5.5 (income deviation, repayment stress, leading indicators)

#### Why two-stage?

The current single-threshold approach misses **leading indicators** (stress appears 1–2 months before default). A two-stage model provides both:

| Stage | Model | Purpose |
|---|---|---|
| Anomaly detection | **Isolation Forest** | Unsupervised; flags unusual income/repayment patterns without needing labelled default data |
| Severity classification | **LightGBM** binary classifier per severity tier | Uses anomaly score + current financial features to predict INFO / WARNING / CRITICAL within a 60-day window |

#### Why Isolation Forest first?

- Cold-start problem: labelled early-warning data doesn't exist yet in the system
- Isolation Forest trains on **normal behaviour** (majority class) and computes anomaly scores for outliers
- As labelled incidents accumulate, LightGBM classifier replaces the second stage

#### Feature set (early warning — 22 features)

```
income_deviation_3m       float  % deviation from 3-month forecast
income_deviation_6m       float  % deviation from 6-month forecast
missed_payments_ytd       int    missed EMI payments in last 12 months
days_overdue_avg          float  average days past due across all loans
dti_delta_3m              float  DTI ratio change in last 3 months
surplus_trend_slope       float  linear regression slope of 6-month surplus trend
weather_shock_score       float  IMD anomaly from normal (district-level)
market_price_shock        float  Agmarknet MSP deviation this month
crop_failure_probability  float  NDVI satellite-derived crop stress index
loan_count_increase       int    new loans taken in last 6 months
credit_utilisation_delta  float  credit utilisation rate-of-change
has_informal_debt         bool   any informal lender activity detected
seasonal_stress_flag      bool   current month is historically high-stress
risk_category_current     int    encoded current risk category (0–3)
repayment_months_remaining int   months until maturity of largest loan
income_sources_count      int    diversified income sources
land_holding_acres        float  total land (larger = more cushion)
has_irrigation            bool   irrigation reduces weather sensitivity
household_size            int    total dependents + earners
district_drought_index    float  CWC / IMD district drought percentile
prev_alert_severity       int    encoded severity of last alert (0–3)
days_since_last_alert     int    lead time from last alert
```

#### Integration into existing service

```python
# services/early_warning/ml/warning_model.py   (NEW FILE)

def predict_alert(features: dict) -> dict:
    """
    Returns {"anomaly_score": float, "severity": str, "probability": float,
             "leading_indicators": list[str]}
    """
    ...

# In services/early_warning/app/domain/services.py — flag-gated:
alert = (
    ml_warning_model.predict_alert(feature_dict)
    if USE_ML_ALERT
    else build_alert(profile_id, stress, deviations, risk_category)
)
```

---

### 2.4 Scenario Impact Simulator

**Codebase location**: `services/early_warning/ml/scenario_model.py`  
**Replaces**: `simulate_scenario()` linear scalar logic  
**Requirements**: Req 6.1–6.5 (weather disruption, market price volatility, what-if repayment capacity)

#### Why Monte Carlo over pure regression?

Scenario simulation inherently deals with **uncertainty**, not point estimates. The existing code multiplies base income by `weather_adjustment` (a scalar). This:
- Gives a single outcome, not a distribution
- Ignores co-variance between weather and market prices (drought → lower yield AND lower MSP demand)
- Doesn't propagate uncertainty into the `SimulationResult.repayment_capacity`

**Approach**: Parametric Monte Carlo with a learned correlation matrix.

| Component | Technique | Purpose |
|---|---|---|
| Parameter distribution fitting | MLE on historical district crop data | Fit `(μ, σ)` for income given a scenario type |
| Correlation matrix | `scipy.stats.pearsonr` across 5-year district data | Capture weather↔market↔income co-variance |
| Simulation | 10,000 Monte Carlo draws per scenario | Output: `[p5, p25, p50, p75, p95]` income trajectory |
| Repayment capacity under stress | Regression tree (scikit-learn) | Predict months-in-deficit given p5 income trajectory + loan obligations |

#### Scenario input parameters (enhanced)

```python
@dataclass
class ScenarioParameters:
    scenario_type: str          # "drought", "flood", "price_crash", "input_cost_spike", "custom"
    weather_impact_percentile: float  # e.g. 10th percentile = severe drought year
    market_price_change_pct: float    # -30% = 30% price crash
    crop_yield_change_pct: float      # direct yield impact
    input_cost_change_pct: float      # fertiliser, diesel
    months_affected: int              # duration of the scenario
    simulation_runs: int = 10_000     # MC draws
```

#### Output structure (enhanced `SimulationResult`)

```python
@dataclass
class SimulationResult:
    scenario_id: str
    income_distribution: dict       # {p5, p25, p50, p75, p95} monthly income
    repayment_capacity_stressed: float  # EMI coverage ratio at p10 income
    months_in_deficit_p50: int         # median months where outflow > inflow
    months_in_deficit_p90: int         # pessimistic months in deficit
    recovery_months_estimate: int      # months to return to pre-shock baseline
    recommended_loan_restructure: dict # {grace_period_months, emi_reduction_pct}
    var_95: float                      # Value-at-Risk at 95% confidence
```

---

## 3. Data Sources

### 3.1 Primary Datasets

#### A. Credit / Repayment Data (for Risk Scoring + Early Warning training)

| Dataset | Source | URL | Format | Volume | Label availability |
|---|---|---|---|---|---|
| **RBI Basic Statistical Returns (BSR)** | Reserve Bank of India | [rbi.org.in/Scripts/AnnualPublications.aspx](https://www.rbi.org.in/Scripts/AnnualPublications.aspx) | Excel/CSV | District-level aggregates, annual | No individual labels; useful for base rate calibration |
| **NABARD Rural Financial Inclusion Survey** | NABARD | [nabard.org/content.aspx?id=572](https://www.nabard.org/content.aspx?id=572) | Microdata (restricted; apply via NABARD) | ~70,000 households | Income, loans, repayment status |
| **ICRISAT Village Dynamics in South Asia (VDSA)** | ICRISAT | [vdsa.icrisat.org](http://vdsa.icrisat.org) | Panel CSV | 30+ villages, 30+ years, household-level | Gold standard for agricultural income volatility |
| **CMIE CPHS (Consumer Pyramids)** | CMIE | [cmie.com/kommon/bin/sr.php?kall=wsytpanels](https://www.cmie.com) | API / CSV (paid) | 170,000 households monthly | Income, employment, expenditure — individual level |
| **MFIN MicroScape** | MFIN | [mfin.org.in](https://mfin.org.in/microscape/) | Reports / negotiated data share | District-level MFI penetration and default rates | Default rates by district/state |
| **Sa-Dhan National Survey of Microfinance** | Sa-Dhan | [sa-dhan.net](https://sa-dhan.net/adl/) | Annual PDF reports; CSV negotiated | State-level PAR30, write-off rates | Aggregate default indicators |
| **SHG-Bank Linkage Data** | NABARD / DAY-NRLM | [nrlm.gov.in](https://www.nrlm.gov.in) | CSV on data.gov.in | 12M SHGs, district-level | Repayment status |

#### B. Agricultural / Crop Data (for Cash Flow Prediction + Scenario Simulation)

| Dataset | Source | URL | Format | Coverage |
|---|---|---|---|---|
| **Agmarknet Wholesale Price Data** | AGMARKNET / data.gov.in | [agmarknet.gov.in](https://agmarknet.gov.in) | Daily CSV via API | 7,500+ mandis, 300+ commodities, since 2000 |
| **APMC Price Data (eNAM)** | eNAM | [enam.gov.in/web/](https://enam.gov.in/web/) | CSV + API | Integrated mandis across 22 states |
| **Ministry of Agriculture (DACFW) — Crop Statistics** | data.gov.in | [data.gov.in/catalog/crop-statistics](https://data.gov.in/catalog/crop-statistics) | CSV | State/district, annual acreage + production, 2001–2023 |
| **Forecasted Agricultural Output (FASALs)** | IASRI / DACFW | [iasri.res.in](https://iasri.res.in) | CSV / Excel | District-level yield forecasts before harvest |
| **MSP Announced Prices** | CACP | [cacp.dacnet.nic.in](https://cacp.dacnet.nic.in) | Annual Excel | Kharif + Rabi MSP for 23 crops since 1975 |
| **Input Cost Data (fertiliser, diesel)** | PPAC / FCI | [ppac.gov.in](https://ppac.gov.in), [fci.gov.in](https://fci.gov.in) | Monthly PDF/CSV | Fertiliser prices, diesel retail, 2000–present |

#### C. Weather Data (for Risk + Cash Flow + Early Warning models)

| Dataset | Source | URL | Format | Resolution |
|---|---|---|---|---|
| **IMD Daily Gridded Rainfall (0.25° × 0.25°)** | India Meteorological Department | [imdpune.gov.in](https://imdpune.gov.in/lrfindex.php) | NetCDF / CSV (apply GriddedData) | Daily, 1901–present, entire India |
| **IMD District-Level Drought Monitor** | Drought Monitor India | [imd.gov.in/pages/drought_main.php](https://imd.gov.in/pages/drought_main.php) | PDF tables; scrape to CSV | Weekly, district-level |
| **NASA POWER API** | NASA | [power.larc.nasa.gov/api/](https://power.larc.nasa.gov/api/) | REST JSON | Daily, 0.5° global, 1981–present; free, no auth |
| **ERA5 Reanalysis (ECMWF)** | Copernicus CDS | [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu/) | NetCDF via CDS API | Hourly, 31 km global, 1940–present; free registration |
| **OpenWeatherMap (already integrated)** | OpenWeatherMap | `api.openweathermap.org` | JSON | Current + 5-day; already wired in `WeatherAdapter` |
| **Sentinel-2 NDVI (crop stress)** | AWS Open Data / ESA | [registry.opendata.aws/sentinel-2/](https://registry.opendata.aws/sentinel-2/) | GeoTIFF on S3 | 10 m, 5-day revisit; free on AWS |

#### D. Socioeconomic / Demographic Data

| Dataset | Source | URL | Notes |
|---|---|---|---|
| **SECC 2011 (Socio-Economic Caste Census)** | data.gov.in | [secc.gov.in](http://secc.gov.in) | Household poverty proxies, land holding, amenities; district × village block level |
| **Soil Health Card Data** | Ministry of Agriculture | [soilhealth.dac.gov.in](https://soilhealth.dac.gov.in) | Soil quality (N/P/K, pH, EC) per survey number; 220M cards issued |
| **PMKSY Irrigation Data** | Jal Shakti Ministry | [pmksy.gov.in](https://pmksy.gov.in) | District irrigated area, water source type |
| **Census 2011 Village-level Data** | Census India | [censusindia.gov.in](https://censusindia.gov.in/2011census/B-series/B_Series_links/b4/Rural/Rural%20B-4.xlsx) | Household size, literacy, land area per village |

---

### 3.2 External Real-Time APIs (already integrated)

These APIs are **already wired** in `services/cashflow_service/app/adapters/` and `services/risk_assessment/app/adapters/`. They should feed the feature pipeline, not just the heuristic adjustors:

| API | Current use | Enhanced ML use |
|---|---|---|
| OpenWeatherMap (`WeatherAdapter`) | `weather_adjustment` scalar | `weather_shock_score`, `southwest_monsoon_index`, `district_drought_index` features |
| Agmarknet (`MarketAdapter`) | `market_adjustment` scalar | `msp_deviation`, `market_price_shock`, `commodity_price_trend_7d` features |

---

### 3.3 Synthetic Data Strategy

Before real data is available, generate synthetic training data using domain knowledge:

```python
# ml-pipeline/data/synthetic/generate_synthetic_data.py

import numpy as np, pandas as pd

def generate_farmer_profiles(n: int = 50_000, seed: int = 42) -> pd.DataFrame:
    """
    Generate realistic training samples for small/marginal Indian farmers.
    
    Calibrated against:
    - ICRISAT VDSA income distributions (log-normal, μ=10.2, σ=0.8 in ln-INR)
    - NABARD survey DTI distribution (mean 0.35, 90th pct 0.72)
    - RBI BSR default rates by district category (urban 2%, semi-urban 4%, rural 8%)
    """
    rng = np.random.default_rng(seed)
    n_small  = int(n * 0.60)   # <2 acres (marginal)
    n_medium = int(n * 0.30)   # 2–5 acres (small)
    n_large  = n - n_small - n_medium   # >5 acres (medium)
    
    records = []
    for segment, size, land_mu, income_mu, default_rate in [
        ("marginal", n_small,  1.2, 9.8,  0.12),
        ("small",    n_medium, 3.5, 10.4, 0.07),
        ("medium",   n_large,  8.0, 11.1, 0.04),
    ]:
        land    = rng.lognormal(np.log(land_mu), 0.4, size)
        income  = rng.lognormal(income_mu, 0.8, size)
        dti     = np.clip(rng.beta(2, 5, size) * 1.2, 0, 1.5)
        default = rng.binomial(1, default_rate, size).astype(bool)
        ...
    
    return pd.DataFrame(records)
```

Key synthetic distributions to calibrate:
- **Income**: Log-normal (`μ_ln ≈ 10.2`, `σ_ln ≈ 0.8`) from ICRISAT data; strong seasonal skew (Kharif harvest months 2–3× non-harvest)
- **DTI**: Beta(2, 5) × 1.2 clipped at 1.5; bimodal for marginal farmers (formal MFI + informal moneylender)
- **Default rate**: 4–12% depending on land segment and district drought exposure
- **Seasonal variance**: Gamma distribution; irrigated farmers have CV ≈ 0.35, rainfed ≈ 0.65

---

## 4. Feature Engineering Reference

### Risk Model Features — Derivation

| Feature | Source service | Derivation |
|---|---|---|
| `income_volatility_cv` | profile_service | `std(monthly_income_12m) / mean(monthly_income_12m)` |
| `seasonal_variance` | profile_service | `std(season_avg_income)` across the 4 seasons |
| `debt_to_income_ratio` | loan_tracker | `sum(monthly_emi) / avg_monthly_income` |
| `credit_utilisation` | loan_tracker | `sum(outstanding) / sum(sanctioned)` |
| `on_time_repayment_ratio` | loan_tracker | `on_time_count / total_due_count` |
| `weather_risk_score` | cashflow_service / weather adapter | IMD district percentile; 0 = no risk, 100 = extreme |
| `market_risk_score` | cashflow_service / market adapter | Agmarknet MSP deviation rolling 3-month z-score, scaled 0–100 |
| `crop_diversification_index` | profile_service | `1 - sum(s²)` where `s` = revenue share of each crop (Herfindahl) |
| `soil_quality_score` | profile_service (future: Soil Health Card API) | Mean of N, P, K, pH normalised sub-scores |

### Cash Flow Prediction Features

| Feature | Lag | Notes |
|---|---|---|
| `monthly_income` | t-1 … t-12 | Core time series; fill missing with seasonal imputation |
| `monthly_expense` | t-1 … t-6 | Household + input costs |
| `month_of_year` | — | `sin(2π·m/12)`, `cos(2π·m/12)` Fourier encoding |
| `season` | — | One-hot: Kharif (Jun–Oct), Rabi (Nov–Feb), Zaid (Mar–May) |
| `southwest_monsoon_cumulative` | — | IMD cumulative rainfall % of LPA (June–Sep) |
| `wheat_msp_deviation` | t-1 | (actual_price - MSP) / MSP |
| `diesel_retail_price_index` | t-1 | PPAC monthly price % change |
| `loan_emi_this_month` | — | Sum of all EMI obligations (from loan_tracker) |

### Early Warning Features

The 22 features listed in §2.3 are all derived from existing service outputs with no external APIs required beyond what's already integrated.

---

## 5. AWS Implementation Plan

### 5.1 Architecture Overview

```
                    ┌───────────────────────────────────────────────────┐
                    │              DATA PLANE (ap-south-1)              │
                    │                                                   │
  External APIs     │  S3 raw/  ──► Glue ETL ──► S3 processed/         │
  (IMD, Agmarknet,  │  (landing)     (daily       (parquet,            │
   NASA POWER)      │                triggers)    partitioned)         │
        │           │                    │                              │
        │           │              SageMaker Feature Store             │
        │           │              (online + offline store)            │
        │           └────────────────────┬──────────────────────────────┘
        │                                │
        │           ┌────────────────────▼──────────────────────────────┐
        │           │           TRAINING PLANE                          │
        │           │                                                   │
        │           │  SageMaker Pipelines ──► Model Registry          │
        │           │  (scheduled weekly)       (approval gate)        │
        │           │                                                   │
        │           │  SageMaker Experiments / MLflow (tracking)       │
        │           └────────────────────┬──────────────────────────────┘
        │                                │
        │           ┌────────────────────▼──────────────────────────────┐
        │           │           SERVING PLANE                           │
        │           │                                                   │
        │           │  SageMaker Endpoints (risk, cashflow)             │
        │           │  Lambda + S3 Model Artefact (early warning,       │
        │           │  scenario — lower traffic)                        │
        │           │                                                   │
        │           │  SageMaker Model Monitor (data drift + bias)      │
        │           └────────────────────┬──────────────────────────────┘
        │                                │
        └────────────────────────────────▼──────────────────────────────
                    FastAPI services call SageMaker / Lambda via boto3
                    (flag-gated: USE_RISK_ML, USE_CASHFLOW_ML, etc.)
```

---

### 5.2 Data Ingestion & Storage

**S3 bucket layout**:
```
s3://rural-credit-ml-data-{account_id}/
├── raw/
│   ├── agmarknet/daily/YYYY/MM/prices.csv
│   ├── imd/monthly/YYYY/MM/district_rainfall.csv
│   ├── nasa_power/daily/YYYY/MM/{lat}_{lon}.json
│   ├── nabard/annual/YYYY/household_survey.parquet
│   └── synthetic/v{n}/farmers_{n}.parquet
├── processed/
│   ├── risk_features/YYYY/MM/features.parquet
│   ├── cashflow_features/YYYY/MM/features.parquet
│   └── early_warning_features/YYYY/MM/features.parquet
├── models/
│   ├── risk_scoring/v{n}/model.tar.gz
│   ├── cashflow_prophet/v{n}/model.tar.gz
│   └── early_warning/v{n}/model.tar.gz
└── evaluation/
    ├── risk_scoring/v{n}/metrics.json
    └── bias_reports/v{n}/clarify_report.json
```

**AWS Glue jobs** (Python-shell, triggered daily by EventBridge):
- `glue_ingest_agmarknet.py` — fetch yesterday's mandi prices, save to `raw/agmarknet/`
- `glue_ingest_imd.py` — scrape IMD district rainfall, save to `raw/imd/`
- `glue_feature_engineering.py` — read raw, compute all features, write parquet to `processed/`

---

### 5.3 Feature Store

Use **SageMaker Feature Store** to centralise features that are shared across models:

```python
# ml-pipeline/feature_store/setup_feature_groups.py

import boto3, sagemaker
from sagemaker.feature_store.feature_group import FeatureGroup

fg_risk = FeatureGroup(
    name="rural-credit-risk-features",
    sagemaker_session=sagemaker.Session(),
)

# Feature definitions mirror §4 feature tables
fg_risk.feature_definitions = [
    FeatureDefinition("profile_id",              FeatureTypeEnum.STRING),
    FeatureDefinition("event_time",              FeatureTypeEnum.FRACTIONAL),
    FeatureDefinition("income_volatility_cv",    FeatureTypeEnum.FRACTIONAL),
    FeatureDefinition("debt_to_income_ratio",    FeatureTypeEnum.FRACTIONAL),
    FeatureDefinition("on_time_repayment_ratio", FeatureTypeEnum.FRACTIONAL),
    FeatureDefinition("weather_risk_score",      FeatureTypeEnum.FRACTIONAL),
    FeatureDefinition("market_risk_score",       FeatureTypeEnum.FRACTIONAL),
    # ... full 18 features
]

fg_risk.create(
    s3_uri=f"s3://rural-credit-ml-data/feature-store/risk/",
    record_identifier_name="profile_id",
    event_time_feature_name="event_time",
    role_arn=SAGEMAKER_ROLE_ARN,
    enable_online_store=True,   # for real-time inference
)
```

**Benefits**: Features computed once, reused across risk, early warning, and scenario models; online store enables <10 ms retrieval at inference time.

---

### 5.4 Training Pipelines

Each model gets a **SageMaker Pipeline** (declarative DAG):

```python
# ml-pipeline/pipelines/risk_scoring_pipeline.py

from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import ProcessingStep, TrainingStep, CreateModelStep
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo

# Step 1: Data preparation
step_process = ProcessingStep(
    name="PrepareRiskTrainingData",
    processor=SKLearnProcessor(framework_version="1.2", ...),
    code="ml-pipeline/processing/prepare_risk_data.py",
    inputs=[ProcessingInput(source=f"s3://.../processed/risk_features/", ...)],
    outputs=[ProcessingOutput(output_name="train", source="/opt/ml/processing/train")],
)

# Step 2: XGBoost training
step_train = TrainingStep(
    name="TrainRiskModel",
    estimator=XGBoost(
        entry_point="ml-pipeline/training/train_risk_xgboost.py",
        framework_version="1.7-1",
        instance_type="ml.m5.xlarge",
        hyperparameters={
            "max_depth": 6,
            "n_estimators": 500,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "multi:softprob",
            "num_class": 4,
            "eval_metric": "mlogloss",
            "scale_pos_weight": 3,   # imbalanced: HIGH/VERY_HIGH < 20% of data
        },
    ),
    inputs={"train": TrainingInput(step_process.properties.ProcessingOutputConfig...)},
)

# Step 3: Evaluate (accuracy, F1, AUC, calibration)
step_eval = ProcessingStep(
    name="EvaluateRiskModel",
    processor=SKLearnProcessor(...),
    code="ml-pipeline/evaluation/evaluate_risk.py",
)

# Step 4: Conditional — only register if F1-weighted >= 0.78
step_register = ConditionStep(
    name="CheckRiskModelQuality",
    conditions=[ConditionGreaterThanOrEqualTo(
        left=JsonGet(step_eval, "evaluation.json", "f1_weighted"),
        right=0.78,
    )],
    if_steps=[RegisterModelStep(...)],
    else_steps=[],  # fail silently; alert via SNS
)

pipeline = Pipeline(
    name="RuralCreditRiskScoringPipeline",
    steps=[step_process, step_train, step_eval, step_register],
)
```

**Equivalent pipeline configurations** exist for:
- `ml-pipeline/pipelines/cashflow_prophet_pipeline.py`
- `ml-pipeline/pipelines/early_warning_pipeline.py`
- `ml-pipeline/pipelines/scenario_simulation_pipeline.py`

**Schedule**: EventBridge rule triggers each pipeline weekly (Sunday 02:00 IST) or on data volume trigger (>500 new profiles with repayment events).

---

### 5.5 Model Registry & Approval

```
SageMaker Model Registry
├── ModelPackageGroup: rural-credit-risk-scoring
│   ├── v1 [Approved]  — XGBoost on synthetic + ICRISAT data
│   ├── v2 [PendingApproval]
│   └── ...
├── ModelPackageGroup: rural-credit-cashflow-prophet
│   └── ...
├── ModelPackageGroup: rural-credit-early-warning
│   └── ...
└── ModelPackageGroup: rural-credit-scenario-simulation
    └── ...
```

**Approval workflow**:
1. Pipeline registers model with status `PendingApproval`
2. EventBridge rule fires → Lambda sends Slack / email notification with evaluation metrics
3. Senior ML engineer approves via SageMaker Studio or API call
4. Approval triggers a CodePipeline deployment that updates the endpoint

---

### 5.6 Inference Endpoints

| Model | Endpoint Type | Instance | Estimated Traffic | Rationale |
|---|---|---|---|---|
| Risk Scoring (XGBoost) | Real-time endpoint | `ml.m5.large` (1 instance) | ~100 req/s peak | Low latency needed; SHAP explanation per call |
| Cash Flow (Prophet) | **Async endpoint** | `ml.m5.xlarge` | 5–10 req/min | Forecasts are batch; not latency-sensitive |
| Early Warning | **Serverless endpoint** | — | <1 req/min per profile | Low traffic; cold start acceptable for alerts |
| Scenario Simulation | **Serverless endpoint** | — | On-demand only | Interactive; acceptable 3–5 s cold start |

**Serverless inference** (risk and cashflow when traffic is low):
```python
serverless_config = ServerlessInferenceConfig(
    memory_size_in_mb=2048,
    max_concurrency=10,
)
model.deploy(serverless_inference_config=serverless_config)
```

#### Local fallback (development / testing)

When `RISK_ML_ENABLED=false`, the existing heuristic `compute_risk_score()` runs. The ML wrapper wraps the endpoint call with a circuit breaker:

```python
# services/shared/circuit_breaker.py already exists — reuse it
from services.shared.circuit_breaker import CircuitBreaker

_cb = CircuitBreaker(name="sagemaker-risk", failure_threshold=3, timeout=30)

def predict_risk(inp: RiskInput) -> dict:
    with _cb:
        return _call_sagemaker_endpoint(inp)
    # circuit open → fall back to heuristic
    return _heuristic_fallback(inp)
```

---

### 5.7 Monitoring & Drift Detection

**SageMaker Model Monitor** — configured per endpoint:

```python
from sagemaker.model_monitor import DefaultModelMonitor, DataCaptureConfig

# Enable data capture on the risk endpoint
data_capture = DataCaptureConfig(
    enable_capture=True,
    sampling_percentage=20,
    destination_s3_uri="s3://rural-credit-ml-data/monitoring/risk/captures/",
)

# Create a monitoring schedule (hourly statistics generation)
monitor = DefaultModelMonitor(role=SAGEMAKER_ROLE_ARN, ...)
monitor.create_monitoring_schedule(
    endpoint_input=risk_endpoint.endpoint_name,
    statistics=Statistics.from_s3_uri(baseline_statistics_uri),
    constraints=Constraints.from_s3_uri(baseline_constraints_uri),
    schedule_cron_expression=CronExpressionGenerator.hourly(),
    output_s3_uri="s3://rural-credit-ml-data/monitoring/risk/reports/",
)
```

**Key metrics monitored**:
- Data drift on `weather_risk_score`, `market_risk_score` (external data shifts)
- Label drift: distribution of predicted risk categories drifting from baseline
- Missing value rate: rural data often arrives incomplete — alert if null rate > 15%

---

### 5.8 Bias Detection

Rural credit models risk perpetuating discrimination against marginal farmers, women borrowers, or scheduled caste/tribe members.

**SageMaker Clarify** runs in the evaluation step of every training pipeline:

```python
# ml-pipeline/evaluation/bias_detection.py

from sagemaker.clarify import (
    BiasConfig, DataConfig, ModelConfig, ModelPredictedLabelConfig,
    SageMakerClarifyProcessor,
)

bias_config = BiasConfig(
    label_values_or_threshold=[1],   # 1 = HIGH or VERY_HIGH risk
    facet_name="land_holding_segment",   # marginal / small / medium
    facet_values_or_threshold=["marginal"],
)

clarify_processor = SageMakerClarifyProcessor(
    role=SAGEMAKER_ROLE_ARN,
    instance_count=1,
    instance_type="ml.m5.xlarge",
    sagemaker_session=sagemaker_session,
)

clarify_processor.run_bias(
    data_config=DataConfig(s3_data_input_path=..., label="risk_category", ...),
    bias_config=bias_config,
    model_config=ModelConfig(model_name=..., instance_type="ml.m5.large"),
    model_predicted_label_config=ModelPredictedLabelConfig(probability_threshold=0.5),
    pre_training_methods="all",
    post_training_methods="all",
)
```

**Bias metrics** evaluated (Clarify SHAP + bias metrics):
- **CI (Class Imbalance)** — is risk score distribution biased against a protected group?
- **DPL (Difference in Positive Proportions in Labels)** — do HIGH-risk predictions disproportionately affect marginal farmers?
- **DPPL (Difference in Positive Proportions in Predicted Labels)** — post-training disparity
- **FTd (Flip Test difference)** — counterfactual: if `land_holding_segment` = small vs marginal, does risk score change?

**Block threshold**: If `|DPL| > 0.1` or `|DPPL| > 0.1`, model registration is blocked and SNS alert fires.

---

### 5.9 Retraining Triggers

**Automatic retraining** is triggered by any of:

| Trigger | EventBridge rule | Description |
|---|---|---|
| Weekly schedule | `cron(0 20 ? * SUN *)` (UTC = 01:30 IST Mon) | Routine weekly retraining on fresh data |
| Data volume | DynamoDB Streams → Lambda: new profile count > 500 since last train | Fresh data available |
| Drift alert | Model Monitor CloudWatch alarm → EventBridge | Feature distribution drifted beyond threshold |
| Manual | API Gateway → Lambda: `POST /retrain/{model_name}` | On-demand by ML team |

```python
# ml-pipeline/lambdas/trigger_retraining.py

import boto3, json

def handler(event, context):
    sm = boto3.client("sagemaker")
    pipeline_name = event.get("pipeline_name", "RuralCreditRiskScoringPipeline")
    resp = sm.start_pipeline_execution(PipelineName=pipeline_name)
    return {"pipeline_execution_arn": resp["PipelineExecutionArn"]}
```

---

### 5.10 GenAI Guidance Layer (Bedrock)

The **Guidance Service** (port 8006) currently produces rule-based text recommendations. With Bedrock, it can generate contextualised natural-language advice in regional languages (Hindi, Kannada, Tamil, Telugu, Marathi).

**Architecture**:
```
RiskAssessment + CashFlowForecast + Alert
         │
         ▼
Bedrock Invoke (Claude 3 Haiku — low latency, cost-effective)
  system prompt: "You are a financial advisor for Indian smallholder farmers.
                  Respond in {language}. Keep advice to 3 bullet points under
                  50 words each. Reference the specific risk factors provided."
  user message:  Structured JSON of the farmer's risk context
         │
         ▼
Localised guidance text  →  GuidanceService.generate_guidance()
```

**Model selection** (AWS Bedrock — `ap-south-1`):

| Use case | Model | Why |
|---|---|---|
| Farmer guidance (Hindi/regional) | `anthropic.claude-3-haiku-20240307-v1:0` | Cheap (~$0.00025/1K tokens), multilingual, 200K context |
| Loan officer dashboard summaries | `anthropic.claude-3-sonnet-20240229-v1:0` | Better reasoning for complex multi-scenario summaries |
| Risk explanation narratives | `amazon.titan-text-lite-v1` | Cheapest option when input is structured and output is templated |

---

## 6. Directory Layout

```
ml-pipeline/                              ← NEW — entire ML infrastructure
├── README.md                             ← This file
├── requirements.txt                      ← sagemaker, xgboost, prophet, shap, lightgbm, ...
│
├── data/
│   ├── synthetic/
│   │   ├── generate_synthetic_data.py    ← Generates training data with ICRISAT-calibrated distributions
│   │   └── synthetic_schema.json
│   ├── ingestion/
│   │   ├── ingest_agmarknet.py           ← Fetch daily mandi prices → S3
│   │   ├── ingest_imd_rainfall.py        ← Fetch IMD district data → S3
│   │   └── ingest_nasa_power.py          ← Fetch weather covariates → S3
│   └── feature_engineering/
│       ├── risk_features.py              ← Compute all 18 risk features from raw data
│       ├── cashflow_features.py          ← Build time-series feature matrix
│       └── early_warning_features.py     ← Compute 22 early-warning features
│
├── feature_store/
│   ├── setup_feature_groups.py           ← Create SageMaker Feature Groups
│   └── feature_definitions/
│       ├── risk_feature_group.json
│       ├── cashflow_feature_group.json
│       └── early_warning_feature_group.json
│
├── models/
│   ├── risk_scoring/
│   │   ├── train_risk_xgboost.py         ← SageMaker training script
│   │   ├── inference.py                  ← model_fn, predict_fn, output_fn (SageMaker serving)
│   │   └── local_train.py                ← Local dev: train on synthetic data
│   ├── cashflow_prediction/
│   │   ├── train_prophet.py
│   │   ├── inference.py
│   │   └── local_train.py
│   ├── early_warning/
│   │   ├── train_isolation_forest.py     ← Phase A: unsupervised anomaly detection
│   │   ├── train_lightgbm_classifier.py  ← Phase B: severity classification
│   │   ├── inference.py
│   │   └── local_train.py
│   └── scenario_simulation/
│       ├── fit_distributions.py          ← Fit income/yield distributions per district
│       ├── monte_carlo.py                ← Core MC simulation engine
│       ├── inference.py
│       └── local_train.py
│
├── pipelines/
│   ├── risk_scoring_pipeline.py          ← SageMaker Pipeline DAG
│   ├── cashflow_prophet_pipeline.py
│   ├── early_warning_pipeline.py
│   └── scenario_simulation_pipeline.py
│
├── evaluation/
│   ├── evaluate_risk.py                  ← F1-weighted, AUC-ROC, calibration curve
│   ├── evaluate_cashflow.py              ← MAPE, sMAPE, coverage (prediction intervals)
│   ├── evaluate_early_warning.py         ← Precision@K, recall@K for 30/60-day horizon
│   ├── bias_detection.py                 ← Clarify runner
│   └── backtesting.py                    ← Walk-forward cross-validation
│
├── lambdas/
│   ├── trigger_retraining.py             ← Receives EventBridge → starts SageMaker Pipeline
│   └── model_approval_notification.py    ← Sends Slack/email on PendingApproval
│
└── notebooks/
    ├── 01_data_exploration.ipynb         ← EDA on synthetic + ICRISAT data
    ├── 02_risk_model_prototype.ipynb     ← XGBoost prototype, SHAP analysis
    ├── 03_cashflow_prophet_prototype.ipynb
    ├── 04_early_warning_prototype.ipynb
    └── 05_bias_analysis.ipynb
```

**Service-side ML hooks** (in existing services):
```
services/risk_assessment/
└── ml/
    └── risk_model.py           ← Thin wrapper: build feature vector → call endpoint → parse response

services/cashflow_service/
└── ml/
    └── cashflow_model.py       ← Prophet endpoint wrapper → MonthlyProjection list

services/early_warning/
└── ml/
    ├── warning_model.py        ← Isolation Forest / LightGBM endpoint wrapper
    └── scenario_model.py       ← Monte Carlo endpoint wrapper → SimulationResult
```

---

## 7. Phased Rollout Roadmap

### Phase 1 — Foundation (Weeks 1–2)
- [ ] Set up S3 bucket structure and IAM roles
- [ ] Deploy SageMaker Feature Groups (risk + cashflow + early warning)
- [ ] Write and run `generate_synthetic_data.py` (50,000 synthetic profiles)
- [ ] Set up Glue jobs for Agmarknet and IMD ingestion
- [ ] Create `ml-pipeline/` directory structure

### Phase 2 — Risk Model MVP (Weeks 3–4)
- [ ] Train XGBoost on synthetic data (`local_train.py`)
- [ ] Validate: F1-weighted > 0.78, no demographic bias
- [ ] Register model in SageMaker Model Registry
- [ ] Deploy serverless endpoint
- [ ] Add `services/risk_assessment/ml/risk_model.py` with flag gate `RISK_ML_ENABLED`
- [ ] Shadow mode: run both heuristic and ML; compare outputs in CloudWatch

### Phase 3 — Cash Flow Prophet (Weeks 5–6)
- [ ] Collect 24 months of Agmarknet + IMD historical data
- [ ] Prototype Prophet with seasonal regressors in `03_cashflow_prophet_prototype.ipynb`
- [ ] Train and validate (MAPE < 15% on held-out 3-month window)
- [ ] Deploy async endpoint
- [ ] Add `services/cashflow_service/ml/cashflow_model.py`

### Phase 4 — Early Warning (Weeks 7–8)
- [ ] Train Isolation Forest on normal-behaviour profiles
- [ ] Define anomaly score threshold at 95th percentile as WARNING, 99th as CRITICAL
- [ ] Accumulate labelled incidents over 60 days; train LightGBM classifier
- [ ] Deploy serverless endpoint
- [ ] Add `services/early_warning/ml/warning_model.py`

### Phase 5 — Scenario Simulation (Weeks 9–10)
- [ ] Fit district-level income distributions from ICRISAT + Agmarknet
- [ ] Build Monte Carlo engine (`monte_carlo.py`, 10,000 runs in < 2 s)
- [ ] Validate against historical drought year outcomes
- [ ] Add `services/early_warning/ml/scenario_model.py`

### Phase 6 — Production Hardening (Weeks 11–12)
- [ ] Enable data capture on all endpoints
- [ ] Create Model Monitor baselines and schedules
- [ ] Wire EventBridge retraining triggers
- [ ] Run full Clarify bias report on all 4 models
- [ ] Enable Bedrock guidance in `services/guidance/`
- [ ] A/B test: 10% traffic to ML endpoints, 90% to heuristic; ramp up over 2 weeks

---

## 8. Model Cards

### Model Card: Risk Scoring v1

| Field | Value |
|---|---|
| **Model name** | `rural-credit-risk-scoring-v1` |
| **Algorithm** | XGBoost 1.7 multi-class classifier |
| **Input** | 18 tabular features (see §2.1) |
| **Output** | Risk category + score (0–1000) + SHAP explanations |
| **Training data** | 50,000 synthetic profiles (ICRISAT-calibrated) |
| **Intended use** | Loan underwriting assistance for rural Indian smallholder farmers |
| **Not intended for** | Urban borrowers, corporate credit, non-agricultural borrowers |
| **Evaluation metrics** | F1-weighted ≥ 0.78, AUC ≥ 0.85, calibration error < 0.05 |
| **Bias constraints** | |DPL| < 0.10 across land holding segments |
| **Refresh cadence** | Weekly (automated), with human approval gate |
| **Limitations** | No history of individual repayment means cold-start profiles use only income/demographic features; confidence degrades for profiles with < 6 months history |

### Model Card: Cash Flow Prediction v1

| Field | Value |
|---|---|
| **Model name** | `rural-credit-cashflow-prophet-v1` |
| **Algorithm** | Facebook Prophet with custom Kharif/Rabi/Zaid seasonality + 3 regressors |
| **Input** | Monthly income/expense history (min 6 points) + external regressor values |
| **Output** | 12-month (mean, p10, p90) monthly inflow/outflow projections |
| **Evaluation metrics** | MAPE < 15%, Coverage (p80 CI) > 80% |
| **Known limitation** | Struggles with structural breaks (new crop adoption); flag when CV > 0.9 |

### Model Card: Early Warning Detection v1

| Field | Value |
|---|---|
| **Model name** | `rural-credit-early-warning-v1` |
| **Algorithm** | Isolation Forest (Phase A) + LightGBM (Phase B) |
| **Input** | 22 features (see §2.3) |
| **Output** | Anomaly score + severity (INFO/WARNING/CRITICAL) + top contributing features |
| **Evaluation metrics** | Recall@30d ≥ 0.75 (catch 75% of defaults 30 days before); Precision ≥ 0.60 |
| **Bias note** | Marginal farmers have higher anomaly scores by definition; severity threshold adjusted per land segment |

### Model Card: Scenario Simulator v1

| Field | Value |
|---|---|
| **Model name** | `rural-credit-scenario-simulation-v1` |
| **Algorithm** | Parametric Monte Carlo with learned correlation matrix |
| **Input** | `ScenarioParameters` (type, weather/market shocks, months affected) |
| **Output** | Income distribution (p5–p95), months-in-deficit, recommended loan restructure |
| **Evaluation** | Back-tested against 2002, 2009, 2014, 2018, 2023 drought years; mean error < 12% on p50 income |
| **Runs** | 10,000 MC draws in < 2 s on `ml.m5.large` |

---

*Document version: 1.0 — generated as part of the rural credit platform ML strategy.*  
*Update this document when: (a) new data sources become available, (b) model versions change, (c) AWS service recommendations are updated.*
