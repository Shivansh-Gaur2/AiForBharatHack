# Implementation Plan: AI-Powered Rural Credit Decision Support System

## Executive Summary

We are building an **AI-powered credit advisory system** for rural India that helps small farmers, SHG members, tenant farmers, and seasonal migrants make informed borrowing decisions. The system provides personalized credit guidance, risk assessment, cash flow prediction, multi-loan tracking, early warnings, and scenario simulation — all aligned to volatile rural livelihood cycles.

This plan lays out a phased, milestone-driven approach to go from zero to a production-ready MVP and beyond.

---

## 1. Technology Stack Decisions

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend Runtime** | Python 3.12+ (FastAPI) | Best-in-class ML ecosystem, async support, type hints |
| **API Gateway** | Kong / AWS API Gateway | Auth, rate limiting, request routing |
| **ML/AI** | scikit-learn, XGBoost, TensorFlow Lite | Risk scoring, cash flow prediction, early warning models |
| **Primary Database** | PostgreSQL 16 | ACID compliance, JSON support for flexible schemas |
| **Cache** | Redis 7 | Session caching, alert queuing, rate limiting |
| **Message Queue** | RabbitMQ / AWS SQS | Async event processing (alerts, notifications) |
| **Object Storage** | MinIO / S3 | Model artifacts, data lineage logs |
| **Frontend** | React Native (mobile) + Next.js (web) | Cross-platform mobile + lightweight web admin |
| **Voice Interface** | Google Speech-to-Text + Bhashini APIs | Indic language support |
| **SMS Gateway** | Twilio / MSG91 | Rural reach where internet is limited |
| **Containerization** | Docker + Kubernetes (EKS/GKE) | Microservice orchestration |
| **CI/CD** | GitHub Actions | Automated testing, model validation, deployment |
| **Monitoring** | Prometheus + Grafana + Sentry | Metrics, alerting, error tracking |
| **Testing** | pytest + Hypothesis (property-based) | Dual testing strategy per design doc |

---

## 2. Architecture Layering (Clean Architecture)

Every service follows **Clean Architecture** (Hexagonal / Ports & Adapters). The `domain/` folder is **NOT DTOs** — it contains pure business logic with zero framework dependencies. Here's how the three layers work:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        api/  (Interface Layer)                      │
│                                                                     │
│  Routes (FastAPI endpoints), Request/Response Schemas (Pydantic)   │
│  These ARE the DTOs — they serialize/deserialize HTTP payloads.    │
│  This layer only translates HTTP ↔ domain calls.                   │
│                                                                     │
│  Depends on: domain/                                                │
├─────────────────────────────────────────────────────────────────────┤
│                      domain/  (Business Logic Layer)                │
│                                                                     │
│  Entities: Rich domain objects with behavior (BorrowerProfile,     │
│            RiskAssessment, CashFlowForecast, Alert)                │
│  Services: Business rules & orchestration (risk_engine.py,         │
│            predictor.py, exposure.py)                               │
│  Interfaces (Ports): Abstract contracts that infrastructure must   │
│            implement (e.g., BorrowerRepository protocol)            │
│  Validators: Domain-specific rules (rural context ranges)          │
│                                                                     │
│  Depends on: NOTHING (pure Python, zero imports from api/ or       │
│              infrastructure/)                                       │
│                                                                     │
│  ⚡ This is testable without any database, HTTP server, or AWS.    │
├─────────────────────────────────────────────────────────────────────┤
│                infrastructure/  (Adapters Layer)                    │
│                                                                     │
│  Repository Implementations: DynamoDB/RDS adapters that implement  │
│            the domain's repository interfaces                       │
│  Event Publishers: SQS/SNS message publishing                      │
│  External API Clients: Weather, market data fetchers               │
│  ML Model Wrappers: Load & invoke trained models                   │
│                                                                     │
│  Depends on: domain/ (implements its interfaces)                   │
│  Depends on: AWS SDKs, boto3, external libraries                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this separation matters:**

| Question | Answer |
|----------|--------|
| Can I test business logic without a DB? | Yes — domain/ has zero infra imports; inject mock repos |
| Can I swap DynamoDB for PostgreSQL? | Yes — only change infrastructure/repository.py; domain/ untouched |
| Where do Pydantic schemas live? | api/schemas.py — they are DTOs for HTTP, NOT domain entities |
| Where does validation live? | Domain validation in domain/validators.py; HTTP validation in api/schemas.py (Pydantic) |
| What about ML models? | ml/ folder sits alongside domain/ — it wraps model inference; domain/ calls it via an interface |

