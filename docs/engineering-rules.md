# Engineering rules

The constraints this codebase is built under. They are here because most of them look like
arbitrary restrictions until you know what they are protecting.

## The adjudicator

1. **No model in `verdict.py`.** Not behind a flag, not lazily imported, not "just for the
   hard cases". Asking a model whether an answer was definite gets you an answer that is
   itself indefinite. `tests/test_no_model_in_verdict.py` enforces this against the AST.
2. **No quote, no confirmation.** A value is only CONFIRMED when the cited span is present in
   the transcript as a substring. `transcript.find(quote) == -1` means UNRESOLVED, whatever
   else was true.
3. **Parse failures are verdicts, not exceptions.** The adjudication functions do not raise.
   A garbled value is an UNRESOLVED field, which is a normal state.
4. **Authority outranks clarity.** A perfectly clear answer from someone not on the field's
   authority list is NO_AUTHORITY. The value is kept on the row so a human can see what was
   said; it just does not count.
5. **Rule order is fixed:** quote → type → authority → compare → confirm. Reordering changes
   which reason a field stops at, which changes what the requeue does about it.

## The four verdicts

`CONFIRMED / CONTRADICTED / UNRESOLVED / NO_AUTHORITY`. Never three, never five.

There is no `success` boolean anywhere in the system — not on a call, not on a run. A call
does not succeed or fail; each of its fields lands somewhere. `tests/test_api.py` asserts no
endpoint has quietly reintroduced one.

Every UNRESOLVED and NO_AUTHORITY field produces a requeue row. A code path that drops an open
field on the floor is a bug even if nothing visibly breaks.

## The ledger

Append-only. There is no `UPDATE ledger` or `DELETE FROM ledger` in `store.py`, and
`tests/test_store.py` greps for both. A correction is a new row with a later sequence number;
the superseded row stays readable, because the question "what did we believe, and when, and
why" is the reason the ledger exists.

## Domain knowledge

All of it lives in `schemas/*.yaml`. If the words "supplier", "purchase order", "candidate",
or a Korean domain term appear in `verdict.py`, `planner.py`, or `promote.py`, that is a
refactoring target — `tests/test_planner.py` checks the planner for exactly this. Two domain
packs are maintained rather than one, because a second working pack is the only real evidence
that the first one is not hard-coded.

The public surface is one function: `onrecord.run(schema, contact, ...) -> LedgerDelta`.

## Call budget

Twenty calls, and no more without an approval nobody controls. Consequences:

- The number lives in `constants.py`; the CLI, API, and every screen read it from there, and
  `tests/test_doc_consistency.py` checks the README against it.
- `--live` refuses to dial when three or fewer remain. The reserve is for demo day.
- Replayed calls cost nothing and are not counted. The counter reflects live calls only.
- The follow-up call drops fields that are already settled. That is a budget mechanism as
  much as a UX one: a shorter call is cheaper and finishes sooner.

## The screens

Three: ledger, call detail, requeue. There is no settings screen, no statistics screen, and
no onboarding.

No fake progress. No skeleton loaders, no simulated progress bars, no artificial delays. The
only animation in the product is a one-second blink on a dot that means a call is actually in
progress. A UI that performs work it is not doing is lying about state, which is the exact
failure this project is about.

Colour is never the only signal — every badge carries its verdict as text.

## Claims

Report the false-positive count (values that settled with no verbatim quote) and the real
count of false negatives. Do not report an accuracy percentage: six scenarios cannot support
one, and a number that cannot be defended is worse than no number.

Say what does not work, in the README, before anyone has to find out. Say that the demo
counterparts are re-enacted. A reviewer who discovers an omission stops trusting the parts
that were true.
