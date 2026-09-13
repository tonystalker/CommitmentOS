"""
CommitmentOS — deterministic risk scorer.

Risk score is a float [0, 1]. It is computed from deterministic signals,
not from an LLM adjective. The formula is explicit and auditable.

Signals:
  - deadline_proximity:  how soon the deadline is (exponential decay)
  - progress_deficit:    no linked Linear tasks = 0 progress
  - blocker_flag:        state == BLOCKED adds a large penalty
  - historical_delay:    person's prior late-commitment rate (from memory)
"""
from __future__ import annotations

from datetime import datetime, timezone

from commitments.models import Commitment, CommitmentState, RiskLevel


# ─────────────────────────────────────────────────────────────────────────────
# Weights (tune via eval, do not hardcode blindly)
# ─────────────────────────────────────────────────────────────────────────────

W_DEADLINE = 0.40
W_PROGRESS = 0.30
W_BLOCKER = 0.20
W_HISTORY = 0.10

DECAY_HALF_LIFE_HOURS = 48.0   # deadline ≤ 48h → score approaches 1.0


def score_deadline_proximity(resolved_deadline: datetime | None, now: datetime) -> float:
    """
    Returns 0.0 (deadline far away / no deadline) → 1.0 (deadline passed).
    Uses exponential decay so urgency increases non-linearly as deadline approaches.
    """
    if resolved_deadline is None:
        return 0.1   # unknown deadline is mildly risky

    # Normalize both datetimes to UTC to prevent offset-naive vs offset-aware errors
    dl_utc = resolved_deadline if resolved_deadline.tzinfo else resolved_deadline.replace(tzinfo=timezone.utc)
    now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)

    hours_remaining = (dl_utc - now_utc).total_seconds() / 3600.0

    if hours_remaining <= 0:
        return 1.0   # overdue

    # Exponential: score = 1 - exp(-ln(2) * (1/hours_remaining) * half_life)
    # Simplified: score = 1 - 2^(-half_life / hours_remaining)
    return 1.0 - pow(2, -DECAY_HALF_LIFE_HOURS / max(hours_remaining, 0.5))


def score_progress_deficit(commitment: Commitment) -> float:
    """
    0.0 = has linked tasks  →  1.0 = no tasks linked at all.
    """
    if commitment.related_task_ids:
        return 0.0
    return 1.0


def score_blocker(commitment: Commitment) -> float:
    return 1.0 if commitment.state == CommitmentState.BLOCKED else 0.0


def risk_level_from_score(score: float) -> RiskLevel:
    if score >= 0.75:
        return RiskLevel.CRITICAL
    if score >= 0.55:
        return RiskLevel.HIGH
    if score >= 0.35:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class RiskScorer:
    """
    Computes a deterministic risk score for a commitment.

    historical_delay_rate: fraction of past commitments by this person that were
    delivered late. Pass 0.0 if no history is available.
    """

    def score(
        self,
        commitment: Commitment,
        *,
        historical_delay_rate: float = 0.0,
    ) -> tuple[float, RiskLevel]:
        now = datetime.now(timezone.utc)

        d = score_deadline_proximity(commitment.resolved_deadline, now)
        p = score_progress_deficit(commitment)
        b = score_blocker(commitment)
        h = min(max(historical_delay_rate, 0.0), 1.0)

        raw = W_DEADLINE * d + W_PROGRESS * p + W_BLOCKER * b + W_HISTORY * h
        score = min(max(raw, 0.0), 1.0)
        level = risk_level_from_score(score)

        return score, level

    def apply(
        self,
        commitment: Commitment,
        *,
        historical_delay_rate: float = 0.0,
    ) -> None:
        """Compute and write risk_score + risk_level onto the commitment object."""
        score, level = self.score(commitment, historical_delay_rate=historical_delay_rate)
        commitment.risk_score = score
        commitment.risk_level = level
