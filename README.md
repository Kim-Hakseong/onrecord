# ONRECORD

**Your agent hung up. What did it actually confirm?**

A workflow plugin for [CALL-E](https://github.com/CALLE-AI/call-e-integrations). It takes the
output of a phone call and turns it into a field-level record with a verdict and a quote per
field — not a summary, and not a `success: true`.

A call-success rate of 100% can sit on top of zero confirmed facts. The phone rang, a person
answered, and nothing was settled. ONRECORD is built around that case.

## Reproduce it in three commands

No CALL-E account, no API key, no network:

```bash
uv sync
uv run pytest -q
uv run onrecord --replay --schema schemas/supplier_delivery.yaml
```

The third command adjudicates seven recorded calls and prints one verdict per field, with the
sentence each verdict came from. To see the same corpus through a different domain pack, with
no code change:

```bash
uv run onrecord --replay --schema schemas/reference_check.yaml
```

## What it does

You declare, before dialing, the fields a call has to settle — with a type and a list of roles
allowed to commit to each one:

```yaml
fields:
  - name: promised_ship_date
    type: date
    required: true
    authority: [sales_rep, account_manager, production_manager]
    question_hint: >-
      Ask for the date the order will actually leave their warehouse. A calendar
      date is required; "soon" or "probably next week" is not an answer.
```

CALL-E places the call. Afterwards every field gets one of **4** verdicts:

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | A value that parsed, quoted verbatim from the transcript, spoken by someone with authority |
| `CONTRADICTED` | Confirmed, and different from what your system already believed |
| `UNRESOLVED` | The call happened and this field did not settle |
| `NO_AUTHORITY` | Someone answered who cannot commit to this field |

Unresolved and no-authority fields go into a requeue, and the follow-up call asks only what is
still open — which makes the second call shorter and gives call budget back.

The ledger is append-only. A correction is a new row, never an edit, so any date you act on
stays traceable to a call ID and a spoken sentence.

## The adjudication rules

`src/onrecord/verdict.py` contains **5** rules, applied in a fixed order, and no model:

1. **Quote** — the cited span must exist verbatim in the transcript. If not → `UNRESOLVED`.
2. **Type** — the cited value must parse against the declared type. A parse failure is
   `UNRESOLVED`, never an exception.
3. **Authority** — the respondent must be allowed to commit to this field. If not →
   `NO_AUTHORITY`, no matter how clear the answer was.
4. **Contrast** — a settled value that differs from the value on record → `CONTRADICTED`.
5. **Confirm** — everything that got this far → `CONFIRMED`.

A small model (Claude Haiku 4.5) is used for exactly one thing: pointing at candidate spans in
the transcript. It never produces a value. If the span it points at is not literally in the
transcript, the value is discarded. `tests/test_no_model_in_verdict.py` walks the adjudicator's
AST and fails the build if a model or network client is ever imported there;
`tests/test_verdict_without_model.py` runs the whole pipeline with span pointing switched off —
every field falls to `UNRESOLVED`, the requeue fills, and the state machine keeps working.

CALL-E's own `structured_result` is treated the same way as the model's output: it is a claim,
and it has to find a quote before it can settle anything.

## What the corpus shows

Eight recorded calls, replayed by `uv run onrecord --replay` and asserted in
`tests/test_replay.py`:

| Scenario | Outcome |
|---|---|
| Evasive answer ("let me check and get back to you") | date `UNRESOLVED`, blocking reason `CONFIRMED` |
| Follow-up call | asks 3 fields instead of 4, all settle |
| Voicemail | every field `UNRESOLVED`, all requeued |
| Stand-in answered | date `NO_AUTHORITY` — the assistant may report the reason, not commit the date |
| Supplier moved the date | `CONTRADICTED` against the ERP's 2026-09-20 |
| Model paraphrased the sentence | value discarded, field stays open |
| Reference check (second domain pack) | rehire question `NO_AUTHORITY`, the rest settle |
| The same call in Korean | identical verdicts — see below |

The transcripts are in English so that a reader can check for themselves that a highlighted
quote really is in the call. One is deliberately in Korean: the adjudicator has no language in
it either, because rule 1 is a substring check, so a quote is present or it is not. The only
language-aware code anywhere is the date parser, which reads both `September 24th` and
`9월 24일`.

**Values that settled without a verbatim quote: 0.** That is the number this design is for, and
it is asserted per fixture rather than claimed in prose.

Read it for what it is worth: these six transcripts were written by the author, so the zero
shows the rules behave as specified, not that adjudication is accurate on real calls. That is
also why there is no accuracy percentage here — six scenarios cannot support one — and why the
first item under "what does not work yet" is that the corpus is not yet made of real calls.

## Call budget

A new CALL-E account gets **20** free calls. That number is in `src/onrecord/constants.py`, the
CLI reads it from there, and every screen shows `Calls used: N / 20` in the top right. The last
3 are reserved: `--live` refuses to dial below that floor.

```bash
uv run onrecord calls-remaining
uv run onrecord --dry-run --schema schemas/supplier_delivery.yaml   # prints the CALL-E task, dials nothing
uv run onrecord --live --schema schemas/supplier_delivery.yaml --subject PO-1041
```

`--replay` is the reviewer's mode and the regression harness. `--live` is the real one: it calls
the CALL-E Python SDK (`calle-ai`) at runtime, and all of that is isolated in
`src/onrecord/calle_client.py`.

## Screens

**3**, no more: the ledger, one call's detail with the quoted span highlighted in the
transcript, and the requeue.

```bash
cd web && npm install && cd ..
./scripts/dev.sh                 # api on :8799, dashboard on :3000, ctrl-c stops both
```

Or run the two halves yourself:

```bash
uv run onrecord serve            # API on :8799
cd web && npm run dev
```

## What does not work yet

- **The recorded corpus is scripted, not captured from live calls.** The transcripts in
  `fixtures/` were written to exercise the adjudicator; they have not yet been replaced with
  recordings of real CALL-E calls. Every fixture says so in its own `note` field.
- **Counterpart calls are re-enacted.** The people on the other end of the demo calls are the
  builder's own numbers and an acquaintance following a script, not real suppliers. This is
  stated in the demo video's subtitles as well.
- **Two languages, and only just.** The date parser reads English month names, ISO dates,
  `9/24`, and Korean `9월 24일`. Nothing else has been checked, and the boolean vocabulary is
  smaller still.
- **IVR trees are unhandled.** A call that lands in a phone menu produces `UNRESOLVED` rows and
  no attempt to navigate the menu.
- **Transfers and three-way calls are out of scope.** The adjudicator reads the last attempt of
  the first recipient and assumes one respondent per call.
- **The requeue does not dial by itself.** It plans the follow-up call; running it is a
  deliberate action, because calls cost money and the budget is 20.

## Layout

```
src/onrecord/verdict.py       the 5 rules; no model, no network
src/onrecord/planner.py       open fields -> CALL-E task text
src/onrecord/promote.py       open fields -> requeue rows
src/onrecord/calle_client.py  every line that touches CALL-E
src/onrecord/spanner.py       the one model call, and the null implementation
src/onrecord/store.py         append-only SQLite ledger
schemas/*.yaml                all of the domain knowledge, all of it here
fixtures/*.json               recorded calls + recorded span pointing
```

## License

MIT.
