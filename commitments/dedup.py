"""
CommitmentOS — deduplication service.

Two commitments are merged when:
  - Same person (resolved canonical person_id)
  - Similar deadline (within 24h of each other)
  - Semantic similarity above threshold (via Supermemory search or text similarity)

When merged, the earlier commitment absorbs the new evidence.
Confidence scores are updated to reflect the combined evidence.
"""
from __future__ import annotations

import difflib
from datetime import timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commitments.models import Commitment, CommitmentState, Evidence

if TYPE_CHECKING:
    pass

SEMANTIC_SIMILARITY_THRESHOLD = 0.70
DEADLINE_WINDOW_HOURS = 24


class DeduplicationService:
    """
    Checks a new (not-yet-persisted) commitment against existing ones.
    Returns the existing commitment to merge into, or None if it's unique.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_duplicate(
        self,
        person_id: str,
        normalized_action: str,
        resolved_deadline,   # datetime | None
    ) -> Commitment | None:
        """
        Finds an existing non-cancelled, non-completed commitment that is a
        probable duplicate of the described one.
        """
        stmt = select(Commitment).where(
            Commitment.person_id == person_id,
            Commitment.state.not_in([CommitmentState.COMPLETED, CommitmentState.CANCELLED]),
        )
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        for existing in candidates:
            # ── Deadline proximity check ──────────────────────────────────────
            if resolved_deadline and existing.resolved_deadline:
                # Normalize both to UTC-aware to avoid offset-naive vs offset-aware TypeError
                def _to_utc(dt):
                    if dt.tzinfo is None:
                        return dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)

                diff_hours = abs(
                    (_to_utc(resolved_deadline) - _to_utc(existing.resolved_deadline)).total_seconds() / 3600
                )
                if diff_hours > DEADLINE_WINDOW_HOURS:
                    continue
            elif resolved_deadline != existing.resolved_deadline:
                # One has deadline, the other doesn't — not a dupe
                continue

            # ── Text similarity check ─────────────────────────────────────────
            similarity = difflib.SequenceMatcher(
                None,
                normalized_action.lower(),
                existing.normalized_action.lower(),
            ).ratio()

            if similarity >= SEMANTIC_SIMILARITY_THRESHOLD:
                return existing

        return None

    async def merge_evidence(
        self,
        existing_commitment: Commitment,
        new_evidence: Evidence,
        new_confidence: dict[str, float],
    ) -> None:
        """
        Absorb new_evidence into an existing commitment.
        Updates confidence scores (take element-wise maximum).
        """
        new_evidence.commitment_id = existing_commitment.id
        self.db.add(new_evidence)

        # Update confidence — take max of each dimension
        updated_confidence = {
            k: max(existing_commitment.confidence.get(k, 0.0), new_confidence.get(k, 0.0))
            for k in set(existing_commitment.confidence) | set(new_confidence)
        }
        existing_commitment.confidence = updated_confidence
        await self.db.flush()
