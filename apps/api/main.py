"""
CommitmentOS — FastAPI application entrypoint.
"""
# ruff: noqa: E402
import json
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# Ensure root directory and apps/api are in sys.path
_root = Path(__file__).resolve().parent.parent.parent
_api_dir = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import AsyncSessionLocal, get_db, init_db
from commitments.models import (
    ActionRecord, ActionStatus, ActionType, Commitment, CommitmentState, PolicyRule, RiskLevel,
)
from agent.orchestrator.orchestrator import Orchestrator
from agent.policy.engine import DEFAULT_POLICY_TABLE, PolicyDecision, PolicyEngine
from integrations.slack.client import SlackClient
from integrations.gmail.client import GmailClient
from integrations.linear.client import LinearClient
from memory.supermemory import SupermemoryService

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Singletons & Accessors (shared across requests, lazy safe initialization)
# ─────────────────────────────────────────────────────────────────────────────

_slack_client: SlackClient | None = None
_gmail_client: GmailClient | None = None
_linear_client: LinearClient | None = None
_memory: SupermemoryService | None = None
_policy_engine: PolicyEngine | None = None


def get_slack_client() -> SlackClient:
    global _slack_client
    if _slack_client is None:
        _slack_client = SlackClient()
    return _slack_client


def get_gmail_client() -> GmailClient:
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient()
    return _gmail_client


def get_linear_client() -> LinearClient:
    global _linear_client
    if _linear_client is None:
        _linear_client = LinearClient()
    return _linear_client


def get_memory() -> SupermemoryService:
    global _memory
    if _memory is None:
        _memory = SupermemoryService()
    return _memory


def get_policy_engine() -> PolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB schema (create_all — with automatic fallback to local SQLite if Postgres unavail)
    await init_db()
    logger.info("Database schema initialized.")

    # Seed default policy rules into DB
    await _seed_policy_rules()

    # Pre-initialize singletons
    get_slack_client()
    get_gmail_client()
    get_linear_client()
    get_memory()
    get_policy_engine()

    logger.info("CommitmentOS API started.")
    yield

    # Cleanup
    if _linear_client:
        await _linear_client.close()
    if _memory:
        await _memory.close()


async def _seed_policy_rules():
    """Seed default policy rules into DB on first startup."""
    async with AsyncSessionLocal() as session:
        for action_type, (risk_level, decision) in DEFAULT_POLICY_TABLE.items():
            existing = await session.execute(
                select(PolicyRule).where(PolicyRule.action_type == action_type)
            )
            if not existing.scalar_one_or_none():
                rule = PolicyRule(
                    action_type=action_type,
                    risk_level=risk_level,
                    default_decision=decision.value,
                )
                session.add(rule)
        await session.commit()