**Data flow through the layers:**

```
HTTP Request
    → api/routes.py (deserialize via Pydantic DTO)
        → domain/services.py (pure business logic)
            → domain/models.py (entity behavior)
            → infrastructure/repository.py (persist/fetch via DynamoDB)
        ← domain returns entity
    ← api/routes.py (serialize entity → Pydantic response DTO)
HTTP Response
```

---

## 3. Project Structure

```
rural-credit-advisor/
├── services/
│   ├── profile-service/              # Requirement 1
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # FastAPI + Mangum (Lambda adapter)
│   │   │   ├── api/                   # INTERFACE LAYER (DTOs live here)
│   │   │   │   ├── routes.py          # REST endpoints
│   │   │   │   └── schemas.py         # Pydantic request/response DTOs
│   │   │   ├── domain/                # BUSINESS LOGIC (pure Python, no imports from api/ or infra/)
│   │   │   │   ├── models.py          # Domain entities (BorrowerProfile, etc.)
│   │   │   │   ├── services.py        # Business rules & orchestration
│   │   │   │   ├── interfaces.py      # Abstract ports (Repository protocols)
│   │   │   │   └── validators.py      # Rural-context data validation rules
│   │   │   ├── infrastructure/        # ADAPTERS (implements domain interfaces)
│   │   │   │   ├── dynamodb_repo.py   # DynamoDB repository implementation
│   │   │   │   └── sqs_events.py      # SQS/SNS event publishing
│   │   │   └── config.py
│   │   ├── tests/
│   │   │   ├── unit/                  # Test domain/ in isolation (mock repos)
│   │   │   ├── property/              # Hypothesis property tests
│   │   │   └── integration/           # Test with real DynamoDB Local
│   │   ├── template.yaml              # SAM template (Lambda + API Gateway)
│   │   └── requirements.txt
│   │
│   ├── risk-service/                  # Requirement 4
│   │   ├── app/
│   │   │   ├── api/                   # DTOs: RiskAssessmentRequest/Response
│   │   │   ├── domain/                # Pure logic: scoring rules, explanations
│   │   │   │   ├── risk_engine.py     # Risk scoring orchestration
│   │   │   │   ├── explainer.py       # Risk score explanation generator
│   │   │   │   └── interfaces.py      # Ports: RiskRepository, ModelPredictor
│   │   │   ├── infrastructure/        # Adapters: DynamoDB, S3 model loading
│   │   │   │   └── dynamodb_repo.py
│   │   │   └── ml/
│   │   │       ├── risk_model.py      # ML model wrapper (implements ModelPredictor)
│   │   │       └── feature_engineering.py
│   │   └── tests/
│   │
│   ├── cashflow-service/              # Requirement 3
│   │   ├── app/
│   │   │   ├── api/                   # DTOs: ForecastRequest/Response
│   │   │   ├── domain/                # Pure logic: prediction, alignment
│   │   │   │   ├── predictor.py       # Cash flow prediction logic
│   │   │   │   ├── seasonal.py        # Seasonal pattern analysis
│   │   │   │   ├── alignment.py       # Credit timing alignment
│   │   │   │   └── interfaces.py      # Ports: WeatherDataPort, MarketDataPort
│   │   │   ├── infrastructure/        # Adapters: API clients, DynamoDB
│   │   │   │   ├── weather_client.py  # IMD/OpenWeather API adapter
│   │   │   │   └── market_client.py   # Agmarknet API adapter
│   │   │   └── ml/
│   │   │       └── cashflow_model.py
│   │   └── tests/
│   │
│   ├── loan-tracker-service/          # Requirement 2
│   │   ├── app/
│   │   │   ├── api/                   # DTOs: LoanRequest, ExposureResponse
│   │   │   ├── domain/                # Pure logic: aggregation, exposure calc
│   │   │   │   ├── tracker.py         # Multi-loan aggregation
│   │   │   │   ├── exposure.py        # Debt exposure calculator
│   │   │   │   └── interfaces.py      # Ports: LoanRepository
│   │   │   ├── infrastructure/        # Adapters: DynamoDB, SQS events
│   │   │   │   └── dynamodb_repo.py
│   │   └── tests/
│   │
│   ├── early-warning-service/         # Requirement 5
│   │   ├── app/
│   │   │   ├── api/                   # DTOs: AlertResponse, EscalationRequest
│   │   │   ├── domain/                # Pure logic: monitoring rules, escalation
│   │   │   │   ├── monitor.py         # Repayment risk monitoring
│   │   │   │   ├── alerter.py         # Alert generation & escalation
│   │   │   │   ├── recommender.py     # Actionable recommendations
│   │   │   │   └── interfaces.py      # Ports: AlertRepository, NotificationPort
│   │   │   ├── infrastructure/        # Adapters: DynamoDB, SNS SMS dispatch
│   │   │   │   ├── dynamodb_repo.py
│   │   │   │   └── sns_notification.py # SNS SMS/Push notification dispatch
│   │   │   └── ml/
│   │   │       └── warning_model.py
│   │   └── tests/
│   │
│   ├── scenario-service/              # Requirement 6
│   │   ├── app/
│   │   │   ├── api/                   # DTOs: ScenarioRequest, SimulationResult
│   │   │   ├── domain/                # Pure logic: simulation rules
│   │   │   │   ├── simulator.py       # Scenario simulation engine
│   │   │   │   ├── weather_impact.py  # Weather disruption modeling
│   │   │   │   ├── market_impact.py   # Market volatility modeling
│   │   │   │   └── interfaces.py      # Ports: SimulationRepository
│   │   │   ├── infrastructure/        # Adapters: DynamoDB, S3
│   │   │   └── ml/
│   │   │       └── scenario_model.py
│   │   └── tests/
│   │
│   ├── guidance-service/              # Requirement 7
│   │   ├── app/
│   │   │   ├── api/                   # DTOs: GuidanceRequest, GuidanceResponse
│   │   │   ├── domain/                # Pure logic: recommendation rules
│   │   │   │   ├── advisor.py         # Credit guidance generation
│   │   │   │   ├── timing.py          # Loan timing optimizer
│   │   │   │   ├── explainer.py       # Reasoning in simple language
│   │   │   │   └── interfaces.py      # Ports: GuidanceRepository, ServicePorts
│   │   │   └── infrastructure/        # Adapters: DynamoDB, Lambda invoke
│   │   │       └── localization.py    # Multi-language support (S3-backed)
│   │   └── tests/
│   │
│   └── shared/                        # Cross-cutting concerns (Lambda Layer)
│       ├── auth/                      # Cognito JWT validation, RBAC (Req 9)
│       ├── encryption/                # KMS encryption utilities
│       ├── events/                    # SQS/SNS event bus abstractions
│       ├── localization/              # i18n framework (Requirement 10)
│       ├── offline/                   # Offline-first sync engine
│       ├── models/                    # Shared domain types (value objects)
│       └── validation/               # Common validators
│
├── ml-pipeline/                       # ML training & evaluation
│   ├── data/
│   │   ├── preprocessing/
│   │   └── feature_store/
│   ├── models/
│   │   ├── risk_scoring/
│   │   ├── cashflow_prediction/
│   │   ├── early_warning/
│   │   └── scenario_simulation/
│   ├── evaluation/
│   │   ├── bias_detection.py
│   │   ├── backtesting.py
│   │   └── cross_validation.py
│   └── mlflow_config.py
│
├── mobile-app/                        # React Native app
│   ├── src/
│   │   ├── screens/
│   │   ├── components/
│   │   ├── services/
│   │   ├── offline/                   # Offline storage & sync
│   │   └── voice/                     # Voice interaction module
│   └── package.json
│
├── infra/                             # Infrastructure-as-Code
│   ├── docker-compose.yml             # Local dev (DynamoDB Local, LocalStack)
│   ├── samconfig.toml                 # AWS SAM deployment config
│   ├── template.yaml                  # SAM root template (all Lambdas)
│   └── terraform/                     # VPC, Cognito, DynamoDB tables, IAM
│
├── docs/
│   ├── api/                           # OpenAPI specs
│   └── architecture/
│
└── .github/
    └── workflows/                     # CI/CD pipelines
```

