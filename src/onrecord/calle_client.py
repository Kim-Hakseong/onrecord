"""Everything that touches CALL-E lives here.

Measured against calle-ai 0.7.0 on 2026-09-06; the observed response shape is
written down in `docs/calle-response-shape.md`. If the SDK moves, this file is
the only one that has to move with it -- the adjudicator never sees a CALL-E
object, only a `CallOutcome`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

SPEAKER_AGENT = "agent"
SPEAKER_CALLEE = "callee"
SPEAKER_UNKNOWN = "unknown"

_SPEAKER_MAP = {"bot": SPEAKER_AGENT, "user": SPEAKER_CALLEE, "unknown": SPEAKER_UNKNOWN}

#: CALL-E call statuses that mean the call is over, one way or another.
TERMINAL_STATUSES = frozenset({"completed", "failed", "canceled"})


class CalleNotConfigured(RuntimeError):
    """Raised when a live call is requested without an API key."""


@dataclass
class CallOutcome:
    """A finished call, flattened into the only shape ONRECORD understands."""

    call_id: str
    status: str = ""
    transcript: str = ""
    turns: list[dict[str, Any]] = field(default_factory=list)
    structured_result: dict[str, Any] = field(default_factory=dict)
    duration_seconds: int = 0
    end_reason: str = ""
    provider_call_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def reached_someone(self) -> bool:
        return any(turn.get("speaker") == SPEAKER_CALLEE for turn in self.turns)


def render_transcript(turns: list[dict[str, Any]]) -> str:
    return "\n".join(f"{t.get('speaker', SPEAKER_UNKNOWN)}: {t.get('text', '')}" for t in turns)


def outcome_from_payload(payload: dict[str, Any]) -> CallOutcome:
    """Flatten a CALL-E call task payload. Pure -- no network, no key needed.

    A call task carries a list of recipients, each with a list of attempts, each
    with its own transcript turns. ONRECORD dials one recipient at a time, so it
    reads the last attempt of the first recipient and keeps the whole payload.
    """
    recipients = payload.get("recipients") or []
    recipient = recipients[0] if recipients else {}
    attempts = recipient.get("attempts") or []
    attempt = attempts[-1] if attempts else {}

    turns = [
        {
            "speaker": _SPEAKER_MAP.get(str(turn.get("speaker", "unknown")), SPEAKER_UNKNOWN),
            "text": str(turn.get("text", "")),
            "offset_seconds": turn.get("offset_seconds"),
        }
        for turn in (attempt.get("transcript_turns") or [])
    ]

    structured = payload.get("structured_result") or recipient.get("structured_result") or {}

    end_reason = str(
        attempt.get("failure_code")
        or attempt.get("failure_message")
        or recipient.get("status")
        or payload.get("status")
        or ""
    )

    return CallOutcome(
        call_id=str(payload.get("id", "")),
        status=str(payload.get("status", "")),
        transcript=render_transcript(turns),
        turns=turns,
        structured_result=dict(structured) if isinstance(structured, dict) else {},
        duration_seconds=_duration(attempt),
        end_reason=end_reason,
        provider_call_id=str(attempt.get("provider_call_id") or ""),
        raw=payload,
    )


def _duration(attempt: dict[str, Any]) -> int:
    offsets = [
        turn.get("offset_seconds")
        for turn in (attempt.get("transcript_turns") or [])
        if isinstance(turn.get("offset_seconds"), int)
    ]
    if offsets:
        return max(offsets)
    started, completed = attempt.get("started_at"), attempt.get("completed_at")
    if isinstance(started, str) and isinstance(completed, str):
        from datetime import datetime

        try:
            delta = datetime.fromisoformat(completed) - datetime.fromisoformat(started)
            return max(0, int(delta.total_seconds()))
        except ValueError:
            return 0
    return 0


class CalleClient:
    """Thin wrapper over `calle.CalleClient`.

    The SDK is imported lazily so that `--replay` and the whole test suite run
    on a machine with no CALL-E credentials and no SDK configuration at all.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("CALLE_API_KEY", "")
        self.base_url = base_url or os.environ.get("CALLE_BASE_URL", "https://api.heycall-e.com")
        self.timeout = timeout
        self._sdk: Any = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> Any:
        if self._sdk is None:
            if not self.configured:
                raise CalleNotConfigured(
                    "CALLE_API_KEY is not set. Live calls need it; `--replay` does not."
                )
            from calle import CalleClient as _SDKClient  # imported at call time on purpose

            self._sdk = _SDKClient(
                api_key=self.api_key, base_url=self.base_url, timeout=self.timeout
            )
        return self._sdk

    def place_call(
        self,
        *,
        task: str,
        phone: str,
        result_schema: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        locale: str | None = None,
        idempotency_key: str | None = None,
        timeout_seconds: float = 600.0,
        interval_seconds: float = 2.0,
    ) -> CallOutcome:
        """Place one call and block until CALL-E reports a terminal status."""
        recipient: dict[str, Any] = {"phone": phone}
        if locale:
            recipient["locale"] = locale
        payload = self._client().calls.create_and_wait(
            task=task,
            recipient=recipient,
            result_schema=result_schema,
            metadata=metadata,
            idempotency_key=idempotency_key,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
        )
        return outcome_from_payload(payload)

    def create_call(
        self,
        *,
        task: str,
        phone: str,
        result_schema: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        locale: str | None = None,
    ) -> dict[str, Any]:
        recipient: dict[str, Any] = {"phone": phone}
        if locale:
            recipient["locale"] = locale
        return self._client().calls.create(
            task=task,
            recipient=recipient,
            result_schema=result_schema,
            metadata=metadata,
        )

    def fetch_call(self, call_id: str) -> CallOutcome:
        return outcome_from_payload(self._client().calls.get(call_id))

    def events(self, call_id: str) -> list[dict[str, Any]]:
        return list(self._client().calls.list_events(call_id).get("data", []))

    def close(self) -> None:
        if self._sdk is not None:
            self._sdk.close()
            self._sdk = None
