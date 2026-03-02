# AI-Powered Rural Credit Decision Support System

An intelligent credit advisory platform for rural India — helping small farmers, SHG members, tenant farmers, and seasonal migrants make informed borrowing decisions aligned with their volatile livelihood cash-flow cycles.

Built as a hackathon project for **AI for Bharat**.

---

## Architecture

The system follows **Clean Architecture** (Hexagonal / Ports & Adapters) across 7 independently deployable microservices:

```
┌─────────────────────────────────────────────────────────────┐
│                       API Gateway                           │
└──────────┬───────┬───────┬───────┬───────┬──────┬──────────┘
           │       │       │       │       │      │
     ┌─────▼──┐ ┌──▼───┐ ┌▼────┐ ┌▼────┐ ┌▼───┐ ┌▼────────┐
     │Profile │ │ Loan │ │Risk │ │Cash │ │E.W.│ │Guidance │
     │Service │ │Track.│ │Asses│ │Flow │ │    │ │& Intel. │
     │ :8001  │ │:8081 │ │:8082│ │:8083│ │:8084│ │ :8085   │
     └────┬───┘ └──┬───┘ └─┬───┘ └─┬───┘ └─┬──┘ └──┬──────┘
          │        │       │       │       │       │
     ┌────▼────────▼───────▼───────▼───────▼───────▼──┐
     │               Security & Privacy :8086          │
     │   (Consent · Audit · Data Lineage · Retention)  │
     └─────────────────────┬──────────────────────────┘
                           │
     ┌─────────────────────▼──────────────────────────┐
     │           DynamoDB (single-table design)        │
     │              SNS / SQS (events)                 │
     └────────────────────────────────────────────────┘
```

Each service follows a strict three-layer structure:

| Layer | Path | Responsibility |
|-------|------|----------------|
| **Interface** | `app/api/` | FastAPI routes, Pydantic request/response schemas |
| **Domain** | `app/domain/` | Pure business logic — entities, value objects, domain services |
| **Infrastructure** | `app/infrastructure/` | DynamoDB repositories, SNS publishers, HTTP clients |

### Services

| Service | Port | Description |
|---------|------|-------------|
| **Profile** | 8001 | Borrower profiles with income volatility metrics and livelihood cycle tracking |
| **Loan Tracker** | 8081 | Multi-source loan tracking (formal, semi-formal, informal) with debt exposure |
| **Risk Assessment** | 8082 | 8-factor risk scoring engine with composite risk categories |
| **Cash Flow** | 8083 | Seasonal cash flow forecasting with circuit breakers for external data |
| **Early Warning** | 8084 | Alert system with scenario simulation for repayment stress |
| **Guidance** | 8085 | Personalized credit guidance — timing, amounts, terms recommendations |
| **Security** | 8086 | Consent management, audit logging, data lineage, retention policies |

### Shared Library (`services/shared/`)

Cross-cutting concerns used by all services:

- **`auth/`** — Cognito JWT verification middleware
- **`encryption/`** — Field-level Fernet/KMS encryption
- **`events/`** — Domain event publishing via SNS (sync & async)
- **`localization/`** — Multi-language support (6 Indic languages)
- **`models/`** — Base Pydantic models and common types
- **`validation/`** — Input validation rules for rural financial contexts
- **`observability/`** — Structured JSON logging, request tracing, error middleware

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Framework | FastAPI + Pydantic v2 |
| Database | DynamoDB (single-table design per service) |
| Messaging | SNS → SQS (async domain events) |
| Lambda adapter | Mangum |
| Testing | pytest + Hypothesis (property-based) + moto (AWS mocking) |
| Linting | Ruff |
| Type checking | mypy |
| CI | GitHub Actions |
| IaC | AWS SAM (`template.yaml` per service) |
| Local infra | Docker Compose (DynamoDB Local + LocalStack) |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose

### 1. Clone and set up the virtualenv

```bash
git clone <repo-url> && cd AiForBharatHack
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
pip install -e services/shared
```