---

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---------|-------|-----|
| **Repository** | All services (`infrastructure/dynamodb_repo.py`) | Decouple domain logic from DynamoDB; domain/ stays pure |
| **Ports & Adapters** | `domain/interfaces.py` → `infrastructure/*` | Domain defines abstract ports; infra provides concrete adapters |
| **Domain Events** | Profile → Risk, Loan → EarlyWarning (via SQS/SNS) | Loose coupling between Lambda functions via async events |
| **Strategy** | Risk engine, Scenario simulator | Swap ML models or algorithms without changing orchestration |
| **Factory** | Alert generation, Guidance creation | Complex object construction with varying parameters |
| **Circuit Breaker** | External API calls (weather, market) | Graceful degradation when external services fail |
| **CQRS** | Profile reads vs. writes; Risk queries vs. scoring | Optimize read-heavy paths independently |
| **Saga** | Multi-service credit guidance workflow | Coordinate distributed transactions across Lambda functions |
| **Adapter** | External data integrations | Normalize diverse data sources (weather, market, economic) |
| **Observer** | Early Warning System (SQS fan-out) | React to risk factor changes across multiple services |
| **Decorator** | Localization, KMS encryption wrappers | Add cross-cutting concerns without modifying core logic |

---

## 5. Phased Implementation Plan

