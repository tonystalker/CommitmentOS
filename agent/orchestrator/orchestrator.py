"""
CommitmentOS — Main Orchestrator.

Wires the full commitment recovery loop:
  OBSERVE → EXTRACT → RESOLVE → DEDUP → RISK → MEMORY → PLAN → POLICY → ACT → VERIFY → TRACE

Emits Server-Sent Events at each stage for streaming progress in the UI.
Each stage event: {"stage": "...", "detail": "...", "data": {...}}

Key architectural rule:
  LLM proposes (extractor, planner).
  Policy engine authorizes.
  Executor acts.
  Verifier marks done.
  Orchestrator coordinates — it never decides.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent.extraction.extractor import extract_from_messages
from agent.executor.executor import Executor
from agent.planner.planner import plan_actions
from agent.policy.engine import PolicyDecision, PolicyEngine
from agent.verifier.verifier import Verifier
from commitments.dedup import DeduplicationService
from commitments.identity import IdentityService
from commitments.models import (
    Commitment, CommitmentState, Evidence, EvidenceSource,
    TraceStep,
)
from commitments.risk import RiskScorer
from commitments.state_machine import CommitmentStateMachine, evaluate_auto_transitions
from integrations.gmail.client import GmailClient
from integrations.linear.client import LinearClient
from integrations.slack.client import SlackClient
from memory.supermemory import SupermemoryService
from security.extraction_guard import ExtractionGuard

logger = logging.getLogger(__name__)

SseEvent = dict[str, Any]


class Orchestrator:
    """
    Runs the full CommitmentOS loop.
    Yields SSE events (dicts) for streaming to the frontend.
    """

    def __init__(
        self,
        db: AsyncSession,
        slack_client: SlackClient,
        gmail_client: GmailClient,
        linear_client: LinearClient,
        memory: SupermemoryService,
        policy_engine: PolicyEngine,
    ) -> None:
        self.db = db
        self.slack = slack_client
        self.gmail = gmail_client
        self.linear = linear_client
        self.memory = memory
        self.policy = policy_engine
        self.identity = IdentityService(db)
        self.dedup = DeduplicationService(db)
        self.risk_scorer = RiskScorer()
        self.guard = ExtractionGuard()
        self.executor = Executor(db, slack_client, linear_client, gmail_client)
        self.verifier = Verifier(db, linear_client, slack_client)

    async def run(
        self,
        *,
        user_request: str,
        slack_channel_ids: list[str],
        gmail_query: str = "is:unread",
        message_limit: int = 50,
    ) -> AsyncGenerator[SseEvent, None]:
        """
        Main entry point. Yields SSE events throughout.
        Usage: async for event in orchestrator.run(...): stream(event)
        """

        # ── Stage: OBSERVE ─────────────────────────────────────────────────
        yield self._event("OBSERVE", "Scanning Slack and Gmail for messages…")

        slack_messages = []
        for channel_id in slack_channel_ids:
            msgs = await self.slack.get_channel_messages(channel_id, limit=message_limit)
            slack_messages.extend(msgs)

        gmail_limit = max(1, min(message_limit, 10))
        gmail_threads = self.gmail.get_threads(gmail_query, max_results=gmail_limit)
        gmail_messages = [
            msg for thread in gmail_threads for msg in thread.messages
        ][:message_limit]

        total_messages = len(slack_messages) + len(gmail_messages)
        yield self._event("OBSERVE", f"Found {total_messages} messages ({len(slack_messages)} Slack, {len(gmail_messages)} Gmail)", {
            "slack_count": len(slack_messages),
            "gmail_count": len(gmail_messages),
        })

        # ── Stage: EXTRACT ─────────────────────────────────────────────────
        yield self._event("EXTRACT", "Extracting commitments from messages…")

        all_messages = [
            {
                "text": msg.text,
                "source_timestamp": msg.timestamp,
                "channel_id": msg.channel_id,
                "message_id": msg.message_id,
                "user_name": msg.user_name,
                "user_id": msg.user_id,
                "source": "SLACK",
            }
            for msg in slack_messages
        ] + [
            {
                "text": msg.body,
                "source_timestamp": msg.timestamp,
                "channel_id": msg.thread_id,
                "message_id": msg.message_id,
                "user_name": msg.sender,
                "user_id": msg.sender,
                "source": "GMAIL",
            }
            for msg in gmail_messages
        ]

        extraction_results = await extract_from_messages(all_messages)
        raw_commitments = [
            (msg, c)
            for msg, res in zip(all_messages, extraction_results)
            for c in res.commitments
        ]

        # Secondary belt-and-suspenders scan (primary defense is structural)
        flagged_count = 0
        for msg, _ in raw_commitments:
            txt = str(msg.get("text", ""))
            flag = self.guard.scan(txt)
            if flag.flagged:
                flagged_count += 1
                logger.warning("ExtractionGuard flagged message_id=%s: %s", msg.get("message_id", ""), flag.reason)

        yield self._event("EXTRACT", f"Extracted {len(raw_commitments)} commitments from {total_messages} messages" + (f" ({flagged_count} messages flagged by secondary scanner)" if flagged_count else ""), {
            "commitment_count": len(raw_commitments),
            "flagged_count": flagged_count,
        })

        if not raw_commitments:
            yield self._event("DONE", "No commitments found.", {"total": 0})
            return

        # ── Stage: RESOLVE ─────────────────────────────────────────────────
        yield self._event("RESOLVE", "Resolving identities and dates…")

        resolved = []
        needs_review = []

        for msg, extracted in raw_commitments:
            user_id_val = msg.get("user_id")
            user_name_val = msg.get("user_name")
            slack_id = str(user_id_val) if msg.get("source") == "SLACK" and user_id_val else None
            email_val = str(user_name_val) if isinstance(user_name_val, str) and "@" in user_name_val else None

            identity_result = await self.identity.resolve(
                display_name=extracted.person_name,
                slack_user_id=slack_id,
                email=email_val,
            )

            if identity_result.requires_human_review or not identity_result.person:
                display_name = extracted.person_name if (extracted.person_name and extracted.person_name != "Unknown") else (str(user_name_val) if user_name_val else "Teammate")
                person = await self.identity.get_or_create(
                    display_name=display_name,
                    slack_user_id=slack_id,
                    email=email_val,
                )
                identity_result.person = person
                needs_review.append({"extracted": extracted, "msg": msg, "identity": identity_result})

            resolved.append((msg, extracted, identity_result))

        yield self._event("RESOLVE", f"Resolved {len(resolved)} identities; {len(needs_review)} need human review", {
            "resolved": len(resolved),
            "needs_review": len(needs_review),
        })

        # ── Stage: DEDUP ───────────────────────────────────────────────────
        yield self._event("DEDUP", "Deduplicating commitments across Slack and Gmail…")

        unique_commitments: list[Commitment] = []
        merged_count = 0

        for msg, extracted, identity_result in resolved:
            person = identity_result.person
            if not person:
                continue

            # Resolve date
            anchor_val = msg.get("source_timestamp")
            anchor_dt = anchor_val if isinstance(anchor_val, datetime) else None
            resolved_deadline = self._resolve_date(
                extracted.deadline_phrase,
                anchor=anchor_dt,
            )

            duplicate = await self.dedup.find_duplicate(
                person_id=person.id,
                normalized_action=extracted.action,
                resolved_deadline=resolved_deadline,
            )

            # Build evidence record
            evidence = Evidence(
                commitment_id="",   # will be set during merge or create
                source=EvidenceSource(msg.get("source", "SLACK")),
                extracted_person=extracted.person_name,
                extracted_action=extracted.action,
                extracted_deadline_phrase=extracted.deadline_phrase,
                source_message_id=msg.get("message_id"),
                source_channel=msg.get("channel_id"),
                source_timestamp=msg.get("source_timestamp"),
                extraction_confidence=extracted.confidence.get("extraction", 0.0),
            )

            if duplicate:
                await self.dedup.merge_evidence(duplicate, evidence, extracted.confidence)
                merged_count += 1
            else:
                # Create new commitment
                commitment = Commitment(
                    person_id=person.id,
                    commitment_text=f"{extracted.person_name} committed to: {extracted.action}",
                    normalized_action=extracted.action,
                    raw_deadline=extracted.deadline_phrase,
                    resolved_deadline=resolved_deadline,
                    source_timestamp=msg.get("source_timestamp"),
                    timezone=person.timezone,
                    state=CommitmentState.PROPOSED,
                    confidence=extracted.confidence,
                )
                self.db.add(commitment)
                await self.db.flush()
                evidence.commitment_id = commitment.id
                self.db.add(evidence)
                await self.db.flush()

                # Store evidence in Supermemory
                doc_id = await self.memory.store(
                    f"{extracted.person_name} committed: {extracted.action}" + (
                        f" by {extracted.deadline_phrase}" if extracted.deadline_phrase else ""
                    ),
                    person_id=person.id,
                    commitment_id=commitment.id,
                )
                commitment.supermemory_doc_id = doc_id

                unique_commitments.append(commitment)

        await self.db.flush()

        yield self._event("DEDUP", f"{len(unique_commitments)} unique commitments; {merged_count} duplicates merged", {
            "unique": len(unique_commitments),
            "merged": merged_count,
        })

        # ── Load ALL active commitments (new + existing) for RISK/PLAN/ACT ──
        # unique_commitments only contains newly created ones. We must re-score
        # ALL active commitments every loop — including ones merged as duplicates.
        from sqlalchemy import select as _sa_select
        _active_stmt = _sa_select(Commitment).where(
            Commitment.state.not_in([CommitmentState.COMPLETED, CommitmentState.CANCELLED])
        )
        _active_result = await self.db.execute(_active_stmt)
        all_active_commitments: list[Commitment] = list(_active_result.scalars().all())

        # ── Stage: RISK ────────────────────────────────────────────────────
        yield self._event("RISK", "Scoring risk for each commitment…")

        at_risk = 0
        blocked = 0

        for commitment in all_active_commitments:
            # Auto-transition PROPOSED → CONFIRMED
            machine = CommitmentStateMachine(commitment)
            if machine.can_transition(CommitmentState.CONFIRMED):
                machine.transition(CommitmentState.CONFIRMED, trigger="extraction_complete", actor="orchestrator")

            # Score risk
            self.risk_scorer.apply(commitment)

            # Auto-transition based on risk
            suggested = evaluate_auto_transitions(commitment)
            if suggested and machine.can_transition(suggested):
                machine.transition(suggested, trigger="auto_risk_evaluation", actor="orchestrator")

            if commitment.state == CommitmentState.AT_RISK:
                at_risk += 1
            elif commitment.state == CommitmentState.BLOCKED:
                blocked += 1

        await self.db.flush()

        yield self._event("RISK", f"{len(all_active_commitments)} scored: {at_risk} at risk, {blocked} blocked", {
            "total": len(all_active_commitments),
            "at_risk": at_risk,
            "blocked": blocked,
        })

        # ── Stage: PLAN ────────────────────────────────────────────────────
        yield self._event("PLAN", "Planning recovery actions…")

        plans = []
        for commitment in all_active_commitments:
            if commitment.state not in (CommitmentState.AT_RISK, CommitmentState.BLOCKED, CommitmentState.OVERDUE):
                continue

            # Search memory for context
            memory_results = await self.memory.search(
                f"{commitment.normalized_action} commitment delay history",
                limit=5,
            )

            # Get person name (we need to query it)
            from sqlalchemy import select as sa_select
            from commitments.models import Person
            person_result = await self.db.execute(sa_select(Person).where(Person.id == commitment.person_id))
            person = person_result.scalar_one_or_none()
            person_name = person.display_name if person else "Unknown"

            plan = await plan_actions(
                commitment,
                person_name=person_name,
                user_request=user_request,
                memory_context=memory_results,
            )
            plans.append(plan)

            # Add trace step
            self.db.add(TraceStep(
                commitment_id=commitment.id,
                stage="PLAN",
                detail=f"Proposed {len(plan.proposed_actions)} actions",
                data={"actions": [a.action_type.value for a in plan.proposed_actions]},
            ))

        await self.db.flush()
        total_proposed = sum(len(p.proposed_actions) for p in plans)
        yield self._event("PLAN", f"{total_proposed} actions proposed across {len(plans)} commitments", {
            "plans": len(plans),
            "total_actions": total_proposed,
        })

        # ── Stage: POLICY ──────────────────────────────────────────────────
        yield self._event("POLICY", "Evaluating actions through policy engine…")

        auto_count = 0
        approval_count = 0
        blocked_count = 0
        execution_queue = []

        for plan in plans:
            for action in plan.proposed_actions:
                policy_result = self.policy.evaluate(action.action_type)
                if policy_result.decision == PolicyDecision.AUTO:
                    auto_count += 1
                    execution_queue.append((action, policy_result))
                elif policy_result.decision == PolicyDecision.APPROVAL:
                    approval_count += 1
                    execution_queue.append((action, policy_result))
                else:
                    blocked_count += 1

        yield self._event("POLICY", f"{auto_count} auto-authorized, {approval_count} held for approval, {blocked_count} blocked", {
            "auto": auto_count,
            "approval": approval_count,
            "blocked": blocked_count,
        })

        # ── Stage: ACT ─────────────────────────────────────────────────────
        yield self._event("ACT", f"Executing {auto_count} auto-authorized actions…")

        executed = []
        held_for_approval = []
        failed = []

        commitment_map = {c.id: c for c in all_active_commitments}

        for action, policy_result in execution_queue:
            target_commitment: Commitment | None = commitment_map.get(action.commitment_id)
            if target_commitment is None:
                continue

            exec_result = await self.executor.execute(action, policy_result, target_commitment)

            if exec_result.awaiting_approval:
                held_for_approval.append(exec_result)
            elif exec_result.success:
                executed.append(exec_result)
            else:
                failed.append(exec_result)

            # Add trace step
            self.db.add(TraceStep(
                commitment_id=action.commitment_id,
                stage="ACT",
                detail=f"{action.action_type.value}: {'success' if exec_result.success else 'awaiting_approval' if exec_result.awaiting_approval else 'failed'}",
                data={"action_record_id": exec_result.action_record_id},
            ))

        await self.db.flush()

        yield self._event("ACT", f"{len(executed)} executed, {len(held_for_approval)} held for approval, {len(failed)} failed", {
            "executed": len(executed),
            "held_for_approval": len(held_for_approval),
            "failed": len(failed),
        })

        # ── Stage: VERIFY ──────────────────────────────────────────────────
        yield self._event("VERIFY", f"Verifying {len(executed)} executed actions…")

        verified_count = 0
        verification_failed = []

        verify_tasks = [self.verifier.verify(r.action_record_id) for r in executed]
        verification_results = await asyncio.gather(*verify_tasks, return_exceptions=True)

        for result, exec_result in zip(verification_results, executed):
            if isinstance(result, Exception):
                verification_failed.append(exec_result.action_record_id)
            elif result:
                verified_count += 1
            else:
                verification_failed.append(exec_result.action_record_id)

        await self.db.flush()

        yield self._event("VERIFY", f"{verified_count} of {len(executed)} actions verified ✓", {
            "verified": verified_count,
            "failed": len(verification_failed),
        })

        # ── Stage: DONE ────────────────────────────────────────────────────
        yield self._event("DONE", f"Loop complete. {len(all_active_commitments)} commitments tracked, {verified_count} actions verified.", {
            "commitments": len(all_active_commitments),
            "at_risk": at_risk,
            "blocked": blocked,
            "actions_verified": verified_count,
            "held_for_approval": len(held_for_approval),
            "commitment_ids": [c.id for c in all_active_commitments],
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _event(self, stage: str, detail: str, data: dict | None = None) -> SseEvent:
        return {
            "stage": stage,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }

    def _resolve_date(self, phrase: str | None, *, anchor: datetime | None) -> datetime | None:
        """
        Resolve a relative date phrase to an absolute datetime.
        Never resolves without an anchor timestamp — returns None if anchor is missing.
        Stores raw_deadline for audit; resolved_deadline for computation.
        """
        if not phrase:
            return None
        if not anchor:
            logger.warning("Cannot resolve date phrase '%s' without anchor timestamp", phrase)
            return None

        from dateutil.parser import parse as dateutil_parse
        from dateutil.relativedelta import relativedelta

        # Ensure anchor is UTC-aware
        anchor_utc = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
        phrase_lower = phrase.lower().strip()

        try:
            res: datetime | None = None
            if "tomorrow" in phrase_lower:
                res = (anchor_utc + relativedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
            elif "today" in phrase_lower:
                res = anchor_utc.replace(hour=17, minute=0, second=0, microsecond=0)
            elif "end of week" in phrase_lower or "eow" in phrase_lower or "friday" in phrase_lower:
                days_until_friday = (4 - anchor_utc.weekday()) % 7 or 7
                res = (anchor_utc + relativedelta(days=days_until_friday)).replace(hour=17, minute=0, second=0, microsecond=0)
            else:
                # Try dateutil for specific dates
                parsed = dateutil_parse(phrase, default=anchor_utc)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed < anchor_utc:
                    parsed = parsed + relativedelta(years=1)   # assume next occurrence
                res = parsed

            if res and res.tzinfo is None:
                res = res.replace(tzinfo=timezone.utc)
            return res
        except Exception:
            logger.warning("Could not resolve date phrase: %s", phrase)
            return None
