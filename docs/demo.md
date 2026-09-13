# CommitmentOS — Demo Guide & Golden Demo Chain

## 1. Quick Start / Running the Demo

### Step 1: Start PostgreSQL (Docker)
```powershell
docker compose up -d
```
*(Ensures Postgres is running on port 5432 with database `commitmentos`).*

### Step 2: Seed Demo Data
```powershell
python evaluation/seed_demo.py
```
*(Seeds Acme company personas, 25 realistic commitments, prompt injection scenarios, and the Golden Demo Chain).*

### Step 3: Start FastAPI Backend
```powershell
.\scripts\start_api.ps1
```
*(Runs on `http://localhost:8000`).*

### Step 4: Start Next.js Frontend
```powershell
cd apps/web
npm run dev
```
*(Runs on `http://localhost:3000`).*

---

## 2. Two-Minute Presentation Script

| Timestamp | Phase | What to Say / Do |
|---|---|---|
| **0:00 – 0:15** | **The Problem** | *"Promises in companies are scattered across Slack and Gmail, work lives in Linear, and nobody owns the gap until a deadline silently blows up."* |
| **0:15 – 0:25** | **The Trigger** | Open `/chat` and enter: `"Find commitments at risk and take care of whatever you can."` |
| **0:25 – 0:55** | **Autonomous Discovery** | Watch the SSE live trace emit in real time: `OBSERVE → UNDERSTAND → RESOLVE → DEDUP → STATE`. Point out: *"17 commitments discovered, 3 at risk, 1 blocked."* |
| **0:55 – 1:20** | **Policy-Gated Actions** | Show the agent's actions: Auto-creates missing Linear task (Low Risk), posts internal Slack update (Low Risk), drafts external customer email held for human approval (High Risk). Navigate to `/approvals` and click **Approve**. |
| **1:20 – 1:40** | **Verification & Trace** | Navigate to `/commitments` and click into the commitment trace (`/commitments/[id]`). Show the expandable timeline proving the Linear task was confirmed via API, not just LLM assumption. |
| **1:40 – 1:55** | **Longitudinal Pattern** | In `/chat`, ask: *"Why does this keep happening?"* The agent queries Supermemory episodic history: *"Finance has blocked 4 of the last 5 pricing commitments across the past 3 quarters."* |
| **1:55 – 2:00** | **Conclusion** | *"CommitmentOS turns organizational promises into observable, actionable, and verifiable work."* |

---

## 3. Golden Demo Chain Breakdown

The deterministic test chain script in `evaluation/seed_demo.py`:
1. **Slack Observation:** Rahul Sharma writes: *"I'll send the revised pricing tomorrow."*
2. **Gmail Observation:** Rahul emails: *"Still waiting for Finance to confirm the discount."*
3. **Linear State:** Cross-reference shows no corresponding Linear issue exists.
4. **Resolution & Dedup:** Identity resolved to `Rahul Sharma` (`U001RAHUL` / `rahul@acme.com`). The two messages are merged into a single commitment with state `BLOCKED`.
5. **Memory Query:** Supermemory surfaces historical precedent: *"Finance has repeatedly blocked pricing docs pending margin approval."*
6. **Actions Taken:**
   - `create_linear_task`: Auto-authorized (Low risk)
   - `post_slack_update`: Auto-authorized (Low risk)
   - `send_email`: Held for Human Approval (High risk)
7. **Human Approval:** Human approves in `/approvals`. Verifier confirms email transmission.