### Phase 1: Foundation (Weeks 1–3)
**Goal:** Skeleton infrastructure, shared libraries, and the Profile Service.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W1** | Project scaffolding, Docker Compose (DynamoDB Local, LocalStack for SQS/SNS), shared Lambda Layer (Cognito auth, KMS encryption, validation, SQS event bus), GitHub Actions CI pipeline | Running local dev environment |
| **W2** | Profile Service: domain entities, Pydantic DTOs, CRUD Lambda endpoints, income volatility calculation, rural-context domain validators, DynamoDB repository | Profile CRUD API with tests |
| **W3** | Data validation framework (Req 1.4), historical data preservation logic (Req 1.5), seasonal pattern ingestion, integration tests with DynamoDB Local, API docs | Profile Service fully functional |

**Key Properties Validated:** Property 1 (Profile Completeness), Property 2 (Data Validation), Property 3 (Historical Preservation)

---

### Phase 2: Loan Tracking & Risk Engine (Weeks 4–6)
**Goal:** Multi-Loan Tracker and Risk Assessment Service with initial ML model.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W4** | Loan Tracker Service: domain models, loan CRUD, exposure aggregation (formal + semi-formal + informal), debt-to-income calculation | Loan tracking API |
| **W5** | Risk Assessment Service: feature engineering pipeline, initial risk scoring model (XGBoost on synthetic data), risk explanation generator | Risk scoring API with model v0.1 |
| **W6** | Integration: Profile ↔ Risk ↔ Loan Tracker event wiring, real-time exposure updates on loan status changes, property tests | Services communicating end-to-end |

**Key Properties Validated:** Property 4 (Multi-Loan Aggregation), Property 5 (Real-time Updates), Property 8 (Risk Scoring)

---

### Phase 3: Cash Flow & External Data (Weeks 7–9)
**Goal:** Cash Flow Service with seasonal predictions and external data integration.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W7** | Cash Flow Service: seasonal pattern modeling, historical cash flow analysis, repayment capacity calculator | Cash flow prediction API |
| **W8** | External data adapters: weather API (IMD/OpenWeather), market price feeds (agmarknet), economic indicators; Circuit Breaker wrappers | External data integration |
| **W9** | Cash flow ML model training, credit timing alignment engine, emergency reserve calculations, data quality validation (Req 8) | Cash flow predictions with external data |

**Key Properties Validated:** Property 6 (Cash Flow Integration), Property 7 (Timing Alignment), Property 13 (Data Quality)

---

### Phase 4: Early Warning & Scenarios (Weeks 10–12)
**Goal:** Early Warning System and Scenario Simulation Engine.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W10** | Early Warning Service: income deviation monitoring, repayment stress detection, alert generation, severity escalation logic | Alert generation API |
| **W11** | Notification infrastructure (SMS, push), stakeholder notification routing, actionable recommendation engine | End-to-end alert pipeline |
| **W12** | Scenario Simulation Engine: weather impact modeling, market volatility simulation, repayment capacity impact analysis, risk-adjusted recommendations | Scenario simulation API |

**Key Properties Validated:** Property 10 (Alert Generation), Property 11 (Scenario Simulation)

---

### Phase 5: Guidance & Intelligence (Weeks 13–14)
**Goal:** Guidance Service that orchestrates all components into personalized recommendations.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W13** | Guidance Service: aggregation from all services (Profile, Risk, CashFlow, Scenarios), optimal timing calculation, amount recommendation engine | Guidance generation API |
| **W14** | Recommendation explanation in simple language, Saga orchestration for multi-service guidance workflow, end-to-end integration tests | Complete backend intelligence |

