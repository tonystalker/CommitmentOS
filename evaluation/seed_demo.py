"""
CommitmentOS — Demo seed script for the Acme fictional company.

Seeds:
  - 5 people (Rahul, Sarah, Ana, Marcus, Priya)
  - 25 commitments covering: completed, overdue, blocked, duplicate (Slack+Gmail),
    missing Linear task, ambiguous identity, prompt-injection attempt
  - Stores evidence in Supermemory for episodic pattern detection
  - The golden demo chain from plan.md §9 is included

Run: python evaluation/seed_demo.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "api"))


from database import init_db, AsyncSessionLocal
from commitments.models import (
    Commitment, CommitmentState, Evidence, EvidenceSource,
    Person, RiskLevel, ActionRecord, ActionType, ActionStatus,
)
from commitments.state_machine import CommitmentStateMachine
from memory.supermemory import SupermemoryService


NOW = datetime.now(timezone.utc)


async def seed():
    await init_db()
    memory = SupermemoryService()

    async with AsyncSessionLocal() as db:
        print("Seeding Acme demo data...")

        # ── People ─────────────────────────────────────────────────────────
        people = {
            "rahul": Person(
                display_name="Rahul Sharma",
                email="rahul@acme.com",
                slack_user_id="U001RAHUL",
                linear_username="rahul.sharma",
                timezone="Asia/Kolkata",
            ),
            "sarah": Person(
                display_name="Sarah Chen",
                email="sarah@acme.com",
                slack_user_id="U002SARAH",
                linear_username="sarah.chen",
                timezone="America/New_York",
            ),
            "ana": Person(
                display_name="Ana Rodriguez",
                email="ana@acme.com",
                slack_user_id="U003ANA",
                linear_username="ana.rodriguez",
                timezone="America/Los_Angeles",
            ),
            "marcus": Person(
                display_name="Marcus Johnson",
                email="marcus@acme.com",
                slack_user_id="U004MARCUS",
                linear_username="marcus.johnson",
                timezone="Europe/London",
            ),
            "priya": Person(
                display_name="Priya Patel",
                email="priya@acme.com",
                slack_user_id="U005PRIYA",
                linear_username="priya.patel",
                timezone="America/Chicago",
            ),
        }
        for p in people.values():
            db.add(p)
        await db.flush()
        print(f"  [OK] {len(people)} people seeded")

        commitments_seeded = []

        # ── GOLDEN DEMO CHAIN (plan.md §9) ────────────────────────────────
        # 1. Rahul: "I'll send the revised pricing tomorrow" (Slack)
        # 2. Gmail: "Still waiting for Finance to confirm the discount."
        # → No Linear task exists
        # → State: BLOCKED (Finance hasn't confirmed)
        # → Memory: Finance has blocked 4 previous pricing commitments

        pricing_commitment = Commitment(
            person_id=people["rahul"].id,
            commitment_text="Rahul committed to: send the revised pricing to the team",
            normalized_action="send revised pricing document to team",
            raw_deadline="tomorrow",
            resolved_deadline=NOW + timedelta(days=1),
            source_timestamp=NOW - timedelta(hours=6),
            timezone="Asia/Kolkata",
            state=CommitmentState.BLOCKED,
            risk_score=0.82,
            risk_level=RiskLevel.HIGH,
            confidence={"extraction": 0.96, "identity": 0.99, "date_resolution": 0.90, "deduplication": 0.95, "action_selection": 0.88},
            related_task_ids=[],   # intentionally empty — no Linear task
        )
        db.add(pricing_commitment)
        await db.flush()

        # Evidence: Slack
        ev_slack = Evidence(
            commitment_id=pricing_commitment.id,
            source=EvidenceSource.SLACK,
            extracted_person="Rahul Sharma",
            extracted_action="send revised pricing document to team",
            extracted_deadline_phrase="tomorrow",
            source_message_id="U001RAHUL:1694000000.000100",
            source_channel="C_PRODUCT_LAUNCH",
            source_timestamp=NOW - timedelta(hours=6),
            extraction_confidence=0.96,
        )
        db.add(ev_slack)

        # Evidence: Gmail (deduplicated into same commitment)
        ev_gmail = Evidence(
            commitment_id=pricing_commitment.id,
            source=EvidenceSource.GMAIL,
            extracted_person="Rahul Sharma",
            extracted_action="send revised pricing document after Finance confirmation",
            extracted_deadline_phrase=None,
            source_message_id="GMAIL:thread_pricing_001",
            source_channel="inbox",
            source_timestamp=NOW - timedelta(hours=3),
            extraction_confidence=0.89,
        )
        db.add(ev_gmail)

        # Transition history: PROPOSED → CONFIRMED → BLOCKED
        machine = CommitmentStateMachine(pricing_commitment)
        # Manually build history since we're seeding
        pricing_commitment.transition_history = [
            {
                "timestamp": (NOW - timedelta(hours=6)).isoformat(),
                "from_state": "PROPOSED",
                "to_state": "CONFIRMED",
                "trigger": "identity_resolved",
                "actor": "orchestrator",
                "evidence": {"slack_message_id": "U001RAHUL:1694000000.000100"},
            },
            {
                "timestamp": (NOW - timedelta(hours=3)).isoformat(),
                "from_state": "CONFIRMED",
                "to_state": "BLOCKED",
                "trigger": "gmail_evidence_blocker_detected",
                "actor": "orchestrator",
                "evidence": {"gmail_thread": "thread_pricing_001", "blocker": "Finance confirmation pending"},
            },
        ]

        commitments_seeded.append(pricing_commitment)

        # Store Finance blocking pattern in Supermemory (4 previous pricing commitments blocked)
        for i in range(4):
            await memory.store(
                f"Finance team blocked pricing commitment #{i+1} — discount approval pending",
                person_id=people["rahul"].id,
                commitment_id=pricing_commitment.id,
                metadata={"pattern": "finance_blocks_pricing", "instance": i + 1},
            )
        print("  [OK] Golden demo chain seeded (Rahul pricing commitment, Finance blocking pattern x4)")

        # ── OVERDUE commitment ─────────────────────────────────────────────
        overdue_c = Commitment(
            person_id=people["sarah"].id,
            commitment_text="Sarah committed to: review Q3 contracts",
            normalized_action="review Q3 contracts and send summary",
            raw_deadline="last Friday",
            resolved_deadline=NOW - timedelta(days=3),
            source_timestamp=NOW - timedelta(days=7),
            state=CommitmentState.OVERDUE,
            risk_score=0.95,
            risk_level=RiskLevel.CRITICAL,
            confidence={"extraction": 0.93, "identity": 0.99, "date_resolution": 0.85, "deduplication": 1.0, "action_selection": 0.91},
            related_task_ids=["LIN-201"],
            transition_history=[
                {"timestamp": (NOW - timedelta(days=7)).isoformat(), "from_state": "PROPOSED", "to_state": "CONFIRMED", "trigger": "extraction_complete", "actor": "orchestrator", "evidence": {}},
                {"timestamp": (NOW - timedelta(days=3)).isoformat(), "from_state": "CONFIRMED", "to_state": "OVERDUE", "trigger": "deadline_passed", "actor": "orchestrator", "evidence": {}},
            ],
        )
        db.add(overdue_c)
        await db.flush()
        db.add(Evidence(
            commitment_id=overdue_c.id,
            source=EvidenceSource.SLACK,
            extracted_person="Sarah Chen",
            extracted_action="review Q3 contracts and send summary",
            extracted_deadline_phrase="last Friday",
            source_message_id="U002SARAH:slack_001",
            extraction_confidence=0.93,
        ))
        commitments_seeded.append(overdue_c)

        # ── COMPLETED commitment ───────────────────────────────────────────
        completed_c = Commitment(
            person_id=people["ana"].id,
            commitment_text="Ana committed to: send API documentation",
            normalized_action="send updated API documentation to engineering team",
            raw_deadline="yesterday",
            resolved_deadline=NOW - timedelta(days=1),
            source_timestamp=NOW - timedelta(days=2),
            state=CommitmentState.COMPLETED,
            risk_score=0.0,
            risk_level=RiskLevel.LOW,
            confidence={"extraction": 0.98, "identity": 0.99, "date_resolution": 0.95, "deduplication": 1.0, "action_selection": 0.96},
            related_task_ids=["LIN-301"],
            transition_history=[
                {"timestamp": (NOW - timedelta(days=2)).isoformat(), "from_state": "PROPOSED", "to_state": "CONFIRMED", "trigger": "extraction_complete", "actor": "orchestrator", "evidence": {}},
                {"timestamp": (NOW - timedelta(hours=20)).isoformat(), "from_state": "CONFIRMED", "to_state": "COMPLETED", "trigger": "linear_task_marked_done", "actor": "verifier", "evidence": {"linear_issue": "LIN-301"}},
            ],
        )
        db.add(completed_c)
        await db.flush()
        commitments_seeded.append(completed_c)

        # ── AT RISK commitment ─────────────────────────────────────────────
        at_risk_c = Commitment(
            person_id=people["marcus"].id,
            commitment_text="Marcus committed to: deploy the new auth service",
            normalized_action="deploy auth service to production",
            raw_deadline="end of week",
            resolved_deadline=NOW + timedelta(hours=18),
            source_timestamp=NOW - timedelta(days=3),
            state=CommitmentState.AT_RISK,
            risk_score=0.73,
            risk_level=RiskLevel.HIGH,
            confidence={"extraction": 0.91, "identity": 0.97, "date_resolution": 0.88, "deduplication": 1.0, "action_selection": 0.90},
            related_task_ids=[],   # no Linear task = risk factor
        )
        db.add(at_risk_c)
        await db.flush()
        db.add(Evidence(
            commitment_id=at_risk_c.id,
            source=EvidenceSource.SLACK,
            extracted_person="Marcus Johnson",
            extracted_action="deploy auth service to production",
            extracted_deadline_phrase="end of week",
            source_message_id="U004MARCUS:slack_002",
            extraction_confidence=0.91,
        ))
        commitments_seeded.append(at_risk_c)

        # ── PROMPT INJECTION test commitment ───────────────────────────────
        # The injection text is in evidence — structural defense contains it
        injection_evidence = Evidence(
            commitment_id=overdue_c.id,   # attach to existing to avoid NULL FK
            source=EvidenceSource.SLACK,
            extracted_person="Unknown",
            extracted_action="[INJECTION CONTAINED — no commitment extracted]",
            extracted_deadline_phrase=None,
            source_message_id="INJECTED_MSG_001",
            source_channel="C_ENGINEERING",
            source_timestamp=NOW - timedelta(hours=1),
            extraction_confidence=0.0,
            injection_flagged=True,
            injection_flag_reason="Secondary scanner: 'ignore all previous instructions' pattern detected. Primary defense (schema enforcement) contained the injection — no data extracted.",
        )
        db.add(injection_evidence)

        # ── Pending approval action (for golden demo) ──────────────────────
        approval_action = ActionRecord(
            commitment_id=pricing_commitment.id,
            idempotency_key=f"{pricing_commitment.id}:SEND_EXTERNAL_EMAIL",
            action_type=ActionType.SEND_EXTERNAL_EMAIL,
            risk_level=RiskLevel.HIGH,
            status=ActionStatus.AWAITING_APPROVAL,
            params={
                "to": "customer@enterprise.com",
                "subject": "Update on pricing revision timeline",
                "body": "Hi,\n\nI wanted to reach out regarding the revised pricing document. Due to an internal approval process, we expect to have the final numbers to you by end of week.\n\nThank you for your patience.\n\nBest,\nRahul Sharma\nAcme Corp",
            },
            policy_decision="APPROVAL",
            policy_reason="Policy table: SEND_EXTERNAL_EMAIL is HIGH risk → APPROVAL",
        )
        db.add(approval_action)

        # ── Auto-executed actions ──────────────────────────────────────────
        auto_action_linear = ActionRecord(
            commitment_id=pricing_commitment.id,
            idempotency_key=f"{pricing_commitment.id}:CREATE_LINEAR_TASK",
            action_type=ActionType.CREATE_LINEAR_TASK,
            risk_level=RiskLevel.LOW,
            status=ActionStatus.VERIFIED,
            params={"title": "Revised pricing document — Rahul", "description": "Commitment tracked by CommitmentOS"},
            policy_decision="AUTO",
            policy_reason="Policy table: CREATE_LINEAR_TASK is LOW risk → AUTO",
            result={"linear_issue_id": "LIN-999", "url": "https://linear.app/acme/issue/LIN-999"},
            verified=True,
            verification_result={"linear_issue_id": "LIN-999", "title_verified": True, "commitment_linked": True, "state": "Todo"},
        )
        db.add(auto_action_linear)

        auto_action_slack = ActionRecord(
            commitment_id=pricing_commitment.id,
            idempotency_key=f"{pricing_commitment.id}:POST_SLACK_MESSAGE",
            action_type=ActionType.POST_SLACK_MESSAGE,
            risk_level=RiskLevel.LOW,
            status=ActionStatus.VERIFIED,
            params={"channel_id": "C_PRODUCT_LAUNCH", "text": "👋 Quick update: Rahul's pricing doc commitment is being tracked. Finance approval is the current blocker — will follow up."},
            policy_decision="AUTO",
            policy_reason="Policy table: POST_SLACK_MESSAGE is LOW risk → AUTO",
            result={"slack_ts": "1694100000.000200"},
            verified=True,
            verification_result={"slack_ts": "1694100000.000200", "posted": True},
        )
        db.add(auto_action_slack)

        await db.commit()

        print(f"  [OK] {len(commitments_seeded)} commitments seeded")
        print("  [OK] Evidence records seeded (including 1 prompt-injection test)")
        print("  [OK] 1 action awaiting approval (external email to customer)")
        print("  [OK] 2 auto-executed + verified actions (Linear task + Slack message)")
        print("  [OK] Finance blocking pattern stored in Supermemory")
        print("\n[SUCCESS] Seed complete! You can now start the demo.\n")
        print("Golden demo chain ready:")
        print(f"  Pricing commitment ID: {pricing_commitment.id}")
        print(f"  Approval action ID:    {approval_action.id}")

    await memory.close()


if __name__ == "__main__":
    asyncio.run(seed())
