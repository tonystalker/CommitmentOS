"""
CommitmentOS — Policy engine.

The policy table is the ONLY mechanism that authorizes actions.
The LLM never modifies these mappings — only a human does (via API or UI).

Default policy table (from plan.md §5):
  Action                   | Risk     | Default
  Create Linear task       | Low      | AUTO
  Update Linear status     | Low      | AUTO
  Post Slack message       | Low      | AUTO
  Create reminder          | Low      | AUTO
  Assign task              | Medium   | APPROVAL
  Send external email      | High     | APPROVAL
  Reschedule meeting       | High     | APPROVAL
  Financial action         | Critical | BLOCK
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from commitments.models import ActionType, RiskLevel

logger = logging.getLogger(__name__)


class PolicyDecision(str, Enum):
    AUTO = "AUTO"
    APPROVAL = "APPROVAL"
    BLOCK = "BLOCK"


@dataclass
class PolicyResult:
    decision: PolicyDecision
    reason: str
    action_type: ActionType
    risk_level: RiskLevel


# ─────────────────────────────────────────────────────────────────────────────
# Default policy table — human-editable, LLM-immutable
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_POLICY_TABLE: dict[ActionType, tuple[RiskLevel, PolicyDecision]] = {
    ActionType.CREATE_LINEAR_TASK:    (RiskLevel.LOW,      PolicyDecision.AUTO),
    ActionType.UPDATE_LINEAR_STATUS:  (RiskLevel.LOW,      PolicyDecision.AUTO),
    ActionType.POST_SLACK_MESSAGE:    (RiskLevel.LOW,      PolicyDecision.AUTO),
    ActionType.CREATE_REMINDER:       (RiskLevel.LOW,      PolicyDecision.AUTO),
    ActionType.ASSIGN_TASK:           (RiskLevel.MEDIUM,   PolicyDecision.APPROVAL),
    ActionType.SEND_EXTERNAL_EMAIL:   (RiskLevel.HIGH,     PolicyDecision.APPROVAL),
    ActionType.RESCHEDULE_MEETING:    (RiskLevel.HIGH,     PolicyDecision.APPROVAL),
    ActionType.FINANCIAL_ACTION:      (RiskLevel.CRITICAL, PolicyDecision.BLOCK),
}


class PolicyEngine:
    """
    Deterministic policy evaluation.

    evaluate() → PolicyResult.
    The LLM may propose actions; this engine authorizes them.
    No action reaches the executor without passing through here.
    """

    def __init__(self, overrides: dict[ActionType, tuple[RiskLevel, PolicyDecision]] | None = None) -> None:
        # Start from defaults; overrides are human-applied (e.g. from DB PolicyRule records)
        self._table = dict(DEFAULT_POLICY_TABLE)
        if overrides:
            self._table.update(overrides)

    def evaluate(self, action_type: ActionType) -> PolicyResult:
        """
        Return the policy decision for an action type.
        Always returns a result — BLOCK on unknown action types (fail-closed).
        """
        if action_type not in self._table:
            logger.warning("Unknown action_type=%s — defaulting to BLOCK", action_type)
            return PolicyResult(
                decision=PolicyDecision.BLOCK,
                reason=f"Unknown action type '{action_type}' — blocked by default (fail-closed)",
                action_type=action_type,
                risk_level=RiskLevel.CRITICAL,
            )

        risk_level, decision = self._table[action_type]
        return PolicyResult(
            decision=decision,
            reason=f"Policy table: {action_type} is {risk_level} risk → {decision}",
            action_type=action_type,
            risk_level=risk_level,
        )

    def update_rule(self, action_type: ActionType, risk_level: RiskLevel, decision: PolicyDecision) -> None:
        """Update a policy rule. Only called by a human-facing API endpoint."""
        old = self._table.get(action_type)
        self._table[action_type] = (risk_level, decision)
        logger.info(
            "Policy rule updated by human: %s %s → %s → %s (was %s)",
            action_type, risk_level, decision, old,
        )

    def get_all_rules(self) -> list[dict]:
        """Return the full policy table for display in the UI."""
        return [
            {
                "action_type": action_type,
                "risk_level": risk_level,
                "default_decision": decision,
                "description": self._descriptions.get(action_type, ""),
            }
            for action_type, (risk_level, decision) in self._table.items()
        ]

    _descriptions: dict[ActionType, str] = {
        ActionType.CREATE_LINEAR_TASK: "Create a new issue in Linear",
        ActionType.UPDATE_LINEAR_STATUS: "Update the status of an existing Linear issue",
        ActionType.POST_SLACK_MESSAGE: "Post a message to a Slack channel or DM",
        ActionType.CREATE_REMINDER: "Create an internal reminder",
        ActionType.ASSIGN_TASK: "Assign a Linear task to someone",
        ActionType.SEND_EXTERNAL_EMAIL: "Send an email to an external recipient",
        ActionType.RESCHEDULE_MEETING: "Reschedule a customer or external meeting",
        ActionType.FINANCIAL_ACTION: "Any action with financial implications — always blocked",
    }
