# Submission target

Read from the `CALLE-AI/awesome-phone-call-agents` README on 2026-09-06.

## Contribution areas

| Area | Directory |
|---|---|
| Agent Skills | `skills/` |
| Workflow Plugins | `plugins/` |
| User-facing Apps | `apps/` |

ONRECORD is a **Workflow Plugin**: it sits on top of CALL-E, is driven by declared schemas
rather than by a UI, and is meant to be dropped into someone else's flow. Target directory:

```
plugins/onrecord/
├── README.md                 (a plugin-scoped version of the repo README)
├── manifest.json             (the config file the template calls for)
└── examples/
    ├── supplier_delivery.yaml
    ├── reference_check.yaml
    └── recorded-calls/       (the fixture bundles, so the examples run)
```

The repo's plugin template asks for `README.md`, a manifest-or-config file, and `examples/`.

Build it with:

```bash
uv run python scripts/build_plugin.py ../awesome-phone-call-agents
```

The script copies the schemas and recorded calls that the tests already run against, rather
than maintaining a second hand-edited copy — so the examples in the PR cannot drift from the
ones under test. Verified: the emitted tree runs `onrecord --replay --schema
examples/supplier_delivery.yaml` and its own 86-test suite from inside `plugins/onrecord/`,
with no credentials. (`test_doc_consistency.py` is left out; it checks this repo's README and
`docs/`, neither of which travels with the plugin.)

## Repo requirements to satisfy before opening the PR

- Setup, usage, side-effect and cancellation notes in the plugin README. **Side effects
  matter here**: this plugin places real phone calls and spends call credit. That has to be
  stated in the first screen of the plugin README, along with `--dry-run` and `--replay` as
  the two ways to exercise it without dialing.
- Fictional or masked phone numbers in every sample. All fixtures use `+8210000010xx`.
- `python3 scripts/validate_repository.py` must pass in the fork before the PR is opened.

## Out of scope for that repo (checked against our submission)

Generic telephony vendor directories, marketing-only pages, and tools that require unsafe
credential handling. ONRECORD reads `CALLE_API_KEY` from the environment, never writes it
anywhere, and its default mode needs no credential at all.

## Fallback

If the maintainers would rather have this as an Agent Skill, the code does not change — only
the packaging. `plugins/onrecord/` becomes `skills/onrecord/` with a `SKILL.md` in place of
the manifest, and the MCP tool descriptions in `src/onrecord/mcp_server.py` become the skill's
tool documentation.
