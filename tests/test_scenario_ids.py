"""Scenario ids are visible to the agent (the task input is the id), so an id must not leak the answer.
EC ids are "mission-" plus the performer's four-digit staff number (tests/test_fixtures.py also checks this):
they carry no city, country, mode, rule word or boundary value. Modelled on T1's test, with one deviation:
digits are allowed here, so this test proves that the number is not a fact and not an answer."""

import json
import re
from pathlib import Path

import contract

ROOT = Path(__file__).resolve().parent.parent
IDS = [member.value for member in contract.EcScenario]
# Rule boundaries a number could leak: flight threshold (300 min), DSA bands, hotel and DSA amounts in cents.
WORDS = {word for enum in (contract.Country, contract.Mode, contract.AirCabin, contract.TravelClass,
                           contract.DsaBand, contract.RateSource) for member in enum
         for word in str(member.value).lower().split("_") if word}


def integers(value):
    """Every int, and every run of digits in a string, anywhere in a JSON value."""
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        yield value
    elif isinstance(value, str):
        yield from (int(digits) for digits in re.findall(r"\d+", value))
    elif isinstance(value, dict):
        for item in value.values():
            yield from integers(item)
    elif isinstance(value, list):
        for item in value:
            yield from integers(item)


def test_ids_are_mission_plus_four_digits():
    for scenario in IDS:
        assert re.fullmatch(r"mission-\d{4}", scenario), scenario


def test_ids_carry_no_enum_word():
    for scenario in IDS:
        assert not set(scenario.split("-")) & WORDS, scenario


def test_the_number_is_only_the_staff_number_never_a_fact_or_an_answer():
    for scenario in IDS:
        number = int(scenario.split("-")[1])
        facts = json.loads((ROOT / "src/plugin/data/scenarios" / f"{scenario}.json").read_text(encoding="utf-8"))
        expected = json.loads((ROOT / "tests/cases" / f"{scenario}.json").read_text(encoding="utf-8"))["expected"]
        assert facts["mission_performer"]["staff_id"] == f"S{number}"
        stripped = {key: value for key, value in facts.items() if key not in ("scenario", "mission_performer")}
        assert number not in set(integers(stripped)), f"{scenario}: {number} is also a fact"
        assert number not in set(integers(expected)), f"{scenario}: {number} is also an answer value"


def test_ids_are_unique():
    assert len(IDS) == len(set(IDS))
