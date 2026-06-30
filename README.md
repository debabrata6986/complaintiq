# ComplaintIQ v3.0 — Autonomous Self-Healing AI Complaint Resolution

## Overview

ComplaintIQ v3.0 adds a full **Autonomous Self-Healing** layer on top of the v2.0 research-grade NLP stack. The system now executes actions, recovers from failures, verifies outcomes, escalates intelligently, notifies stakeholders, and records a complete audit trail — all without human intervention for eligible complaints.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                          │
│  Dashboard │ ComplaintAnalysis │ KnowledgeBase │ Admin       │
└──────────────────────┬───────────────────────────────────────┘
                       │ REST API (JWT)
┌──────────────────────▼───────────────────────────────────────┐
│                 FastAPI Backend v3.0                         │
│  /api/complaints  /api/knowledge  /api/analytics             │
│  /api/self-healing  (NEW)                                    │
└──────┬──────────────┬──────────────────────────────┬─────────┘
       │              │                              │
┌──────▼──────┐ ┌─────▼──────────┐  ┌───────────────▼───────┐
│  MongoDB    │ │  LangGraph     │  │  ChromaDB             │
│             │ │  13-Agent      │  │  all-MiniLM-L6-v2     │
│  complaints │ │  Analysis      │  └───────────────────────┘
│  executions │ │  Pipeline      │
│  audit_trail│ └─────┬──────────┘
│  notifs     │       │ background task
│  escalations│ ┌─────▼──────────────────────────────────────┐
│  learning   │ │  Self-Healing Engine (self_healing.py)     │
│  signals    │ │                                            │
└─────────────┘ │  ActionExecutionAgent (15 handlers)        │
                │  WorkflowVerificationAgent (4-check suite) │
                │  RetryEngine (exponential backoff ×3)      │
                │  RollbackEngine (15 action rollbacks)      │
                │  AutoEscalationAgent (L1→L2→L3→EXEC→LEGAL)│
                │  NotificationAgent (email/sms/push/dash)   │
                │  AuditTrail (every step recorded)          │
                │  IncidentTimeline (ordered event log)      │
                │  LearningSignals (adaptive data pipeline)  │
                └────────────────────────────────────────────┘
```

---

## New Modules (v3.0)

| File | Features | Description |
|------|---------|-------------|
| `backend/self_healing.py` | F1-F8, F11 | Main orchestrator — full autonomous pipeline |
| `backend/action_executor.py` | F1, F12, F16 | 15 mock action handlers with clean API interfaces |
| `backend/execution_models.py` | F7-F10 | Pydantic models: AuditEntry, ExecutionRecord, IncidentTimelineEvent, state machine |
| `backend/simulator.py` | F12 | 8 predefined complaint scenarios for developer testing |
| `backend/routers/self_healing.py` | F13-F14 | 15 REST endpoints for execution, audit, metrics, simulator |

Config extended: `ExecutionConfig` added to `config.py` (F15)

---

## 16-Feature Implementation Summary

| Feature | Status | Module |
|---------|--------|--------|
| F1 Action Execution Agent | Complete | `action_executor.py`, `self_healing.py` |
| F2 Workflow Verification Agent | Complete | `self_healing.py::_verify_action()` |
| F3 Automatic Retry (exp. backoff) | Complete | `self_healing.py` retry loop |
| F4 Rollback Engine | Complete | `self_healing.py::_perform_rollback()` |
| F5 Escalation Agent | Complete | `self_healing.py::_auto_escalate()` |
| F6 Notification Agent (4 channels) | Complete | `self_healing.py::_notify_all()` |
| F7 Execution Audit Trail | Complete | `execution_models.AuditEntry` |
| F8 Incident Timeline | Complete | `self_healing.py::_build_timeline()` |
| F9 State Machine | Complete | `execution_models._VALID_TRANSITIONS` |
| F10 Execution History | Complete | `execution_models.ExecutionRecord` |
| F11 Adaptive Learning | Complete | `self_healing.py::_record_learning_signal()` |
| F12 Workflow Simulator | Complete | `simulator.py` (8 scenarios) |
| F13 Dashboard APIs | Complete | `routers/self_healing.py` (15 endpoints) |
| F14 Metrics | Complete | `GET /api/self-healing/metrics` |
| F15 Configuration | Complete | `config.ExecutionConfig` |
| F16 Security | Complete | Mock isolation, no sensitive logging, auth on all endpoints |

---

## Self-Healing Pipeline Flow

```
AI Analysis (13 agents) completes
        │
        ▼
[SelfHealingOrchestrator] — background task, never blocks the HTTP response
        │
        ├── Pre-execution checks:
        │     escalation_required? → auto-escalate immediately
        │     risk_score ≥ 70?     → escalate
        │     confidence < 0.65?   → escalate
        │
        ├── [ActionExecutionAgent] — dispatch to 1 of 15 handlers
        │
        ├── [WorkflowVerificationAgent] — 4-check verification suite
        │     ✓ action_status = COMPLETED
        │     ✓ no error
        │     ✓ details populated
        │     ✓ action-type-specific field (reference_id, ticket_id, etc.)
        │
        ├── [RetryEngine] — if FAILED or TIMEOUT
        │     attempt 1: delay 2.0s
        │     attempt 2: delay 4.0s
        │     attempt 3: delay 8.0s
        │
        ├── [RollbackEngine] — if retries exhausted
        │
        ├── [AutoEscalationAgent] — if warranted
        │     L1 → Support
        │     L2 → Senior Support
        │     L3 → Management
        │     EXECUTIVE → Executive Team
        │     LEGAL → Legal & Compliance
        │
        ├── [NotificationAgent]
        │     Customer → email
        │     Support  → dashboard
        │     Manager  → dashboard (on failure/risk/escalation)
        │
        ├── [AuditTrail] — every step persisted to audit_trail collection
        │
        ├── [IncidentTimeline] — ordered event log persisted to execution
        │
        └── [LearningSignals] — outcome stored in learning_signals collection
