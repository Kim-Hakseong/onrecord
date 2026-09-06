# Demo script

Three minutes. The first thirty seconds are a call that fails, because that is the case the
product is about and the case every other demo skips.

**Fixed subtitle, on screen from 0:00 and repeated at 2:50:**

> Counterpart calls are re-enacted with the builder's own numbers.

The people on the other end of these calls are the builder and one acquaintance following a
written script. They are not real suppliers. Nothing in the video implies otherwise, and the
README says the same thing in its own words. The recorded transcripts in `fixtures/` are
scripted as well, and each one says so in its `note` field.

## Cue sheet

| Time | Screen | Action | Narration |
|---|---|---|---|
| 0:00 | Call Detail, PO-1041 attempt 1 | play the recorded call | "This call failed." |
| 0:12 | transcript: "확인해보고 다시 연락드릴게요" | none | "A purchasing team hits this ten times a day. The agent got through. Nothing was settled." |
| 0:18 | Ledger, `promised_ship_date` UNRESOLVED in yellow | none | "Existing agents log this as 'call completed'. We log what did not get settled — and there are four states, not two." |
| 0:25 | Requeue, a card appears | none | — |
| 0:30 | `schemas/supplier_delivery.yaml` in the editor | scroll | "You declare the fields before dialing. Type, and who is allowed to commit to them." |
| 0:50 | `calle_client.py`, the `create_and_wait` line | highlight | "CALL-E places the call." |
| 1:05 | the five-rule trace on the Call Detail screen | none | "The verdict is these five rules, in this order. Not a model." |
| 1:20 | the `spans rejected` block | none | "The model pointed at a sentence that is not in the transcript. So the value is thrown away and the field stays open." |
| 1:30 | Requeue, `dropped from goal` block | none | "The follow-up only asks what is still open." |
| 1:40 | `Call again →` | click | — |
| 1:50 | the second call's goal text — one question | none | "Shorter call. Budget back." |
| 2:05 | `CONFIRMED` in green with the quote highlighted in the transcript | none | "A confirmation carries the sentence it came from." |
| 2:20 | PO-1042, `CONTRADICTED` | none | "This is not the date our system believed. The ERP said the twentieth." |
| 2:30 | terminal, `uv run pytest -q` | run | — |
| 2:40 | terminal, `uv run onrecord --replay` with no env vars | run | "Reproducible with no CALL-E credentials." |
| 2:50 | README "What does not work yet" | scroll | "IVR trees, transfers, languages other than Korean, and the fact that these counterparts are re-enacted. Written down, not hidden." |
| 2:55 | the pull request page | none | "Submitted as a workflow plugin." |

## Recording setup

- Browser zoom 125%. 13px monospace is unreadable at 100% in a compressed upload.
- Window 1440×900, devtools closed, bookmarks bar hidden.
- Turn off automatic brightness correction — the UI is dark.
- Cursor highlighting on, so the `Call again →` click is visible.
- After upload, check the four badge colours on a phone. Violet `#A78BFA` and sky `#38BDF8`
  must not end up adjacent.

## Live call requirement

At least one call in the video is placed live, on camera, through CALL-E. Everything else is
replayed from `fixtures/`, and every replayed segment is labelled `replay` in the corner. If
the live call fails during filming, the fallback is to switch to `--replay` and say so on
camera rather than re-shoot until it works.