**Key Properties Validated:** Property 12 (Personalized Guidance), Property 9 (Dynamic Risk Updates)

---

### Phase 6: Security, Privacy & Localization (Weeks 15–16)
**Goal:** Production-grade security, privacy compliance, and multi-language support.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W15** | Encryption at rest (AES-256) and in transit (TLS 1.3), RBAC implementation, consent management system, data lineage tracking, retention/deletion policies | Security layer complete |
| **W16** | Multi-language support (Hindi, Tamil, Telugu, Kannada, Marathi + others), culturally appropriate explanations, voice interface integration (Bhashini API) | Localization framework |

**Key Properties Validated:** Property 14 (Security & Privacy), Property 15 (Accessibility)

---

### Phase 7: Mobile App & Offline (Weeks 17–19)
**Goal:** React Native app with offline-first architecture.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W17** | Mobile app scaffolding, authentication flow, profile management screens, loan tracking UI | Core mobile app |
| **W18** | Offline-first architecture (SQLite local store + background sync), low-bandwidth optimization, basic device compatibility | Offline-capable app |
| **W19** | Voice interaction module, guidance display screens, alert notifications, scenario simulation UI, SMS fallback flow | Feature-complete mobile app |

---

### Phase 8: ML Refinement & Production Readiness (Weeks 20–22)
**Goal:** Model validation, performance tuning, and deployment infrastructure.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **W20** | ML model refinement with real/representative data, bias detection across demographics, cross-validation, backtesting | Validated ML models |
| **W21** | Performance testing (load, scalability), DynamoDB capacity optimization, DAX caching strategy, Lambda cold start optimization | Performance benchmarks met |
| **W22** | Terraform IaC for all AWS resources, CloudWatch dashboards & alarms, X-Ray tracing, production runbooks, SAM deployment pipelines | Production-ready infrastructure |

---

## 6. Service Communication Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   SYNCHRONOUS (API Gateway → Lambda)               │
│                                                                     │
│  Client → API Gateway → Lambda (for user-facing request/response) │
│  Lambda → Lambda (for real-time data fetching via SDK invoke,     │
│           e.g., Guidance Lambda → Profile Lambda.getProfile())     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              ASYNCHRONOUS (SNS Topics → SQS Queues)                │
│                                                                     │
│  SNS: profile-events                                               │
│    profile.updated       → SQS → Risk Lambda (re-score)           │
│                                                                     │
│  SNS: loan-events                                                  │
│    loan.status_changed   → SQS → Loan Tracker Lambda (recalc)     │
│                          → SQS → Early Warning Lambda (stress)    │
│                                                                     │
│  SNS: risk-events                                                  │
│    risk.score_changed    → SQS → Early Warning Lambda (alerts)    │
│                          → SQS → Guidance Lambda (refresh recs)   │
│                                                                     │
│  SNS: cashflow-events                                              │
│    cashflow.deviation    → SQS → Early Warning Lambda (alert)     │
│                                                                     │
│  SNS: alert-events                                                 │
│    alert.generated       → SQS → SNS SMS (borrower notification)  │
│                          → SQS → SES Email (stakeholder notify)   │
│                                                                     │
│  SNS: external-data-events                                         │
│    data.updated          → SQS → CashFlow Lambda (refresh)        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Database Schema Strategy

Each service owns its own DynamoDB table(s) (Table-per-Service pattern). DynamoDB's single-table design is used within each service for efficient access patterns:

| Service | Tables | Key Indices |
|---------|--------|-------------|
| **Profile** | `borrower_profiles`, `income_records`, `expense_records`, `seasonal_patterns`, `profile_history` | `borrower_id`, `occupation_type`, `region` |
| **Loan Tracker** | `loans`, `loan_sources`, `repayment_schedules`, `exposure_snapshots` | `borrower_id`, `source_type`, `status` |
| **Risk** | `risk_assessments`, `risk_factors`, `risk_history` | `borrower_id`, `assessment_date`, `risk_category` |
| **Cash Flow** | `cashflow_forecasts`, `seasonal_adjustments`, `external_data_cache` | `borrower_id`, `forecast_date`, `data_source` |
| **Early Warning** | `alerts`, `alert_history`, `recommendations` | `borrower_id`, `severity`, `status`, `created_at` |
| **Guidance** | `credit_guidance`, `guidance_history` | `borrower_id`, `guidance_date` |
| **Auth** | `users`, `roles`, `permissions`, `consent_records`, `audit_log` | `user_id`, `role`, `consent_type` |

