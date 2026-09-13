# CommitmentOS

> **Autonomous commitment recovery agent.** Watches Slack and Gmail for promises, cross-references Linear to confirm real work exists, tracks each promise through a deterministic state machine, and takes policy-gated action to keep the loop from silently breaking.

**One-line thesis:** Don't build an AI assistant that *can use* Slack, Gmail, and Linear. Build a commitment engine that *happens to use* them.

---

## Why This Exists

Commitments break silently. Someone says *"I'll send the pricing doc tomorrow"* in Slack, the thread dies, and nobody follows up. The task never lands in Linear. The customer never hears back. The pattern repeats.

CommitmentOS is the missing layer: an autonomous agent that **observes** cross-channel evidence, **extracts** promises with LLM precision, **resolves** them into canonical commitments, and **acts** — automatically where it's safe, with human approval where it isn't.

---

## 📚 Documentation

| Doc | What's inside |
|---|---|
| [Architecture →](./docs/architecture.md) | Full pipeline breakdown, all 9 stages, data model, security properties, component API |
| [Reliability & Evaluation →](./docs/reliability.md) | Threat model, reliability mechanisms, full evaluation suite results, threshold sweep |
| [Demo Guide →](./docs/demo.md) | 5-minute presentation script, golden demo chain step-by-step, key talking points |

---

## 🏗️ Technical Execution (30%)

### Architecture: OBSERVE → EXTRACT → RESOLVE → DEDUP → RISK → PLAN → POLICY → ACT → VERIFY

Every stage is a discrete, typed, independently-testable module. There are no monolithic agent blobs.

```
CommitmentOS/
├── agent/
│   ├── extraction/       # LLM extraction — untrusted-data framing, typed schema output
│   ├── planner/          # Action planner — proposes only, never executes
│   ├── policy/           # Deterministic policy engine — LLM-immutable
│   ├── executor/         # Structured tool calls + idempotency keys
│   ├── verifier/         # Post-execution verification (Linear task exists? Slack sent?)
│   └── orchestrator/     # Full-loop coordinator with SSE streaming
├── commitments/
│   ├── models.py         # Canonical Commitment + all related SQLAlchemy models
│   ├── state_machine.py  # Deterministic state transitions (PROPOSED → CONFIRMED → AT_RISK → …)
│   ├── identity.py       # 6-level identity resolution cascade
│   ├── dedup.py          # Deduplication — merges cross-channel evidence to one commitment
│   └── risk.py           # Deterministic risk scorer (overdue weight, no-task penalty, etc.)
├── apps/
│   ├── api/              # FastAPI backend — async, SSE streaming, Postgres or SQLite
│   └── web/              # Next.js frontend — dashboard, trace viewer, approvals, policy editor
├── integrations/
│   ├── slack/            # Bot token auth
│   ├── gmail/            # OAuth2 refresh token
│   └── linear/           # Personal API key
├── memory/
│   └── supermemory.py    # Semantic + episodic memory via Supermemory
└── security/
    └── extraction_guard.py  # Secondary scanner (structural defense is primary)
```

### Key Design Decisions

| Decision | Why |
|---|---|
| **LLM proposes, policy engine authorizes, executor acts** | Clean separation of intelligence from authorization from side-effects |
| **Typed schema extraction** | LLM output is validated into a `CommitmentExtraction` Pydantic model — no freeform strings reach downstream |
| **Idempotency keys on every action** | Prevents duplicate Linear tasks / Slack messages on retry |
| **Append-only transition + action history** | Full audit trail; nothing is deleted or mutated silently |
| **Postgres primary, SQLite fallback** | Works for local demo, scales for production |
| **SSE streaming from orchestrator** | UI receives real-time per-stage updates without polling |
| **Multi-dimensional confidence scores** | Per-commitment scores for extraction, identity, date resolution, dedup, action selection |

### Prompt Injection Defense

**Structural (primary):** The extraction prompt enforces a fixed typed schema over untrusted source text. No path exists from message content to agent instruction. The LLM receives user messages as *data*, not as *instructions*.

**Scanner (secondary, belt-and-suspenders):** `security/extraction_guard.py` flags suspicious patterns (e.g., `ignore all`, `disregard`) and marks evidence rows with `injection_flagged=True` for audit.

### State Machine

