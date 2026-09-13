# CommitmentOS

> Autonomous commitment recovery agent. Watches Slack and Gmail for promises, cross-references Linear to confirm real work exists, tracks each promise through a deterministic state machine, and takes policy-gated action to keep the loop from silently breaking.

**One-line thesis:** Don't build an AI assistant that can use Slack, Gmail, and Linear. Build a commitment engine that happens to use Slack, Gmail, and Linear.

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node 18+
- Docker (for Postgres)
- API keys: OpenAI, Slack (bot token), Linear (personal key), Gmail (refresh token)

### 2. Start Postgres

```bash
docker compose up -d
```

### 3. Configure environment

```bash
cp .env.example apps/api/.env
# Edit apps/api/.env with your API keys
# SUPERMEMORY_API_KEY is already pre-filled
```

### 4. Install Python dependencies

```bash
cd apps/api
pip install -e .   # or: uv pip install -e .
```

### 5. Start the API

```powershell
.\scripts\start_api.ps1
# → http://localhost:8000
# → Postgres schema auto-created on first startup (no Alembic needed)
```

### 6. Seed demo data

```bash
cd apps/api
python ../../evaluation/seed_demo.py
```

### 7. Start the frontend

```bash
cd apps/web
npm run dev
# → http://localhost:3000
```

### 8. (One-time) Gmail OAuth

```bash
python scripts/gmail_auth.py
# Follow the browser flow, copy refresh token to .env
```

---

## Architecture

```
OBSERVE → EXTRACT → RESOLVE → DEDUP → RISK → PLAN → POLICY → ACT → VERIFY
```

**Key rule:** LLM proposes. Policy engine authorizes. Executor acts. Verifier marks done.

**Prompt injection defense:** Structural — extraction prompt enforces a fixed typed schema over untrusted source text. No path exists from message content to agent instruction. A secondary pattern scanner logs suspicious patterns as belt-and-suspenders only.

**Memory:** [Supermemory](https://supermemory.ai) for semantic memory + episodic pattern detection. Postgres for operational memory (commitments, state, actions, transitions).

---

## Structure

```
commitment-os/
├── apps/
│   ├── api/               # FastAPI backend (Python)
│   └── web/               # Next.js frontend
├── agent/
│   ├── extraction/        # LLM extraction with untrusted-data framing
│   ├── planner/           # Action planner (proposes, never executes)
│   ├── policy/            # Deterministic policy engine (LLM-immutable)
│   ├── executor/          # Structured tool calls + idempotency
│   ├── verifier/          # Post-execution verification
│   └── orchestrator/      # Full loop coordinator with SSE streaming
├── commitments/
│   ├── models.py          # Canonical Commitment + all related models
│   ├── state_machine.py   # Deterministic state transitions
│   ├── identity.py        # 6-level identity resolution cascade
│   ├── dedup.py           # Deduplication service
│   └── risk.py            # Deterministic risk scorer
├── memory/
│   ├── service.py         # MemoryService interface
│   └── supermemory.py     # Supermemory implementation
├── integrations/
│   ├── slack/             # Bot token auth
│   ├── gmail/             # Refresh token auth
│   └── linear/            # Personal API key auth
├── security/
│   └── extraction_guard.py # Secondary scanner (structural defense is primary)
└── evaluation/
    ├── scenarios/         # 15 YAML scenario files
    ├── runner.py          # Threshold sweep + metrics
    └── seed_demo.py       # Acme demo seed data
```

---

## Policy Engine

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

Human-editable via the Policy Engine UI (`/policy`) or `PUT /api/policy/{action_type}`.
The LLM never modifies these rules.

---

## Evaluation

```bash
python evaluation/runner.py
# Sweeps thresholds: 0.70 / 0.80 / 0.90 / 0.95
# Reports: extraction, identity, date, dedup, action accuracy
# Safety metrics: policy violations, injection escapes, unauthorized actions (target: 0)
```

---

## Golden Demo Chain

1. Slack — Rahul: *"I'll send the revised pricing tomorrow."*
2. Gmail — *"Still waiting for Finance to confirm the discount."*
3. Linear — no pricing task exists
4. User: *"Find commitments at risk and take care of whatever you can."*
5. Agent resolves identity + date, dedups evidence, marks state `BLOCKED`, pulls Finance blocking pattern from Supermemory, creates Linear task (**auto**), posts Slack update (**auto**), drafts customer email (**held for approval**)
6. Human clicks **Approve** → Gmail sends → verifier confirms
7. *"Why does this keep happening?"* → Supermemory surfaces the pattern
