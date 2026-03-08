# AI-Powered Rural Credit Decision Support System

An intelligent credit advisory platform for rural India — helping small farmers, SHG members, tenant farmers, and seasonal migrants make informed borrowing decisions aligned with their volatile livelihood cash-flow cycles.

Built as a hackathon project for **AI for Bharat**.

---

## Architecture

The system follows **Clean Architecture** (Hexagonal / Ports & Adapters) across 8 independently deployable microservices + a React frontend:

```
┌──────────────────────────────────────────────────────────────────┐
│                    React Frontend (:5173)                         │
└──────┬───────┬───────┬───────┬───────┬──────┬──────┬────────────┘
       │       │       │       │       │      │      │
 ┌─────▼──┐ ┌──▼───┐ ┌▼────┐ ┌▼────┐ ┌▼───┐ ┌▼────┐ ┌▼──────────┐
 │Profile │ │ Loan │ │Risk │ │Cash │ │E.W.│ │Guid.│ │AI Advisor │
 │Service │ │Track.│ │Asses│ │Flow │ │    │ │     │ │  (Groq /  │
 │ :8001  │ │:8002 │ │:8003│ │:8004│ │:8005│ │:8006│ │  Bedrock) │
 └────┬───┘ └──┬───┘ └─┬───┘ └─┬───┘ └─┬──┘ └──┬──┘ │  :8008    │
      │        │       │       │       │       │     └─────┬─────┘
 ┌────▼────────▼───────▼───────▼───────▼───────▼───────────▼──┐
 │               Security & Privacy :8007                      │
 │   (Consent · Audit · Data Lineage · Retention)              │
 └─────────────────────┬──────────────────────────────────────┘
                       │
 ┌─────────────────────▼──────────────────────────────────────┐
 │           DynamoDB Local (:8000) · LocalStack (:4566)       │
 └────────────────────────────────────────────────────────────┘
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **Profile** | 8001 | Borrower profiles with income volatility metrics and livelihood cycle tracking |
| **Loan Tracker** | 8002 | Multi-source loan tracking (formal, semi-formal, informal) with debt exposure |
| **Risk Assessment** | 8003 | 8-factor risk scoring engine with composite risk categories |
| **Cash Flow** | 8004 | Seasonal cash flow forecasting with circuit breakers for external data |
| **Early Warning** | 8005 | Alert system with scenario simulation for repayment stress |
| **Guidance** | 8006 | Personalized credit guidance — timing, amounts, terms recommendations |
| **Security** | 8007 | Consent management, audit logging, data lineage, retention policies |
| **AI Advisor** | 8008 | Conversational AI advisor powered by Groq (Llama 3.3 70B) or Amazon Bedrock |
| **Frontend** | 5173 | React + TypeScript dashboard with Tailwind CSS |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | React 18 + TypeScript, Vite, Tailwind CSS, React Query, Recharts |
| **Backend** | Python 3.12+, FastAPI + Pydantic v2 |
| **AI/LLM** | Groq (Llama 3.3 70B) — free tier; Amazon Bedrock (Claude/Nova) as alternative |
| **Database** | DynamoDB (single-table design per service) |
| **Messaging** | SNS → SQS (async domain events) |
| **ML Pipeline** | scikit-learn, custom models for risk/cashflow/early-warning |
| **Lambda adapter** | Mangum |
| **Testing** | pytest + Hypothesis (property-based) + moto (AWS mocking) |
| **Local infra** | Docker Compose (DynamoDB Local + LocalStack) |
| **IaC** | AWS SAM (`template.yaml` per service) |

---

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.12+ | Backend services & ML pipeline |
| **Node.js** | 18+ | Frontend (React) |
| **Docker** | Latest | DynamoDB Local & LocalStack |
| **Git** | Latest | Version control |

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/AiForBharatHack.git
cd AiForBharatHack
```

### 2. Set up Python virtual environment

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
pip install -e services/shared
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure environment variables

```bash
# Copy the example env file
cp .env.example .env
```

**Then edit `.env` and add your API keys:**

