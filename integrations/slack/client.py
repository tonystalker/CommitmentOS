"""
CommitmentOS — Slack integration client.

Auth: Slack bot token from .env (SLACK_BOT_TOKEN).
No OAuth UI — token is generated once from a workspace app and stored in .env.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from typing import Any

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class SlackMessage:
    message_id: str        # channel + ts as composite key
    channel_id: str
    channel_name: str
    user_id: str
    user_name: str
    text: str
    timestamp: datetime
    thread_ts: str | None = None
    raw: dict = field(default_factory=dict)


class SlackClient:
    """
    Thin wrapper around slack_sdk.AsyncWebClient.
    Provides only the two operations CommitmentOS needs:
      - read messages from a channel
      - post a message to a channel/user
    """

    def __init__(self) -> None:
        self._client = AsyncWebClient(token=settings.slack_bot_token)

    async def get_channel_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        oldest: str | None = None,
    ) -> list[SlackMessage]:
        """Read the most recent messages from a public channel."""
        try:
            resp = await self._client.conversations_history(
                channel=channel_id,
                limit=limit,
                oldest=oldest,
            )
        except SlackApiError as e:
            logger.error("Slack conversations_history failed: %s", e.response["error"])
            return []

        messages: list[SlackMessage] = []
        raw_messages: list[Any] = resp.get("messages", [])
        for msg in (raw_messages if isinstance(raw_messages, list) else []):
            if not isinstance(msg, dict) or msg.get("type") != "message" or "bot_id" in msg:
                continue   # skip bot messages and non-message events

            user_id = msg.get("user", "")
            user_name = await self._resolve_user_name(user_id)
            ts_float = float(msg.get("ts", "0"))

            messages.append(
                SlackMessage(
                    message_id=f"{channel_id}:{msg['ts']}",
                    channel_id=channel_id,
                    channel_name=channel_id,   # caller can resolve if needed
                    user_id=user_id,
                    user_name=user_name,
                    text=msg.get("text", ""),
                    timestamp=datetime.fromtimestamp(ts_float, tz=timezone.utc),
                    thread_ts=msg.get("thread_ts"),
                    raw=msg,
                )
            )

        return messages

    async def post_message(self, channel_id: str, text: str, *, thread_ts: str | None = None) -> str:
        """Post a message to a channel. Returns the message timestamp."""
        try:
            resp = await self._client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts,
            )
            return resp.get("ts", "")
        except SlackApiError as e:
            logger.error("Slack post_message failed: %s", e.response["error"])
            raise

    async def list_channels(self) -> list[dict]:
        """List all public channels (for setup/seeding)."""
        try:
            resp = await self._client.conversations_list(types="public_channel")
            return resp.get("channels", [])
        except SlackApiError as e:
            logger.error("Slack list_channels failed: %s", e.response["error"])
            return []

    async def _resolve_user_name(self, user_id: str) -> str:
        if not user_id:
            return "unknown"
        try:
            resp = await self._client.users_info(user=user_id)
            user_data = resp.get("user") if isinstance(resp, dict) else getattr(resp, "data", {}).get("user", {})
            profile = user_data.get("profile", {}) if isinstance(user_data, dict) else {}
            return profile.get("real_name") or profile.get("display_name") or user_id
        except Exception:
            return user_id
