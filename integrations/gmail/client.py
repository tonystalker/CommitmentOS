"""
CommitmentOS — Gmail integration client.

Auth: Refresh token loaded from .env — no sign-in UI in the app.
Generate the refresh token once with: python scripts/gmail_auth.py
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]


@dataclass
class GmailMessage:
    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipient: str
    body: str
    timestamp: datetime
    raw: dict = field(default_factory=dict)


@dataclass
class GmailThread:
    thread_id: str
    subject: str
    messages: list[GmailMessage] = field(default_factory=list)


class GmailClient:
    """
    Gmail client backed by a pre-generated refresh token.
    App never handles an OAuth redirect — credentials come from .env.
    """

    def __init__(self) -> None:
        self._creds: Credentials | None = None
        self._service: Any = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        creds = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        # Refresh to get a valid access token
        creds.refresh(Request())
        self._creds = creds
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def get_threads(
        self,
        query: str = "",
        *,
        max_results: int = 20,
        label_ids: list[str] | None = None,
    ) -> list[GmailThread]:
        """
        List threads matching a Gmail search query.
        query: Gmail search syntax (e.g. "is:unread", "from:someone@acme.com")
        """
        svc = self._get_service()
        try:
            params: dict[str, Any] = {"userId": "me", "maxResults": max_results}
            if query:
                params["q"] = query
            if label_ids:
                params["labelIds"] = label_ids

            result = svc.users().threads().list(**params).execute()
            thread_list = result.get("threads", [])

            threads = []
            for t in thread_list:
                thread = self.get_thread(t["id"])
                if thread:
                    threads.append(thread)
            return threads
        except HttpError as e:
            logger.error("Gmail get_threads failed: %s", e)
            return []

    def get_thread(self, thread_id: str) -> GmailThread | None:
        """Fetch a single thread by ID with all messages."""
        svc = self._get_service()
        try:
            data = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
            messages_data = data.get("messages", [])

            messages = [self._parse_message(m) for m in messages_data]
            subject = ""
            if messages:
                subject = messages[0].subject

            return GmailThread(thread_id=thread_id, subject=subject, messages=messages)
        except HttpError as e:
            logger.error("Gmail get_thread failed for id=%s: %s", thread_id, e)
            return None

    def send_email(self, to: str, subject: str, body: str, *, thread_id: str | None = None) -> str:
        """Send an email. Returns the sent message ID."""
        svc = self._get_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body_payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            body_payload["threadId"] = thread_id

        try:
            sent = svc.users().messages().send(userId="me", body=body_payload).execute()
            return sent.get("id", "")
        except HttpError as e:
            logger.error("Gmail send_email failed: %s", e)
            raise

    def create_draft(self, to: str, subject: str, body: str, *, thread_id: str | None = None) -> str:
        """Create a Gmail draft (for approval-gated external emails). Returns draft ID."""
        svc = self._get_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        msg_payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            msg_payload["threadId"] = thread_id

        try:
            draft = svc.users().drafts().create(userId="me", body={"message": msg_payload}).execute()
            return draft.get("id", "")
        except HttpError as e:
            logger.error("Gmail create_draft failed: %s", e)
            raise

    def send_draft(self, draft_id: str) -> str:
        """Send a previously created draft. Returns sent message ID."""
        svc = self._get_service()
        try:
            sent = svc.users().drafts().send(userId="me", body={"id": draft_id}).execute()
            return sent.get("id", "")
        except HttpError as e:
            logger.error("Gmail send_draft failed: %s", e)
            raise

    def _parse_message(self, data: dict) -> GmailMessage:
        headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
        body = self._extract_body(data.get("payload", {}))
        ts_ms = int(data.get("internalDate", 0))
        return GmailMessage(
            message_id=data.get("id", ""),
            thread_id=data.get("threadId", ""),
            subject=headers.get("subject", "(no subject)"),
            sender=headers.get("from", ""),
            recipient=headers.get("to", ""),
            body=body,
            timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
            raw=data,
        )

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from a Gmail message payload."""
        mime_type = payload.get("mimeType", "")
        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            body = self._extract_body(part)
            if body:
                return body

        return ""