| Variable | Required? | How to get it |
|----------|-----------|---------------|
| `GROQ_API_KEY` | **Yes** (for real AI) | Free at [console.groq.com](https://console.groq.com) — sign up, create API key |
| `LLM_PROVIDER` | Yes | Set to `groq` (real AI) or `stub` (hardcoded responses, no key needed) |
| `WEATHER_API_KEY` | Optional | For live weather data in cash-flow forecasts |

> **Without a Groq API key**: Set `LLM_PROVIDER=stub` in `.env`. The AI advisor will return canned responses instead of real AI — everything else works normally.

### 6. Start local infrastructure (Docker)

```bash
docker compose -f infra/docker-compose.yml up -d
```

This starts:
- **DynamoDB Local** on `localhost:8000` (database)
- **LocalStack** on `localhost:4566` (SNS/SQS events)

Tables are auto-created by an init container.

> **No Docker?** Set `STORAGE_BACKEND=memory` in `.env` to skip Docker entirely. Data will be stored in-memory (lost on restart).

### 7. Set up DynamoDB tables (if needed)

```bash
python scripts/setup_local_infra.py
```

### 8. Seed sample data

```bash
python seed_profiles.py
```

This creates 5 sample borrower profiles for testing.

### 9. Start all services

**Option A: VS Code (recommended)**

The project includes VS Code tasks. Open the Command Palette (`Ctrl+Shift+P`) and run:
- `Tasks: Run Task` → **Start Full Stack** — starts all 8 backend services + frontend in parallel

**Option B: Manual (each in a separate terminal)**

```bash
# Backend services
uvicorn services.profile_service.app.main:app   --host 127.0.0.1 --port 8001 --reload
uvicorn services.loan_tracker.app.main:app      --host 127.0.0.1 --port 8002 --reload
uvicorn services.risk_assessment.app.main:app   --host 127.0.0.1 --port 8003 --reload
uvicorn services.cashflow_service.app.main:app  --host 127.0.0.1 --port 8004 --reload
uvicorn services.early_warning.app.main:app     --host 127.0.0.1 --port 8005 --reload
uvicorn services.guidance.app.main:app          --host 127.0.0.1 --port 8006 --reload
uvicorn services.security.app.main:app          --host 127.0.0.1 --port 8007 --reload
uvicorn services.ai_advisor.app.main:app        --host 127.0.0.1 --port 8008 --reload

# Frontend (separate terminal)
cd frontend && npm run dev
```

### 10. Open the app

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **API Docs** (any service): `http://localhost:<port>/docs` (e.g., [http://localhost:8001/docs](http://localhost:8001/docs))

---

## Quick Start (TL;DR)

```bash
# 1. Clone & enter
git clone <repo-url> && cd AiForBharatHack

# 2. Setup
python -m venv .venv && .\.venv\Scripts\activate    # Windows
pip install -r requirements.txt && pip install -e services/shared
cd frontend && npm install && cd ..

# 3. Configure
cp .env.example .env
# Edit .env → add GROQ_API_KEY (get free key from https://console.groq.com)

# 4. Infrastructure
docker compose -f infra/docker-compose.yml up -d
python scripts/setup_local_infra.py
python seed_profiles.py

# 5. Run (VS Code)
# Ctrl+Shift+P → Tasks: Run Task → Start Full Stack
```

---

## AI Advisor

The AI Advisor service (`services/ai_advisor/`, port 8008) provides an intelligent conversational interface named **Krishi Mitra** (कृषि मित्र).

### LLM Provider Options

| Provider | Model | Cost | Setup |
|----------|-------|------|-------|
| **Groq** (default) | Llama 3.3 70B | Free (30 req/min) | Get key from [console.groq.com](https://console.groq.com) |
| **Amazon Bedrock** | Claude / Nova / Titan | AWS pricing | Requires real AWS credentials with Bedrock access |
| **Stub** | N/A (canned responses) | Free | No setup needed — for offline dev/testing |

Configure in `.env`:

```env
LLM_PROVIDER=groq                          # groq | bedrock | stub
GROQ_API_KEY=gsk_your_key_here             # Required for groq
GROQ_MODEL_ID=llama-3.3-70b-versatile      # Default model
```

### Features
- Intent classification (loan advice, risk explanation, scheme recommendations, etc.)
- Context-aware responses using data from all microservices
- Streaming responses (real-time token delivery)
- Multi-language support (Hindi, Telugu, Tamil, Kannada, Marathi, Bengali)
- Conversation history with DynamoDB persistence

---

## Testing

```bash
# All unit tests
pytest

# With coverage
pytest --cov=services

# Single service
pytest services/profile_service/tests/ -v

# E2E tests (requires running services)
pytest -m e2e

# ML pipeline tests
pytest ml-pipeline/tests/ -v
```

---

## Project Structure

```
AiForBharatHack/
├── .env.example                  # Environment template (copy to .env)
├── .vscode/tasks.json            # VS Code tasks for one-click startup
├── infra/docker-compose.yml      # Local DynamoDB + LocalStack
├── pyproject.toml                # Ruff, mypy, pytest configuration
├── requirements.txt              # Root-level Python dependencies
├── seed_profiles.py              # Seed sample borrower data
├── scripts/setup_local_infra.py  # Create DynamoDB tables & SNS topics
│
├── frontend/                     # React + TypeScript frontend
│   ├── src/
│   │   ├── api/                  # API client layer
│   │   ├── components/           # Reusable UI components
│   │   ├── features/             # Feature modules (dashboard, chat, etc.)
│   │   └── types/                # TypeScript type definitions
│   ├── package.json
│   └── vite.config.ts
│
├── services/
│   ├── shared/                   # Shared library (installed as editable package)
│   │   ├── auth/                 # JWT verification middleware
│   │   ├── encryption/           # Field-level encryption (Fernet/KMS)
│   │   ├── events/               # Domain event publishing (SNS)
│   │   ├── localization/         # Multi-language support (6 Indic languages)
│   │   ├── models/               # Base Pydantic models & common types
│   │   ├── observability/        # Structured logging & request tracing
│   │   └── validation/           # Input validation for rural financial contexts
│   │
│   ├── profile_service/          # :8001 — Borrower profile management
│   ├── loan_tracker/             # :8002 — Multi-loan exposure tracking
│   ├── risk_assessment/          # :8003 — 8-factor risk scoring
│   ├── cashflow_service/         # :8004 — Seasonal cash flow forecasting
│   ├── early_warning/            # :8005 — Alert & scenario simulation
│   ├── guidance/                 # :8006 — Credit guidance engine
│   ├── security/                 # :8007 — Privacy & consent management
│   └── ai_advisor/               # :8008 — Conversational AI advisor (Groq/Bedrock)
│
├── ml-pipeline/                  # ML models for risk, cashflow, early warning
│   ├── models/                   # Trained model artefacts
│   ├── data/                     # Feature engineering & synthetic data
│   ├── evaluation/               # Model evaluation & bias detection
│   └── pipelines/                # Training pipelines
│
└── tests/                        # Integration & E2E tests
```

Each service follows the same internal structure:

```
<service>/
├── template.yaml                 # AWS SAM template (Lambda + API Gateway)
├── requirements.txt              # Runtime dependencies
├── app/
│   ├── main.py                   # FastAPI app + dependency wiring
│   ├── config.py                 # Settings from environment
│   ├── api/
│   │   ├── routes.py             # HTTP endpoints
│   │   └── schemas.py            # Request/response DTOs
│   ├── domain/
│   │   ├── models.py             # Entities, value objects, aggregates
│   │   └── services.py           # Business rules & orchestration
│   └── infrastructure/
│       ├── dynamo_repo.py        # DynamoDB repository
│       └── event_publisher.py    # SNS event publishing
└── tests/                        # Unit & integration tests
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Port already in use** | Kill the process: `netstat -ano \| findstr :PORT` → `taskkill /F /PID <pid>` |
| **DynamoDB connection refused** | Make sure Docker is running: `docker compose -f infra/docker-compose.yml up -d` |
| **AI gives canned responses** | Check `.env`: ensure `LLM_PROVIDER=groq` and `GROQ_API_KEY` is set |
| **Module not found** | Run `pip install -e services/shared` and `pip install -r requirements.txt` |
| **Frontend won't start** | Run `cd frontend && npm install` |
| **Tables don't exist** | Run `python scripts/setup_local_infra.py` |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| DynamoDB single-table per service | Cost-effective, serverless-native, scales to zero |
| Clean Architecture | Domain logic is framework-independent and testable in isolation |
| Groq for AI (Llama 3.3 70B) | Free tier, fast inference, no AWS dependency for local dev |
| Property-based testing (Hypothesis) | Catches edge cases in financial calculations |
| Field-level encryption | DPDP Act compliance for sensitive borrower data |
| VS Code tasks for startup | One-click full-stack startup for developers |
| `.env.example` template | Safe onboarding without exposing secrets |

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

## License

Hackathon project — see repository for license details.
