"""The MCP surface, exercised through the registered tools."""

from __future__ import annotations

import pytest

from onrecord.mcp_server import server


@pytest.fixture
def db(tmp_path) -> str:
    return str(tmp_path / "mcp.sqlite")


async def _call(name: str, **arguments):
    """Invoke a tool the way a client would, and return its structured result."""
    result = await server.call_tool(name, arguments)
    assert result.is_error is not True, result.content
    return result.structured_content


@pytest.mark.anyio
async def test_every_tool_is_registered_and_described():
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert {
        "list_domains",
        "plan_call_goal",
        "replay_recorded_call",
        "read_ledger",
        "read_requeue",
        "place_call",
        "calls_remaining",
    } <= names
    for tool in tools:
        assert tool.description, f"{tool.name} has no description"


@pytest.mark.anyio
async def test_the_dialing_tool_says_it_spends_budget():
    tools = {t.name: t for t in await server.list_tools()}
    assert "SPENDS CALL BUDGET" in tools["place_call"].description
    # And the safe ones say they are safe.
    assert "no credentials" in tools["replay_recorded_call"].description.lower()


@pytest.mark.anyio
async def test_replaying_a_recorded_call_needs_no_credentials(db, monkeypatch):
    monkeypatch.delenv("CALLE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = await _call("replay_recorded_call", fixture_name="supplier_contradicted", db=db)
    assert result["values_settled_without_a_quote"] == 0
    verdicts = {row["field"]: row["verdict"] for row in result["rows"]}
    assert verdicts["promised_ship_date"] == "CONTRADICTED"
    assert len(result["rows"][0]["rule_trace"]) == 5


@pytest.mark.anyio
async def test_planning_a_call_places_no_call(db):
    result = await _call("plan_call_goal", schema_name="supplier_delivery", subject_id="PO-1041", db=db)
    assert result["open_fields"]
    assert "promised_ship_date" in result["task"]
    budget = await _call("calls_remaining", db=db)
    assert budget["used"] == 0
    assert budget["remaining"] == budget["budget"]


@pytest.mark.anyio
async def test_placing_a_call_without_credentials_reports_instead_of_raising(db, monkeypatch):
    monkeypatch.delenv("CALLE_API_KEY", raising=False)
    result = await _call("place_call", schema_name="supplier_delivery", subject_id="PO-1041", db=db)
    assert result["error"] == "not_configured"


@pytest.mark.anyio
async def test_an_unknown_schema_is_rejected_with_the_valid_options(db):
    with pytest.raises(Exception) as exc:
        await _call("plan_call_goal", schema_name="nope", subject_id="PO-1041", db=db)
    assert "supplier_delivery" in str(exc.value)


@pytest.fixture
def anyio_backend():
    return "asyncio"