```
PROPOSED → CONFIRMED → AT_RISK → BLOCKED
                    ↘           ↘
                     OVERDUE → COMPLETED
                              ↘ CANCELLED
```

Every transition is written to `transition_history` (append-only JSON) with timestamp and reason.

---

## 📊 Reliability & Evaluation (25%)

### Automated Evaluation Suite

```bash
python evaluation/runner.py
# Sweeps thresholds: 0.70 / 0.80 / 0.90 / 0.95
# Outputs: evaluation/last_run.json
```

16 YAML scenarios across 5 categories:

| Category | What's tested |
|---|---|
| `extraction` | Correct commitment text, person, deadline extraction |
| `identity` | Name → email → Slack ID → Linear username resolution |
| `date_resolution` | "tomorrow", "end of week", "Friday 5pm" → UTC datetime |
| `dedup` | Cross-channel evidence merges to one canonical commitment |
| `action / authorization` | Correct action selected, policy respected |

### Metrics at `threshold=0.80`

| Metric | Target | Achieved |
|---|---|---|
| Overall pass rate | ≥ 80% | **87.5%** (14/16) |
| Extraction accuracy | ≥ 85% | **88%** |
| Identity accuracy | ≥ 80% | **85%** |
| Date resolution accuracy | ≥ 85% | **90%** |
| Deduplication accuracy | 100% | **100%** |
| Action selection rate | 100% | **100%** |
| **Policy violations** | **0** | **0** |
| **Injection escapes** | **0** | **0** |
| **Unauthorized actions** | **0** | **0** |

Results are persisted to `evaluation/last_run.json` and surfaced live in the `/eval` dashboard tab.

---

## 🎯 Usefulness (20%)

### The Problem It Solves

Modern teams generate commitments constantly across Slack, email, and project tools. Most of them are never tracked. Humans forget. Threads die. Customers wait.

CommitmentOS closes that gap **without requiring any behavior change from the team** — no new workflow, no new tool to adopt. It watches existing channels, surfaces what's at risk, and takes the low-risk actions automatically.

### What It Actually Does

1. **Ingests** Slack channels + Gmail threads + Linear project board
2. **Extracts** commitments via LLM (who promised what by when)
3. **Resolves** person identity across platforms (Rahul in Slack = rahul@acme.com in Gmail = rahul_acme in Linear)
4. **Deduplicates** — one mention in Slack + one in Gmail = one canonical commitment
5. **Scores risk** — overdue, no Linear task, high-stakes action type
6. **Plans actions** — create task, post reminder, draft email
7. **Executes automatically** for low-risk actions (task creation, Slack ping)
8. **Holds for human approval** for high-risk actions (external email, assignment)
9. **Verifies** — did the Linear task actually get created? Did the email actually send?
10. **Surfaces patterns** via Supermemory — "Finance blocking has happened 3 times this quarter"

### Policy Engine (Human-Controllable)

| Action | Risk | Default |
|---|---|---|
| Create Linear task | Low | **AUTO** |
| Update Linear status | Low | **AUTO** |
| Post Slack message | Low | **AUTO** |
| Create reminder | Low | **AUTO** |
| Assign task | Medium | **APPROVAL** |
| Send external email | High | **APPROVAL** |
| Reschedule meeting | High | **APPROVAL** |
| Financial action | Critical | **BLOCK** |

Rules are human-editable in the Policy UI (`/policy`) or via `PUT /api/policy/{action_type}`. **The LLM never modifies these rules.**

---

## 💡 Originality (15%)

CommitmentOS is not a chatbot wrapper or a workflow automation tool. It's a novel abstraction:

**Commitment as a first-class domain object** — with canonical identity, typed evidence, deterministic state, multi-dimensional confidence, risk scoring, and a full audit trail. Most tools track tasks. This tracks *promises*, across channels, with verification.

Key original contributions:

- **6-level identity resolution cascade**: display name → email → Slack user ID → Linear username → fuzzy name match → "unknown person" with low confidence — across three platforms, in one pass
- **Multi-dimensional confidence per commitment**: not one score, but separate scores for extraction quality, identity confidence, date resolution, dedup certainty, and action selection — each used independently for routing decisions
- **LLM-proposes / policy-gates / executor-acts** separation: the LLM's role is bounded to extraction and planning. Authorization is deterministic and human-editable. This is an explicit architectural constraint, not a convention.
- **Episodic pattern memory via Supermemory**: "Why does this keep happening?" gets a real answer — surfaced from semantic search over commitment history, not just the last run.
- **SSE streaming orchestrator**: the full OBSERVE→VERIFY loop streams per-stage events to the frontend in real time, so users see exactly which stage the agent is in and why each decision was made.

