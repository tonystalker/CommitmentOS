"""
CommitmentOS — deterministic state machine.

Transitions are never decided by the LLM. Every transition is logged as an
append-only event: {timestamp, from_state, to_state, trigger, evidence, actor}.
"""
from datetime import datetime, timezone
from typing import Any

from commitments.models import Commitment, CommitmentState


# ─────────────────────────────────────────────────────────────────────────────
# Allowed transitions
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_TRANSITIONS: dict[CommitmentState, set[CommitmentState]] = {
    CommitmentState.PROPOSED: {
        CommitmentState.CONFIRMED,
        CommitmentState.CANCELLED,
    },
    CommitmentState.CONFIRMED: {
        CommitmentState.AT_RISK,
        CommitmentState.BLOCKED,
        CommitmentState.COMPLETED,
        CommitmentState.CANCELLED,
    },
    CommitmentState.AT_RISK: {
        CommitmentState.OVERDUE,
        CommitmentState.COMPLETED,
        CommitmentState.CANCELLED,
    },
    CommitmentState.BLOCKED: {
        CommitmentState.CONFIRMED,   # unblocked
        CommitmentState.OVERDUE,
        CommitmentState.CANCELLED,
    },
    CommitmentState.OVERDUE: {
        CommitmentState.COMPLETED,
        CommitmentState.CANCELLED,
    },
    CommitmentState.COMPLETED: set(),   # terminal
    CommitmentState.CANCELLED: set(),   # terminal
}


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""


# ─────────────────────────────────────────────────────────────────────────────
# State machine
# ─────────────────────────────────────────────────────────────────────────────

class CommitmentStateMachine:
    """
    Deterministic state machine for Commitment objects.

    Usage:
        machine = CommitmentStateMachine(commitment)
        machine.transition(CommitmentState.CONFIRMED, trigger="identity_resolved", actor="orchestrator")
    """

    def __init__(self, commitment: Commitment) -> None:
        self.commitment = commitment

    def can_transition(self, to_state: CommitmentState) -> bool:
        return to_state in ALLOWED_TRANSITIONS.get(self.commitment.state, set())

    def transition(
        self,
        to_state: CommitmentState,
        trigger: str,
        actor: str = "system",
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform a state transition and append it to transition_history.
        Raises InvalidTransitionError if the transition is not allowed.
        Returns the transition event dict.
        """
        if not self.can_transition(to_state):
            raise InvalidTransitionError(
                f"Cannot transition from {self.commitment.state!r} to {to_state!r}. "
                f"Allowed: {ALLOWED_TRANSITIONS.get(self.commitment.state, set())}"
            )

        event: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_state": self.commitment.state,
            "to_state": to_state,
            "trigger": trigger,
            "actor": actor,
            "evidence": evidence or {},
        }

        # Append-only — never overwrite
        history: list = list(self.commitment.transition_history or [])
        history.append(event)
        self.commitment.transition_history = history

        self.commitment.state = to_state
        self.commitment.updated_at = datetime.now(timezone.utc)

        return event

    def get_history(self) -> list[dict[str, Any]]:
        return list(self.commitment.transition_history or [])


# ─────────────────────────────────────────────────────────────────────────────
# Risk-based auto-transitions (called by the risk scorer / orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_auto_transitions(commitment: Commitment) -> CommitmentState | None:
    """
    Determine if a commitment should auto-transition based on deterministic rules.
    Returns the suggested new state, or None if no transition is needed.
    Called by the orchestrator — transition is only applied if policy allows.
    """
    now = datetime.now(timezone.utc)
    state = commitment.state
    deadline = commitment.resolved_deadline
    risk_score = commitment.risk_score

    # Already terminal — nothing to do
    if state in (CommitmentState.COMPLETED, CommitmentState.CANCELLED):
        return None

    # Overdue: past deadline and not done
    if deadline:
        dl_utc = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        if dl_utc < now and state not in (CommitmentState.OVERDUE, CommitmentState.COMPLETED):
            if CommitmentStateMachine(commitment).can_transition(CommitmentState.OVERDUE):
                return CommitmentState.OVERDUE

    # AT_RISK: high risk score, confirmed, not yet flagged
    if state == CommitmentState.CONFIRMED and risk_score is not None and risk_score >= 0.7:
        return CommitmentState.AT_RISK

    return None
