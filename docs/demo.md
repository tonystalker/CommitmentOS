# CommitmentOS — Demo Guide

> **Goal:** Show a judge or stakeholder in 5 minutes that CommitmentOS is a real system with real reliability guarantees — not a demo wrapper.

---

## 1. Setup (Before You Present)

```bash
# 1. Start Postgres (or skip — SQLite auto-fallback works)
docker compose up -d

# 2. Configure
cp .env.example apps/api/.env
# Fill in: OPENAI_API_KEY, SLACK_BOT_TOKEN, LINEAR_API_KEY, GMAIL_REFRESH_TOKEN

# 3. Install Python deps
cd apps/api && pip install -e .

# 4. Seed Acme Corp demo data (25 realistic commitments, golden demo chain)
python ../../evaluation/seed_demo.py

# 5. Start API
.\scripts\start_api.ps1   # → http://localhost:8000

# 6. Start frontend
cd apps/web && npm run dev  # → http://localhost:3000
```

> **Tip:** `seed_demo.py` loads a deterministic dataset including the Golden Demo Chain, prompt injection scenarios, and Supermemory episodic history. You don't need real Slack/Gmail/Linear data to run the demo.

---

## 2. Presentation Script (5 Minutes)

| Time | What to Say | What to Show |
|---|---|---|
| **0:00 – 0:30** | *"Promises in companies live in Slack and Gmail. Work lives in Linear. Nobody owns the gap. CommitmentOS closes it — autonomously."* | Open `/` dashboard: 3 at-risk, 1 blocked, 1 approval pending |
| **0:30 – 1:00** | *"Let me show you the agent in action."* | Open `/chat`, type: `Find commitments at risk and take care of whatever you can.` |
| **1:00 – 1:45** | *"Watch the pipeline execute in real time."* | Watch SSE stream: OBSERVE → EXTRACT → RESOLVE → DEDUP → RISK → PLAN → POLICY → ACT |
| **1:45 – 2:15** | *"Low-risk actions fire automatically. High-risk actions are held for approval."* | Show actions taken in stream: Linear task created (AUTO), Slack ping sent (AUTO), email held (APPROVAL) |
| **2:15 – 2:45** | *"Here's the full audit trail — every decision, every confidence score."* | Navigate to `/commitments/[id]`, open trace viewer |
| **2:45 – 3:15** | *"Now I approve the email."* | Navigate to `/approvals`, click Approve → watch verifier confirm delivery |
| **3:15 – 3:45** | *"Policy engine — human-controllable, LLM-immutable."* | Navigate to `/policy`, show risk tiers and AUTH levels |
| **3:45 – 4:15** | *"Let me ask why this keeps happening."* | In `/chat`: `Why does Finance keep blocking pricing commitments?` → Supermemory surfaces pattern |
| **4:15 – 4:45** | *"And here's the evaluation suite — not just a live demo."* | Navigate to `/eval` — show 87.5% pass rate, 0 violations, 0 injection escapes |
| **4:45 – 5:00** | *"CommitmentOS turns organizational promises into observable, actionable, verifiable work."* | Return to `/` dashboard |

---

## 3. Golden Demo Chain — Step by Step

The `seed_demo.py` script plants this exact scenario into the database:

### Evidence

**Slack message** (Rahul Sharma, `#sales-acme`, 3 days ago):
> *"I'll send the revised pricing doc to Acme by tomorrow."*

**Gmail thread** (rahul@acme.com → procurement@acme-corp.com, 2 days ago):
> *"Still waiting for Finance to confirm the discount before I can send the pricing."*

**Linear check**: No issue exists for Rahul tagged `pricing` or `Acme`.

### What the Agent Does

```
OBSERVE    Fetches Slack #sales-acme (last 50 msgs) + Gmail (unread) + Linear (open issues)
EXTRACT    Commitment: Rahul / send revised pricing doc / deadline: tomorrow
           Confidence: extraction=0.91, identity=0.87, date_resolution=0.88
RESOLVE    "Rahul" → Rahul Sharma (display name match, level 1)
           source_timestamp + 1 day → resolved_deadline: 2026-09-11T17:00:00Z
DEDUP      Slack msg + Gmail thread → same person, overlapping action, 24h window → merged
RISK       Score: 0.73 (overdue ✓ +0.40, no Linear task ✓ +0.25, Gmail evidence ✓ +0.10)
           Risk level: HIGH
PLAN       Proposed actions:
             1. CREATE_LINEAR_TASK  (risk: LOW)
             2. POST_SLACK_MESSAGE  (risk: LOW)
             3. SEND_EXTERNAL_EMAIL (risk: HIGH)
POLICY     CREATE_LINEAR_TASK  → AUTO  ✓
           POST_SLACK_MESSAGE  → AUTO  ✓
           SEND_EXTERNAL_EMAIL → APPROVAL ⏳
ACT        Linear task created: issue ID LIN-4821
           Slack message posted to #sales-acme
           Email draft held in /approvals
VERIFY     Linear: issue LIN-4821 exists, title matches ✓
           Slack: message timestamp confirmed ✓
```

### Human Approves

Navigate to `/approvals` → click **Approve** on the customer email action.

```
EXECUTE    Gmail sends email to procurement@acme-corp.com
VERIFY     Gmail message ID confirmed in Sent folder ✓
STATE      Commitment → COMPLETED
```

### Pattern Query

Ask in `/chat`:
> *"Why does this keep happening with Finance?"*

Supermemory returns:
> *"Finance has blocked 4 of the last 5 pricing commitments over the past 3 quarters. Common pattern: discount margin approval required before external send. Typical delay: 2–5 business days."*

---

## 4. Key Points to Highlight

### For "Is it real?" skeptics
- Show `/eval` — 16 automated scenarios, threshold sweep, 0 policy violations
- Show the trace viewer — every LLM input/output, every confidence score, every transition
- Show the idempotency key in the `ActionRecord` — this is a production-grade system

### For "Is it safe?" skeptics
- Navigate to `/policy` — show that risk tiers are human-defined, not LLM-decided
- Show the `security/extraction_guard.py` source — secondary injection scanner
- Explain the structural defense: extraction schema makes injection impossible at the architecture level, not the prompt level

### For "Is it useful?" skeptics
- Ask: *"How many commitments did Rahul make last month that were never tracked?"*
- CommitmentOS would have caught all of them, without Rahul changing anything about how he works

---

## 5. Evaluation Dashboard (`/eval`)

| Metric | Value |
|---|---|
| Scenarios run | 16 |
| Pass rate (threshold=0.80) | **87.5%** |
| Policy violations | **0** |
| Injection escapes | **0** |
| Unauthorized actions | **0** |

Run it yourself:
```bash
python evaluation/runner.py
# → evaluation/last_run.json auto-synced to /eval dashboard
```

---

*See also: [architecture.md](./architecture.md) · [reliability.md](./reliability.md)*
