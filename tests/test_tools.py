"""The tools: what they return, what they refuse, how big their outputs are, and the real MCP server."""

import json
import sys

import anyio
import pytest
from helpers import ROOT, SCENARIOS
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output, plain_output

import verifier
from contract import Country, RatesInput, ScenarioInput
from plugin import get_country_rates, get_trip_request

MAX_OUTPUT_CHARS = 4000  # about 1k tokens: every tool output stays far from the hosted 65,536-token budget


def trip(scenario):
    return get_trip_request(build_output({"scenario": scenario}, ScenarioInput))


def rates(countries):
    return get_country_rates(build_output({"countries": countries}, RatesInput))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_tool_outputs_match_the_fixtures_and_stay_small(scenario: str) -> None:
    given = build_output({"scenario": scenario}, ScenarioInput)
    request = trip(scenario)
    assert verifier.verify_output("get_trip_request", given, request, ".")["valid"] is True
    assert len(json.dumps(plain_output(request))) <= MAX_OUTPUT_CHARS
    query = build_output({"countries": [request.destination_country.value]}, RatesInput)
    found = get_country_rates(query)
    assert verifier.verify_output("get_country_rates", query, found, ".")["valid"] is True
    assert len(json.dumps(plain_output(found))) <= MAX_OUTPUT_CHARS


def test_every_country_has_a_rate_and_the_whole_table_stays_small() -> None:
    every = [country.value for country in Country]
    table = rates(every)
    assert [row.country.value for row in table.rates] == every
    assert len(json.dumps(plain_output(table))) <= 3 * MAX_OUTPUT_CHARS


def test_rates_keep_the_requested_order_and_the_pinned_values() -> None:
    table = plain_output(rates(["GB", "ES", "LU", "FR"]))["rates"]
    assert [(row["country"], row["daily_allowance_cents"], row["hotel_ceiling_cents"], row["source"]) for row in table] == [
        ("GB", 15200, 22600, "c_2026_634"),
        ("ES", 10100, 15400, "reg_eu_2025_693"),
        ("LU", 14200, 17800, "reg_eu_2025_693"),
        ("FR", 12700, 21200, "reg_eu_2025_693"),
    ]


@pytest.mark.parametrize(("countries", "match"), [([], "at least one"), (["ES", "ES"], "each once")])
def test_rates_refuse_bad_input(countries, match) -> None:
    with pytest.raises(ValueError, match=match):
        rates(countries)


def test_minute_stamps_are_shown_with_the_utc_stamps() -> None:
    request = plain_output(trip("mission-6044"))
    back = request["return_journey"]
    assert (back["depart_utc"], back["arrive_utc"]) == ("2027-03-09T22:00Z", "2027-03-10T03:05Z")
    assert back["arrive_minute"] - back["depart_minute"] == 305
    assert back["first_commitment_minute"] - back["arrive_minute"] == 145
    assert request["return_journey"]["arrive_minute"] - request["outward"]["depart_minute"] == 1200


def test_a_changed_tool_output_is_caught() -> None:
    given = build_output({"scenario": "mission-2290"}, ScenarioInput)
    changed = build_output({**plain_output(trip("mission-2290")), "meals_provided": []}, type(trip("mission-2290")))
    result = verifier.verify_output("get_trip_request", given, changed, ".")
    assert result["valid"] is False and "meals_provided" in result["message"]


def test_the_mcp_server_serves_every_tool() -> None:
    async def session():
        server = StdioServerParameters(command=sys.executable, args=["-m", "plugin"], cwd=str(ROOT))
        async with stdio_client(server) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            names = sorted(tool.name for tool in (await client.list_tools()).tools)
            answer = await client.call_tool("get_trip_request", {"scenario": "mission-3318"})
            refused = await client.call_tool("get_country_rates", {"countries": []})
            return names, answer, refused

    names, answer, refused = anyio.run(session)
    assert names == ["compute_mission_claim", "get_country_rates", "get_trip_request"]
    assert answer.isError is False and answer.structuredContent["destination_country"] == "ES"
    assert refused.isError is True