---

## 8. API Design Conventions

- **Base URL:** `/api/v1/{service}/`
- **Auth:** Bearer JWT tokens with RBAC claims
- **Pagination:** Cursor-based for list endpoints
- **Error format:** RFC 7807 Problem Details
- **Versioning:** URL path versioning (`/v1/`, `/v2/`)
- **Idempotency:** Idempotency keys for all write operations
- **Rate Limiting:** Per-user, per-service tier limits

**Example endpoint design:**

```
POST   /api/v1/profiles                    → Create profile
GET    /api/v1/profiles/{id}               → Get profile
PATCH  /api/v1/profiles/{id}               → Update profile
GET    /api/v1/profiles/{id}/volatility    → Get income volatility

POST   /api/v1/loans                       → Track new loan
GET    /api/v1/loans/exposure/{profileId}  → Get total exposure
PATCH  /api/v1/loans/{id}/status           → Update loan status

GET    /api/v1/risk/{profileId}            → Get risk assessment
GET    /api/v1/risk/{profileId}/explain    → Get risk explanation

GET    /api/v1/cashflow/{profileId}/forecast?horizon=6m    → Cash flow forecast
GET    /api/v1/cashflow/{profileId}/timing?amount=50000    → Timing recommendation

GET    /api/v1/alerts/{profileId}          → Get active alerts
POST   /api/v1/alerts/{id}/acknowledge     → Acknowledge alert

POST   /api/v1/scenarios/simulate          → Run scenario simulation
GET    /api/v1/scenarios/{id}/results      → Get simulation results

GET    /api/v1/guidance/{profileId}        → Get credit guidance
POST   /api/v1/guidance/recommend          → Generate new recommendation
```

---

## 9. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Poor ML model accuracy** (sparse rural data) | High | Start with rule-based heuristics; layer ML gradually; use synthetic data augmentation |
| **External API unreliability** (weather/market) | Medium | Circuit breakers, DynamoDB caching with TTL, fallback to regional averages |
| **Low connectivity in rural areas** | High | Offline-first mobile architecture, SNS SMS fallback, progressive data sync |
| **Data privacy breach** | Critical | KMS encryption at rest, TLS in transit, Cognito RBAC, consent management |
| **Model bias against demographics** | High | Bias detection in ML pipeline, fairness metrics in CloudWatch, diverse training data |
| **Lambda cold starts** | Medium | Provisioned concurrency for critical paths, Lambda SnapStart, keep functions small |
| **AWS cost overrun** | Medium | CloudWatch billing alarms, DynamoDB on-demand pricing, Lambda free tier monitoring |
| **Service coupling creep** | Medium | Strict SNS/SQS event-driven communication, API contracts, contract testing |
| **Scope creep** | Medium | Phase-gated delivery, clear acceptance criteria per requirement |

---

## 10. Definition of Done (per Feature)

- [ ] All acceptance criteria from requirements.md are met
- [ ] Corresponding design properties are validated via property-based tests
- [ ] Unit test coverage ≥ 80%
- [ ] Integration tests pass
- [ ] API documentation (OpenAPI spec) updated
- [ ] Error handling follows defined error categories
- [ ] Localization strings added for supported languages
- [ ] Security review completed (for data-handling features)
- [ ] Performance benchmarks met (API response < 500ms p95)
- [ ] Code reviewed and merged to main

---

## 11. Immediate Next Steps

1. **Initialize the monorepo** with the project structure above
2. **Set up Docker Compose** with DynamoDB Local + LocalStack (for SQS/SNS emulation)
3. **Build the shared Lambda Layer** (Cognito auth, KMS encryption, validation, SQS event bus)
4. **Implement Profile Service** as the first vertical slice (domain → api → infrastructure)
5. **Write property-based tests** for Property 1, 2, and 3
6. **Set up GitHub Actions CI** with linting, type checking, and automated tests
7. **Create SAM template** for deploying Profile Service Lambda + API Gateway

---

*This plan is designed to be iterative — each phase produces a working increment that can be demonstrated and validated against the requirements before proceeding.*