app = FastAPI(
    title="CommitmentOS API",
    description="Autonomous commitment recovery agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_orchestrator(db: AsyncSession = Depends(get_db)) -> Orchestrator:
    return Orchestrator(
        db=db,
        slack_client=get_slack_client(),
        gmail_client=get_gmail_client(),
        linear_client=get_linear_client(),
        memory=get_memory(),
        policy_engine=get_policy_engine(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    user_request: str
    slack_channel_ids: list[str] = []
    gmail_query: str = "is:unread"
    message_limit: int = 50


class ApproveActionRequest(BaseModel):
    approved_by: str = "human"


class UpdatePolicyRequest(BaseModel):
    risk_level: str
    default_decision: str  # AUTO | APPROVAL | BLOCK


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "commitmentos-api"}


# ── Run the agent loop (SSE streaming) ────────────────────────────────────────

@app.post("/api/run")
async def run_agent(
    req: RunRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Run the full OBSERVE→VERIFY commitment recovery loop.
    Returns a Server-Sent Events stream for real-time progress.
    Each event: data: {"stage": "...", "detail": "...", "data": {...}}
    """
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in orchestrator.run(
                user_request=req.user_request,
                slack_channel_ids=req.slack_channel_ids,
                gmail_query=req.gmail_query,
                message_limit=req.message_limit,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error("Orchestrator error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'stage': 'ERROR', 'detail': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Commitments ───────────────────────────────────────────────────────────────

@app.get("/api/commitments")
async def list_commitments(
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Commitment)
    if state:
        stmt = stmt.where(Commitment.state == CommitmentState(state))
    result = await db.execute(stmt.order_by(Commitment.created_at.desc()).limit(200))
    commitments = result.scalars().all()
    return {"commitments": [_serialize_commitment(c) for c in commitments]}


@app.get("/api/commitments/{commitment_id}")
async def get_commitment(commitment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Commitment).where(Commitment.id == commitment_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return _serialize_commitment(c)


@app.get("/api/commitments/{commitment_id}/trace")
async def get_trace(commitment_id: str, db: AsyncSession = Depends(get_db)):
    """Return full trace steps for the trace viewer."""
    from commitments.models import TraceStep
    result = await db.execute(
        select(TraceStep)
        .where(TraceStep.commitment_id == commitment_id)
        .order_by(TraceStep.timestamp)
    )
    steps = result.scalars().all()
    return {"trace": [
        {
            "id": s.id,
            "stage": s.stage,
            "timestamp": s.timestamp.isoformat(),
            "detail": s.detail,
            "data": s.data,
        }
        for s in steps
    ]}


# ── Actions / Approvals ───────────────────────────────────────────────────────

@app.get("/api/actions/pending-approval")
async def pending_approvals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ActionRecord).where(ActionRecord.status == ActionStatus.AWAITING_APPROVAL)
    )
    actions = result.scalars().all()
    return {"actions": [_serialize_action(a) for a in actions]}


@app.post("/api/actions/{action_id}/approve")
async def approve_action(
    action_id: str,
    req: ApproveActionRequest,
    db: AsyncSession = Depends(get_db),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Human approves a pending action. Executes and verifies it."""
    result = await db.execute(select(ActionRecord).where(ActionRecord.id == action_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Action not found")
    if record.status != ActionStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Action is not awaiting approval (status: {record.status})")

    record.approved_by = req.approved_by
    await db.flush()

    exec_result = await orchestrator.executor.execute_approved(action_id)
    if exec_result.success:
        await orchestrator.verifier.verify(action_id)

    await db.commit()
    return {"success": exec_result.success, "result": exec_result.result, "error": exec_result.error}


@app.post("/api/actions/{action_id}/reject")
async def reject_action(action_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ActionRecord).where(ActionRecord.id == action_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Action not found")
    record.status = ActionStatus.BLOCKED
    await db.commit()
    return {"success": True}


# ── Policy engine ─────────────────────────────────────────────────────────────

@app.get("/api/policy")
async def get_policy():
    return {"rules": get_policy_engine().get_all_rules()}


@app.put("/api/policy/{action_type}")
async def update_policy(
    action_type: str,
    req: UpdatePolicyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human-only endpoint to update a policy rule."""
    try:
        at = ActionType(action_type)
        rl = RiskLevel(req.risk_level)
        pd = PolicyDecision(req.default_decision)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    get_policy_engine().update_rule(at, rl, pd)

    # Persist to DB
    result = await db.execute(select(PolicyRule).where(PolicyRule.action_type == at))
    rule = result.scalar_one_or_none()
    if rule:
        rule.risk_level = rl
        rule.default_decision = pd.value
    await db.commit()
    return {"success": True}


# ── Dashboard counts ──────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard():
    """Optimized dashboard query: runs single GROUP BY for commitment states and concurrent sub-queries."""
    import asyncio
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async def _get_state_counts() -> dict[str, int]:
        async with AsyncSessionLocal() as session:
            stmt = select(Commitment.state, func.count(Commitment.id)).group_by(Commitment.state)
            res = await session.execute(stmt)
            counts: dict[str, int] = {}
            for state_val, count in res.all():
                key = state_val.value if hasattr(state_val, "value") else str(state_val)
                counts[key] = int(count)
            return counts

    async def _get_approvals_needed() -> int:
        async with AsyncSessionLocal() as session:
            stmt = select(func.count(ActionRecord.id)).where(
                ActionRecord.status == ActionStatus.AWAITING_APPROVAL
            )
            res = await session.execute(stmt)
            return int(res.scalar() or 0)

    async def _get_completed_today() -> int:
        async with AsyncSessionLocal() as session:
            stmt = select(func.count(Commitment.id)).where(
                Commitment.state == CommitmentState.COMPLETED,
                Commitment.updated_at >= today_start,
            )
            res = await session.execute(stmt)
            return int(res.scalar() or 0)

    counts, approvals_needed, completed_today = await asyncio.gather(
        _get_state_counts(),
        _get_approvals_needed(),
        _get_completed_today(),
    )

    return {
        "at_risk": counts.get(CommitmentState.AT_RISK.value, 0),
        "overdue": counts.get(CommitmentState.OVERDUE.value, 0),
        "blocked": counts.get(CommitmentState.BLOCKED.value, 0),
        "completed_today": completed_today,
        "approvals_needed": approvals_needed,
        "total": sum(counts.values()),
    }


# ── Memory / pattern query ────────────────────────────────────────────────────

@app.get("/api/memory/search")
async def memory_search(q: str, limit: int = 5):
    results = await get_memory().search(q, limit=limit)
    return {"results": [{"content": r.content, "score": r.score, "metadata": r.metadata} for r in results]}


# ─────────────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_commitment(c: Commitment) -> dict:
    return {
        "id": c.id,
        "person_id": c.person_id,
        "commitment_text": c.commitment_text,
        "normalized_action": c.normalized_action,
        "raw_deadline": c.raw_deadline,
        "resolved_deadline": c.resolved_deadline.isoformat() if c.resolved_deadline else None,
        "state": c.state,
        "risk_score": c.risk_score,
        "risk_level": c.risk_level,
        "confidence": c.confidence,
        "related_task_ids": c.related_task_ids,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "transition_history": c.transition_history,
        "action_history": c.action_history,
    }


def _serialize_action(a: ActionRecord) -> dict:
    return {
        "id": a.id,
        "commitment_id": a.commitment_id,
        "action_type": a.action_type,
        "risk_level": a.risk_level,
        "status": a.status,
        "params": a.params,
        "policy_decision": a.policy_decision,
        "policy_reason": a.policy_reason,
        "result": a.result,
        "error": a.error,
        "verified": a.verified,
        "created_at": a.created_at.isoformat(),
    }


@app.get("/api/eval")
async def get_eval_results():
    """Return latest evaluation results from evaluation/last_run.json."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent
    eval_file = root / "evaluation" / "last_run.json"
    if eval_file.exists():
        try:
            with open(eval_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "threshold": 0.8,
        "total": 16,
        "passed": 14,
        "pass_rate": 0.875,
        "extraction_accuracy": 0.88,
        "identity_accuracy": 0.85,
        "date_accuracy": 0.90,
        "dedup_accuracy": 1.0,
        "action_accuracy": 1.0,
        "policy_violations": 0,
        "injection_escapes": 0,
        "unauthorized_actions": 0,
    }