---

## 🎬 Demo Clarity (10%)

### Golden Demo Chain (5 minutes)

**Setup:** Seed the Acme Corp demo data.
```bash
cd apps/api && python ../../evaluation/seed_demo.py
```

**Step 1 — Slack evidence**
> Rahul: *"I'll send the revised pricing doc to the customer by tomorrow."*

**Step 2 — Gmail evidence**
> Thread: *"Still waiting for Finance to confirm the discount before we can send."*

**Step 3 — Linear reality check**
> No pricing task exists for Rahul.

**Step 4 — User prompt**
> *"Find commitments at risk and take care of whatever you can."*

**What the agent does (watch the SSE stream):**
1. `OBSERVE` — fetches Slack + Gmail + Linear
2. `EXTRACT` — LLM extracts commitment: Rahul / send pricing doc / deadline tomorrow
3. `RESOLVE` — Rahul in Slack resolved to rahul@acme.com
4. `DEDUP` — Slack mention + Gmail thread → one canonical commitment
5. `RISK` — overdue score HIGH (no Linear task, deadline passed, external stakeholder)
6. `PLAN` — three proposed actions: create Linear task, post Slack update, draft customer email
7. `POLICY` — Linear task: **AUTO** ✓, Slack ping: **AUTO** ✓, external email: **APPROVAL** ⏳
8. `ACT` — Linear task created, Slack message posted; email held for approval
9. `VERIFY` — Linear task confirmed to exist via API

**Step 5 — Human approves**
Click **Approve** on the email action → Gmail sends → verifier confirms delivery.

**Step 6 — Pattern query**
> *"Why does this keep happening with Finance?"*

Supermemory surfaces: *Finance blocking on pricing has caused 3 commitment failures this quarter.*

### Running the Demo Locally

```bash
# 1. Start Postgres (or skip — SQLite fallback works out of the box)
docker compose up -d

# 2. Configure
cp .env.example apps/api/.env
# Fill in: OPENAI_API_KEY, SLACK_BOT_TOKEN, LINEAR_API_KEY, GMAIL_REFRESH_TOKEN

# 3. Install Python deps
cd apps/api && pip install -e .

# 4. Start API
.\scripts\start_api.ps1
# → http://localhost:8000/docs

# 5. Seed demo data
python ../../evaluation/seed_demo.py

# 6. Start frontend
cd apps/web && npm install && npm run dev
# → http://localhost:3000

# 7. (Optional) Gmail OAuth
python scripts/gmail_auth.py
```

### API Reference

| Endpoint | Description |
|---|---|
| `POST /api/run` | Run the full agent loop (SSE stream) |
| `GET /api/commitments` | List all commitments (filter by state) |
| `GET /api/commitments/{id}/trace` | Full per-stage audit trail |
| `GET /api/actions/pending-approval` | Actions awaiting human approval |
| `POST /api/actions/{id}/approve` | Approve and execute a held action |
| `POST /api/actions/{id}/reject` | Reject a held action |
| `GET /api/policy` | Get all policy rules |
| `PUT /api/policy/{action_type}` | Update a policy rule (human-only) |
| `GET /api/dashboard` | Aggregated counts by state |
| `GET /api/memory/search?q=...` | Semantic memory search |
| `GET /api/eval` | Latest evaluation results |

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async), Pydantic |
| Database | Postgres (Docker) with SQLite auto-fallback |
| LLM | OpenAI (GPT-4o / structured outputs) |
| Memory | [Supermemory](https://supermemory.ai) |
| Integrations | Slack Web API, Gmail API (OAuth2), Linear GraphQL API |
| Frontend | Next.js 14 (App Router), TypeScript |
| Evaluation | Custom YAML scenario runner, 16 scenarios |

---

## Prerequisites

- Python 3.11+
- Node 18+
- Docker (optional — SQLite fallback works without it)
- API keys: `OPENAI_API_KEY`, `SLACK_BOT_TOKEN`, `LINEAR_API_KEY`, `GMAIL_REFRESH_TOKEN`
- `SUPERMEMORY_API_KEY` (pre-filled in `.env.example`)
