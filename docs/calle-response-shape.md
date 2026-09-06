# CALL-E response shape, as measured

Measured against `calle-ai` **0.7.0** on 2026-09-06 by reading the installed package, not by
reading the docs. Everything ONRECORD assumes about CALL-E is in this file and in
`src/onrecord/calle_client.py`; if the SDK moves, those are the two things to change.

## Client

```python
from calle import CalleClient

client = CalleClient(api_key=..., base_url="https://api.heycall-e.com", timeout=30.0)
client.calls    # CalleCalls
client.goals    # CalleGoals
client.webhooks # CalleWebhooks
```

## Calls

| Method | Signature |
|---|---|
| `create` | `(*, task, recipient=None, recipients=None, result_schema=None, recipient_result_schema=None, metadata=None, webhook_url=None, idempotency_key=None) -> dict` |
| `get` | `(call_id) -> dict` |
| `wait_for_result` | `(call_id, *, interval_seconds=2.0, timeout_seconds=600.0) -> dict` |
| `create_and_wait` | `(**kwargs) -> dict` |
| `list_events` | `(call_id, *, cursor=None, limit=None) -> dict` |

`create` posts to `POST /v1/calls`. Passing `recipient={"phone": ...}` is normalised by the
SDK into `recipients: [{"phones": [...]}]`. `wait_for_result` polls `GET /v1/calls/{id}` until
`status` is one of `completed` / `failed` / `canceled`, and raises `CalleTimeoutError`
otherwise. ONRECORD uses `create_and_wait`.

## Call task payload

```
call_task
├─ id, object="call_task", status: queued|in_progress|completed|failed|canceled
├─ task                      the natural-language instruction we sent
├─ structured_result         our result_schema, extracted by CALL-E after the call
└─ recipients[]
   ├─ id, phones[], locale, region
   ├─ status: pending|in_progress|completed|failed|skipped
   ├─ structured_result      per-recipient extraction (recipient_result_schema)
   ├─ summary
   └─ attempts[]
      ├─ id, phone, status: queued|dialing|in_progress|completed|failed|canceled
      ├─ started_at, completed_at
      ├─ summary, provider_call_id, failure_code, failure_message
      └─ transcript_turns[]  { offset_seconds, speaker: bot|user|unknown, text }
```

ONRECORD dials one recipient at a time and reads the **last attempt of the first recipient**.
Speakers are relabelled `bot -> agent`, `user -> callee`, anything else `unknown`; the
transcript ONRECORD stores is those turns rendered as `speaker: text`, one per line,
whitespace-normalised. Quote offsets in the ledger are indices into that string.

Call duration is not a field on the payload. It is derived from the largest
`offset_seconds` in the transcript, falling back to `completed_at - started_at`.

## What we send as `result_schema`

Built by `schema.result_schema_for`. Supported JSON Schema features per the SDK's own
docstring: `type`, `properties`, `required`, `enum`, nested objects, simple `array.items`,
`description`, `additionalProperties: false`. Not supported: `$ref`, `oneOf`, `anyOf`,
`allOf`, recursion, format validation.

Two consequences we act on:

- Booleans are sent as string enums `["yes", "no", "unknown"]`, per the SDK's own advice to
  prefer string enums for decisions that may be unclear.
- **No field is `required`,** and every enum carries `unknown`. A call that settles nothing
  has to be expressible, or the extractor is pushed into inventing values.

## Webhooks

`WebhookEventType` is `call.completed`, `call.failed`, `call.result_validation_failed`.
ONRECORD polls rather than receiving webhooks; the wrapper leaves `webhook_url` unset.

## Notes for the feedback survey

- `structured_result` carries no provenance — no span, offset, or confidence tying a value to
  anything the callee said. That is the gap this project is built around, and a per-field
  `evidence: {attempt_id, turn_index, text}` would be the single most useful addition.
- `status: "completed"` is true of a call that reached voicemail and of a call that settled
  everything. The distinction lives only in `failure_code` on the attempt, which is set even
  when `status` is `completed`.
- There is no duration field on an attempt, so callers derive one from transcript offsets.