### 3. Start local infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d
```

This starts:
- **DynamoDB Local** on `localhost:8000`
- **LocalStack** (SNS/SQS) on `localhost:4566`

DynamoDB tables are auto-created via an init container.

### 4. Configure environment

```bash
cp .env.example .env   # or create .env with:
```

Key variables (see `.env` for all):

```env
DYNAMODB_ENDPOINT_URL=http://localhost:8000
SNS_ENDPOINT_URL=http://localhost:4566
SKIP_AUTH=true
ENVIRONMENT=local
```

### 5. Start services

```bash
# Start all services (each in a separate terminal, or use background mode):
uvicorn services.profile_service.app.main:app   --port 8001 --reload
uvicorn services.loan_tracker.app.main:app      --port 8081 --reload
uvicorn services.risk_assessment.app.main:app   --port 8082 --reload
uvicorn services.cashflow_service.app.main:app  --port 8083 --reload
uvicorn services.early_warning.app.main:app     --port 8084 --reload
uvicorn services.guidance.app.main:app          --port 8085 --reload
uvicorn services.security.app.main:app          --port 8086 --reload
```

Each service exposes interactive API docs at `http://localhost:<port>/docs`.

---

## Testing

### Unit tests (all services)

```bash
pytest                          # uses pyproject.toml config
pytest --cov=services           # with coverage
```

### Single service

```bash
pytest services/profile_service/tests/ -v
```

### E2E tests (requires running services)

```bash
pytest -m e2e                   # run all e2e tests
python tests/e2e/test_api.py    # standalone e2e script
```

### Property-based tests

```bash
pytest services/profile_service/tests/property/ -v
```

---

## Project Structure

```
AiForBharatHack/
├── .github/workflows/ci.yml     # CI pipeline (lint → test matrix → SAM build)
├── infra/docker-compose.yml     # Local DynamoDB + LocalStack
├── pyproject.toml               # Ruff, mypy, pytest configuration
├── requirements.txt             # Root-level dependencies
├── design.md                    # System design document
├── requirements.md              # Functional requirements
├── implementation-plan.md       # Phased implementation plan
│
├── services/
│   ├── shared/                  # Shared library (installed as editable package)
│   │   ├── auth/                # JWT verification
│   │   ├── encryption/          # Field-level encryption
│   │   ├── events/              # Domain event publishing (SNS)
│   │   ├── localization/        # i18n (6 languages)
│   │   ├── models/              # Base Pydantic models
│   │   ├── observability/       # Structured logging & middleware
│   │   └── validation/          # Input validation
│   │
│   ├── profile_service/         # Borrower profile management
│   ├── loan_tracker/            # Multi-loan exposure tracking
│   ├── risk_assessment/         # 8-factor risk scoring
│   ├── cashflow_service/        # Seasonal cash flow forecasting
│   ├── early_warning/           # Alert & scenario simulation
│   ├── guidance/                # Credit guidance engine
│   └── security/                # Privacy & consent management
│
└── tests/e2e/                   # Standalone end-to-end API scripts
```

Each service follows the same internal structure:

```
<service>/
├── template.yaml                # AWS SAM template
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Dev/test dependencies
├── app/
│   ├── main.py                  # FastAPI app factory + Mangum handler
│   ├── config.py                # Pydantic settings (env-driven)
│   ├── api/
│   │   ├── routes.py            # HTTP endpoints
│   │   └── schemas.py           # Request/response DTOs
│   ├── domain/
│   │   ├── models.py            # Entities, value objects, aggregates
│   │   └── services.py          # Business rules & orchestration
│   └── infrastructure/
│       ├── dynamo_repo.py       # DynamoDB repository
│       └── sqs_events.py        # Event publisher factory
└── tests/
    ├── test_models.py           # Domain model unit tests
    ├── test_services.py         # Service layer tests
    ├── test_validators.py       # Validation tests
    └── test_e2e.py              # E2E tests (marked, excluded by default)
```

---

## CI Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main`/`develop`:

1. **Lint & Type-check** — Ruff lint + format check, mypy for all services
2. **Test matrix** — Each service tested in parallel with DynamoDB Local + LocalStack
3. **SAM Build** — Validates and builds each service's Lambda deployment package

---

## Deployment

Each service includes a `template.yaml` for AWS SAM:

```bash
cd services/<service_name>
sam build
sam deploy --guided
```

Services deploy as **AWS Lambda** functions behind API Gateway, with DynamoDB tables and SNS topics provisioned via CloudFormation.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| DynamoDB single-table per service | Cost-effective, serverless-native, scales to zero |
| Clean Architecture | Domain logic is framework-independent and testable in isolation |
| Property-based testing (Hypothesis) | Catches edge cases in financial calculations |
| Async event publishing | Fire-and-forget domain events decouple services |
| Field-level encryption | DPDP Act compliance for sensitive borrower data |
| RFC 7807 error responses | Standard problem detail format for APIs |
| Structured JSON logging | CloudWatch/Datadog-compatible, request-scoped correlation IDs |
| E2E tests as separate marker | Fast CI (unit-only by default), full validation on demand |

---

## License

Hackathon project — see repository for license details.
