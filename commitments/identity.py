"""
CommitmentOS — Identity resolution service.

Resolution order (never silently guess between two plausible people):
  1. Exact canonical person_id match
  2. Exact email match
  3. Exact Slack user_id match
  4. Exact Linear username match
  5. App metadata (display_name exact match)
  6. Fuzzy candidate (low confidence — triggers human review, no auto-action)
  7. Unknown — human review required
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from commitments.models import Person

if TYPE_CHECKING:
    pass


@dataclass
class IdentityResolutionResult:
    person: Person | None
    confidence: float
    method: str          # "exact_id" | "email" | "slack_id" | "linear" | "display_name" | "fuzzy" | "unknown"
    requires_human_review: bool
    candidates: list[Person] = field(default_factory=list)
    reason: str = ""


class IdentityService:
    """
    Resolves an extracted name/handle/email to a canonical Person.
    Returns a structured result — never raises on ambiguity, always surfaces it.
    """

    FUZZY_THRESHOLD = 0.75   # minimum similarity ratio for a fuzzy match

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve(
        self,
        *,
        person_id: str | None = None,
        email: str | None = None,
        slack_user_id: str | None = None,
        linear_username: str | None = None,
        display_name: str | None = None,
    ) -> IdentityResolutionResult:
        """
        Attempt identity resolution using the provided signals, in priority order.
        At most one non-None signal needed; more signals = higher confidence.
        """

        # ── 1-5. Combined Exact Match Query (Single DB roundtrip) ─────────────
        clauses = []
        if person_id:
            clauses.append(Person.id == person_id)
        if email:
            clauses.append(Person.email == email.lower())
        if slack_user_id:
            clauses.append(Person.slack_user_id == slack_user_id)
        if linear_username:
            clauses.append(Person.linear_username == linear_username)
        if display_name:
            clauses.append(Person.display_name == display_name)

        if clauses:
            stmt = select(Person).where(or_(*clauses))
            result = await self.db.execute(stmt)
            candidates = list(result.scalars().all())

            # Evaluate matches in deterministic priority order
            if person_id:
                for p in candidates:
                    if str(p.id) == str(person_id):
                        return IdentityResolutionResult(
                            person=p, confidence=1.0, method="exact_id",
                            requires_human_review=False,
                            reason=f"Matched by canonical person_id={person_id}",
                        )

            if email:
                email_lower = email.lower()
                for p in candidates:
                    if p.email and p.email.lower() == email_lower:
                        return IdentityResolutionResult(
                            person=p, confidence=0.99, method="email",
                            requires_human_review=False,
                            reason=f"Matched by email={email}",
                        )

            if slack_user_id:
                for p in candidates:
                    if p.slack_user_id == slack_user_id:
                        return IdentityResolutionResult(
                            person=p, confidence=0.99, method="slack_id",
                            requires_human_review=False,
                            reason=f"Matched by slack_user_id={slack_user_id}",
                        )

            if linear_username:
                for p in candidates:
                    if p.linear_username == linear_username:
                        return IdentityResolutionResult(
                            person=p, confidence=0.97, method="linear",
                            requires_human_review=False,
                            reason=f"Matched by linear_username={linear_username}",
                        )

            if display_name:
                name_matches = [p for p in candidates if p.display_name == display_name]
                if len(name_matches) == 1:
                    return IdentityResolutionResult(
                        person=name_matches[0], confidence=0.90, method="display_name",
                        requires_human_review=False,
                        reason=f"Matched by exact display_name={display_name!r}",
                    )
                if len(name_matches) > 1:
                    return IdentityResolutionResult(
                        person=None, confidence=0.0, method="display_name",
                        requires_human_review=True,
                        candidates=name_matches,
                        reason=f"Multiple people match display_name={display_name!r} — human review required",
                    )

        # ── 6. Fuzzy display name ────────────────────────────────────────────
        if display_name:
            all_persons_result = await self.db.execute(select(Person))
            all_persons = all_persons_result.scalars().all()

            scored = [
                (p, difflib.SequenceMatcher(None, display_name.lower(), p.display_name.lower()).ratio())
                for p in all_persons
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

            best_score = scored[0][1] if scored else 0.0
            best_match = scored[0][0] if scored else None

            # Check for tie at the top
            top_candidates = [p for p, s in scored if s >= self.FUZZY_THRESHOLD]

            if best_score >= self.FUZZY_THRESHOLD and len(top_candidates) == 1:
                confidence = 0.6 + (best_score - self.FUZZY_THRESHOLD) * 1.0   # [0.6, 0.85)
                return IdentityResolutionResult(
                    person=best_match, confidence=min(confidence, 0.84),
                    method="fuzzy",
                    requires_human_review=True,   # fuzzy always requires human review before acting
                    candidates=top_candidates,
                    reason=f"Fuzzy match on display_name (score={best_score:.2f}) — human review recommended",
                )

            if len(top_candidates) > 1:
                return IdentityResolutionResult(
                    person=None, confidence=0.0, method="fuzzy",
                    requires_human_review=True,
                    candidates=top_candidates,
                    reason=f"Multiple fuzzy matches for {display_name!r} — human review required",
                )

        # ── 7. Unknown ───────────────────────────────────────────────────────
        return IdentityResolutionResult(
            person=None, confidence=0.0, method="unknown",
            requires_human_review=True,
            reason="No identity match found — human review required",
        )

    async def get_or_create(
        self,
        display_name: str,
        *,
        email: str | None = None,
        slack_user_id: str | None = None,
        linear_username: str | None = None,
        timezone: str = "UTC",
    ) -> Person:
        """
        Used during seeding and integration setup. Creates a person if not found.
        Not used in the live agent pipeline (which always resolves first).
        """
        result = await self.resolve(
            email=email,
            slack_user_id=slack_user_id,
            linear_username=linear_username,
            display_name=display_name,
        )
        if result.person:
            return result.person

        if email:
            existing = await self.db.execute(select(Person).where(Person.email == email.lower()))
            p = existing.scalar_one_or_none()
            if p:
                return p
        if slack_user_id:
            existing = await self.db.execute(select(Person).where(Person.slack_user_id == slack_user_id))
            p = existing.scalar_one_or_none()
            if p:
                return p

        person = Person(
            display_name=display_name,
            email=email.lower() if email else None,
            slack_user_id=slack_user_id,
            linear_username=linear_username,
            timezone=timezone,
        )
        self.db.add(person)
        await self.db.flush()
        return person