```

---

## New API Endpoints (v3.0)

All under `/api/self-healing`:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/executions/{id}` | any | Full execution record |
| GET | `/executions` | staff | List executions (filter: complaint_id, status) |
| GET | `/complaints/{id}/execution` | owner/staff | Latest execution for complaint |
| GET | `/complaints/{id}/timeline` | owner/staff | Ordered incident timeline |
| GET | `/complaints/{id}/state` | owner/staff | Current workflow state |
| GET | `/complaints/{id}/audit` | staff | Full audit trail for one complaint |
| POST | `/complaints/{id}/execute` | staff | Manually trigger execution |
| GET | `/audit` | admin/manager | Global audit log |
| GET | `/escalations` | admin/manager | Auto-escalation records |
| GET | `/notifications` | staff | Notification history |
| GET | `/metrics` | admin/manager | Feature 14 metrics |
| GET | `/metrics/adaptive-learning` | admin/manager | Feature 11 learning stats |
| GET | `/state-machine` | any | State machine definition |
| GET | `/simulator/scenarios` | any | List 8 simulator scenarios |
| POST | `/simulator/run` | staff | Run scenario through full pipeline |

---

## MongoDB Collections (v3.0 additions)

| Collection | Contents |
|------------|---------|
| `executions` | Full ExecutionRecord per complaint |
| `audit_trail` | AuditEntry per workflow step |
| `notifications` | NotificationRecord per sent notification |
| `auto_escalations` | AutoEscalationRecord per escalation |
| `learning_signals` | Outcome signals for adaptive analytics |

---

## Configuration (v3.0 additions)

| Variable | Default | Description |
|----------|---------|-------------|
| `EXEC_MAX_RETRIES` | `3` | Max retry attempts |
| `EXEC_RETRY_DELAY` | `2.0` | Base retry delay (seconds) |
| `EXEC_BACKOFF_FACTOR` | `2.0` | Exponential multiplier |
| `EXEC_VERIFY_TIMEOUT` | `30.0` | Verification timeout (seconds) |
| `EXEC_ESCALATION_RISK` | `70` | Risk score threshold for auto-escalation |
| `EXEC_ESCALATION_CONF` | `0.65` | Confidence threshold for escalation |
| `AUTO_EXECUTE` | `true` | Auto-run after analysis completes |
| `SIMULATOR_MODE` | `true` | Use mock APIs (always true in dev) |
| `NOTIFY_CUSTOMER` | `true` | Send customer notifications |
| `NOTIFY_SUPPORT` | `true` | Send support notifications |
| `NOTIFY_MANAGER` | `true` | Send manager alerts |

---

## Simulator Usage

```bash
# List scenarios
curl -H "Authorization: Bearer $TOKEN" \
  GET /api/self-healing/simulator/scenarios

# Run fraud scenario
curl -X POST /api/self-healing/simulator/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenario": "fraud_complaint", "customer_name": "Test User"}'

# Poll execution state
curl /api/self-healing/complaints/{complaint_id}/state

# Get full timeline
curl /api/self-healing/complaints/{complaint_id}/timeline
```

Available scenarios: `refund`, `replacement`, `delivery_delay`, `fraud_complaint`, `technical_issue`, `billing_issue`, `password_reset`, `wrong_product`

---

## Security (Feature 16)

- All 15 self-healing endpoints protected by JWT authentication
- Execution endpoints require `admin`/`manager`/`support` role
- Customer endpoints restricted to complaint owner
- Password reset tokens never logged (documented in handler)
- Mock APIs completely isolated — no production system calls possible
- Sensitive field audit controlled by `AUDIT_SENSITIVE` env var
- All MongoDB writes use `model_dump()` — no raw string injection

---

## Installation

```bash
# Install all dependencies (v2.0 + v3.0 additions)
pip install -r requirements.txt

# Start the server
uvicorn server:app --reload
```

No migration needed — v3.0 is purely additive.

---

## Testing

```bash
# Test action executor
python -c "
import asyncio
from action_executor import execute_action, resolve_action_type
ctx = {'complaint_id': 'test', 'entities': [], 'severity': 'high'}
result = asyncio.run(execute_action('refund', ctx))
print('Refund:', result['status'], result['reference_id'])
"

# Test simulator
python -c "
from simulator import list_scenarios, build_simulator_complaint
print([s['name'] for s in list_scenarios()])
c = build_simulator_complaint('fraud_complaint')
print('Complaint ID:', c['id'])
print('Expected action:', c['expected_action_type'])
"

# Test state machine
python -c "
from execution_models import validate_transition
print(validate_transition('EXECUTING', 'VERIFYING'))  # True
print(validate_transition('COMPLETED', 'EXECUTING'))  # False
"

# Test config
python -c "
from config import get_execution_cfg
cfg = get_execution_cfg()
print('max_retries:', cfg.max_retries)
print('escalation_risk_threshold:', cfg.escalation_risk_threshold)
"
```

---

## Key Design Decisions

- **Non-blocking**: Self-healing runs as a background `asyncio.Task` — the complaint POST returns instantly.
- **Graceful failures**: Every exception in the self-healing pipeline is caught and logged; it never crashes the main analysis.
- **Mock isolation**: `action_executor.py` handlers are async functions returning structured dicts — swapping to a real API requires only changing the handler body.
- **Additive state**: ExecutionRecord is a separate MongoDB document — existing complaint documents are only updated with `execution_id` and `execution_status` references.
- **Learning without retraining**: `learning_signals` collection stores structured outcomes for analytics; no model update is triggered automatically.
