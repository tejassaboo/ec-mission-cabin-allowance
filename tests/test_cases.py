"""Every scenario end to end without an LLM: the oracle equals the hand-written expectation, the answer
is unique, and a scripted agent written from the handbook alone reaches it through the tools within the
step budget; each broken variant of its answer fails with the case's reason code."""

import pytest
from helpers import ROOT, SCENARIOS, case, verdict
from scripted_agent import run
from slimconfig import build_output, plain_output

from contract import TOOLS, EcClaimOutput, Tool
from plugin import get_country_rates, get_trip_request
from plugin.fixtures import scenario as load_scenario
from plugin.fixtures import world
from plugin.rules import BAND_PERCENT, DAY_MINUTES, MEAL_PERCENT, THRESHOLD_MINUTES, dsa_breakdown, oracle

IMPLEMENTATIONS = {Tool.GET_TRIP_REQUEST: get_trip_request, Tool.GET_COUNTRY_RATES: get_country_rates}
MAX_TOOL_CALLS = 4  # plus submit, within the hosted 6 steps whose last may not call tools


def call(tool, arguments):
    """A tool call as NanoAgent makes it: plain JSON in, built into the input class, plain JSON out."""
    given, made = TOOLS[Tool(tool)]
    output = IMPLEMENTATIONS[Tool(tool)](build_output(arguments, given))
    assert isinstance(output, made)
    return plain_output(output)


def test_every_scenario_has_a_case() -> None:
    assert sorted(SCENARIOS) == sorted(path.stem for path in (ROOT / "tests" / "cases").glob("*.json"))
    assert 6 <= len(SCENARIOS) <= 8


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_oracle_equals_the_hand_written_expectation(scenario: str) -> None:
    assert oracle(world(), load_scenario(scenario)) == case(scenario)["expected"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_answer_is_unique(scenario: str) -> None:
    """No tie-break or rounding choice ever decides a committed scenario: each direction has at most one
    segment of 300+ minutes (so "the first" is the only one), and no amount lands on an exact half cent."""
    facts = load_scenario(scenario)
    for direction in ("outward", "return_journey"):
        long = [s for s in facts[direction]["segments"] if (s["in_air_minutes"] or 0) >= THRESHOLD_MINUTES]
        assert len(long) <= 1
    rate = world()["countries"][facts["destination_country"]]
    daily, parts = rate["daily_allowance_cents"], dsa_breakdown(rate, facts)
    if parts["band"] == "pro_rata":
        assert (2 * daily * parts["minutes"]) % (2 * DAY_MINUTES) != DAY_MINUTES
        base = daily
    else:
        assert daily * BAND_PERCENT[parts["band"]] % 100 == 0
        base = parts["gross_cents"]
    for meal in facts["meals_provided"]:
        assert base * MEAL_PERCENT[meal] % 100 != 50
    assert daily * 15 % 100 != 50


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_scripted_agent_reaches_the_gold_answer_within_budget(scenario: str) -> None:
    calls, submission = run(scenario, call)
    assert len(calls) <= MAX_TOOL_CALLS
    assert [tool for tool, _ in calls] == ["get_trip_request", "get_country_rates"]
    built = build_output(submission, EcClaimOutput)  # the submit tool's own shape check
    result = verdict(scenario, plain_output(built))
    assert result["valid"] is True, result["message"]
    assert submission == case(scenario)["expected"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_broken_variants_of_the_scripted_answer_fail_with_their_reason(scenario: str) -> None:
    _, submission = run(scenario, call)
    for broken in case(scenario)["broken"]:
        result = verdict(scenario, {**submission, **broken["change"]})
        assert result["valid"] is False and result["message"].split(":")[0] == broken["reason"], (broken["why"], result["message"])


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_request_text_is_flavour_only(scenario: str) -> None:
    """The structured fields alone decide the answer (C9): the oracle ignores request_text, and the scripted
    agent reaches the same submission when the words are blanked out."""
    facts = load_scenario(scenario)
    assert oracle(world(), {**facts, "request_text": ""}) == oracle(world(), facts)

    def muted(tool, arguments):
        output = call(tool, arguments)
        return {**output, "request_text": ""} if tool == "get_trip_request" else output

    assert run(scenario, muted)[1] == run(scenario, call)[1]
