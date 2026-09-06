#!/usr/bin/env python3
"""Emit the `plugins/onrecord/` tree for the awesome-phone-call-agents PR.

    uv run python scripts/build_plugin.py ../awesome-phone-call-agents

The submission is a copy of this repo shaped to that repo's plugin template
(README, manifest, examples). Building it from a script rather than maintaining
a second copy by hand means the examples in the PR are the same files the tests
run against -- there is no version of the schemas that only exists in the PR.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/Kim-Hakseong/onrecord"

MANIFEST = {
    "name": "onrecord",
    "version": "0.1.0",
    "kind": "workflow-plugin",
    "summary": "Turn a CALL-E call into a field-level record with a verdict and a quote per field.",
    "homepage": REPO_URL,
    "license": "MIT",
    "language": "python",
    "requires": {"python": ">=3.12", "calle-ai": ">=0.7.0"},
    "entrypoints": {
        "cli": "onrecord",
        "mcp": "onrecord-mcp",
        "python": "onrecord.run(schema, contact, subject_id=..., known_values=...)",
    },
    "calle_surfaces": ["python-sdk", "mcp"],
    "side_effects": {
        "places_phone_calls": True,
        "spends_call_credit": True,
        "modes_without_calls": ["--replay", "--dry-run"],
    },
    "verdicts": ["CONFIRMED", "CONTRADICTED", "UNRESOLVED", "NO_AUTHORITY"],
}

README = f"""# ONRECORD

**Turn a CALL-E call into a record, not a summary.**

A call-success rate of 100% can sit on top of zero confirmed facts: the phone rang, a person
answered, and nothing was settled. This plugin makes that outcome representable. You declare
the fields a call has to settle; afterwards every field carries one of four verdicts and the
transcript span it came from.

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | Parsed, quoted verbatim from the transcript, spoken by someone with authority |
| `CONTRADICTED` | Confirmed, and different from what your system believed |
| `UNRESOLVED` | The call happened and this field did not settle |
| `NO_AUTHORITY` | Someone answered who cannot commit to this field |

There is no call-level success flag.

## Setup

```bash
pip install onrecord            # or: uv sync, from a clone
export CALLE_API_KEY=...        # only needed for live calls
export ANTHROPIC_API_KEY=...    # only needed for live calls
```

## Usage

```bash
# Adjudicate the bundled recorded calls. No credentials, no calls placed.
onrecord --replay --schema examples/supplier_delivery.yaml

# Print the exact task text CALL-E would be given. Places no call.
onrecord --dry-run --schema examples/supplier_delivery.yaml --subject PO-1041

# Place a real call.
onrecord --live --schema examples/supplier_delivery.yaml --subject PO-1041
```

From Python:

```python
from onrecord import Contact, Store, load_schema, run

delta = run(
    load_schema("examples/supplier_delivery.yaml"),
    Contact(phone="+821000001041", name="Kim Min-su", org="Hanseong Precision"),
    subject_id="PO-1041",
    known_values={{"promised_ship_date": "2026-09-24"}},
    store=Store("data/onrecord.db"),
)
for row in delta.rows:
    print(row.field, row.verdict.value, row.value, row.quote)
```

From an MCP client, run `onrecord-mcp`. Tools: `list_domains`, `plan_call_goal`,
`replay_recorded_call`, `read_ledger`, `read_requeue`, `calls_remaining`, and `place_call`.

## Side effects

- **`--live` and the `place_call` MCP tool dial real phone numbers and spend CALL-E call
  credit.** Nothing else in the plugin does. `--dry-run` shows exactly what would be said;
  `--replay` runs the full adjudication path against recorded calls.
- A free CALL-E account has 20 calls. The plugin tracks how many it has spent, shows the
  count, and refuses to dial when three or fewer remain.
- Writes to a local SQLite file (default `data/onrecord.db`). Nothing is sent anywhere except
  to CALL-E and, for span pointing, the Anthropic API.
- `CALLE_API_KEY` and `ANTHROPIC_API_KEY` are read from the environment and never written to
  disk, logged, or included in a call payload.

## Cancellation and recovery

- A run is one call. There is no background scheduler and nothing retries on its own: the
  follow-up call for an unresolved field is placed only when you ask for it.
- Interrupting a run mid-call leaves the call to finish on CALL-E's side; re-running
  adjudication over the stored payload is safe and produces the same verdicts.
- The ledger is append-only, so re-running never destroys an earlier verdict. A correction is
  a new row.
- To stop all dialing, unset `CALLE_API_KEY`; every mode except `--live` keeps working.

## How the verdict is decided

Five rules, in a fixed order, in plain Python with no model in the module:

1. the cited span must exist verbatim in the transcript
2. the value must parse against the declared type
3. the respondent must be allowed to commit to this field
4. a settled value differing from the value on record is `CONTRADICTED`
5. otherwise `CONFIRMED`

A small model points at candidate spans and never produces a value; if the span it points at
is not literally in the transcript, the value is discarded. CALL-E's own `structured_result`
is treated the same way — it is a claim, and it has to find a quote.

## Examples

`examples/` holds two domain packs and the recorded calls they were tested against. The
adjudicator has no domain knowledge in it, so swapping the YAML swaps the domain.

Sample phone numbers are fictional. The recorded transcripts are scripted re-enactments, not
recordings of real suppliers; each one says so in its own `note` field.

Full source, tests, and dashboard: {REPO_URL}
"""


def build(target_repo: Path) -> Path:
    out = target_repo / "plugins" / "onrecord"
    if out.exists():
        shutil.rmtree(out)
    (out / "examples" / "recorded-calls").mkdir(parents=True)

    (out / "README.md").write_text(README, encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(MANIFEST, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for schema in sorted((REPO / "schemas").glob("*.yaml")):
        shutil.copy2(schema, out / "examples" / schema.name)
    for fixture in sorted((REPO / "fixtures").glob("*.json")):
        shutil.copy2(fixture, out / "examples" / "recorded-calls" / fixture.name)

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(REPO / "src", out / "src", ignore=ignore)
    # `test_doc_consistency` checks this repo's README and docs/, neither of
    # which travels with the plugin. Everything else runs unchanged.
    shutil.copytree(
        REPO / "tests",
        out / "tests",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test_doc_consistency.py"),
    )
    shutil.copy2(REPO / "LICENSE", out / "LICENSE")
    shutil.copy2(REPO / "pyproject.toml", out / "pyproject.toml")
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.is_dir():
        print(f"not a directory: {target}", file=sys.stderr)
        return 1
    out = build(target)
    print(f"wrote {out}")
    print("next: run `python3 scripts/validate_repository.py` in that checkout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
