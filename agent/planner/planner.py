"""
CommitmentOS — Action Planner.

Takes: commitment state + evidence + memory context + user request
Returns: ActionPlan (list of proposed actions with structured params)

The planner PROPOSES. It never authorizes or executes.
All proposals go through the policy engine before reaching the executor.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from commitments.models import ActionType, Commitment, CommitmentState
from memory.service import MemorySearchResult
from agent.extraction.llm_client import get_llm_config

logger = logging.getLogger(__name__)


@dataclass
class ProposedAction:
    action_type: ActionType
    params: dict[str, Any]
    rationale: str
    commitment_id: str


@dataclass
class ActionPlan:
    commitment_id: str
    proposed_actions: list[ProposedAction] = field(default_factory=list)
    memory_context: list[MemorySearchResult] = field(default_factory=list)
    planner_reasoning: str = ""


PLANNER_SYSTEM_PROMPT = """You are a commitment recovery planner.

Given a commitment's current state, evidence, and memory context, propose concrete actions to recover the commitment.

Available action types (use EXACTLY these strings):
- CREATE_LINEAR_TASK: create a Linear issue to track the commitment
- UPDATE_LINEAR_STATUS: update an existing Linear issue status
- POST_SLACK_MESSAGE: post a message to a Slack channel
- CREATE_REMINDER: create a reminder for the responsible person
- ASSIGN_TASK: assign an existing task to someone
- SEND_EXTERNAL_EMAIL: draft an email to an external recipient (will require approval)
- RESCHEDULE_MEETING: reschedule a meeting (will require approval)

Rules:
1. Only propose actions that are genuinely needed for this commitment.
2. For SEND_EXTERNAL_EMAIL, always include the full draft body in params.
3. For CREATE_LINEAR_TASK, always include title, description, and assignee if known.
4. Do NOT propose FINANCIAL_ACTION — that type is always blocked.
5. Do NOT propose more than 3 actions per commitment.

Return JSON: {"actions": [{"action_type": "...", "params": {...}, "rationale": "..."}]}"""


def _extract_json_dict(text: str) -> dict:
    """Extract a JSON dict from raw LLM output, resilient to markdown code fences and reasoning text."""
    text = text.strip()
    try:
        res = json.loads(text)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    import re
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            res = json.loads(match.group(1).strip())
            if isinstance(res, dict):
                return res
        except Exception:
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            res = json.loads(text[first_brace:last_brace + 1])
            if isinstance(res, dict):
                return res
        except Exception:
            pass

    return {}


async def plan_actions(
    commitment: Commitment,
    *,
    person_name: str,
    user_request: str,
    memory_context: list[MemorySearchResult],
) -> ActionPlan:
    """
    Generate an action plan for a commitment.
    Returns proposed actions — none are executed until policy authorizes them.
    """
    memory_summary = "\n".join(
        f"- {r.content[:300]}" for r in memory_context[:5]
    ) if memory_context else "No relevant memory found."

    evidence_summary = f"State: {commitment.state}\nRisk score: {commitment.risk_score:.2f}\n"
    evidence_summary += f"Normalized action: {commitment.normalized_action}\n"
    if commitment.resolved_deadline:
        evidence_summary += f"Deadline: {commitment.resolved_deadline.isoformat()}\n"
    evidence_summary += f"Related Linear tasks: {commitment.related_task_ids or 'none'}\n"

    user_message = f"""Commitment to recover:
Person: {person_name}
{evidence_summary}

Relevant memory context:
{memory_summary}

User request: {user_request}

Propose the minimal set of actions to recover this commitment."""

    llm_cfg = get_llm_config()
    current_model = llm_cfg.model

    try:
        try:
            response = await llm_cfg.client.chat.completions.create(
                model=current_model,
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1500,
            )
        except Exception as e:
            err_str = str(e).lower()
            if "model_not_found" in err_str or "does not exist" in err_str:
                for fb in llm_cfg.fallback_models:
                    if fb != current_model:
                        current_model = fb
                        llm_cfg.model = fb
                        break
                response = await llm_cfg.client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=1500,
                )
            else:
                raise

        raw = response.choices[0].message.content or '{"actions": []}'
        parsed = _extract_json_dict(raw)

        actions = []
        for item in parsed.get("actions", []):
            try:
                action_type = ActionType(item["action_type"])
                actions.append(ProposedAction(
                    action_type=action_type,
                    params=item.get("params", {}),
                    rationale=item.get("rationale", ""),
                    commitment_id=commitment.id,
                ))
            except (ValueError, KeyError) as e:
                logger.warning("Skipping invalid planned action: %s — %s", item, e)

        return ActionPlan(
            commitment_id=commitment.id,
            proposed_actions=actions,
            memory_context=memory_context,
            planner_reasoning=raw,
        )

    except Exception as e:
        logger.error("Planner failed for commitment %s: %s", commitment.id, e)
        return ActionPlan(commitment_id=commitment.id, memory_context=memory_context)
