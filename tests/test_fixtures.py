"""The environment: the vendored copies stay identical, the handbook is the task's instructions, and the
fixtures hold their invariants (minute stamps recomputed here with datetime, which the plugin never uses)."""

import json
from datetime import UTC, datetime

import pytest
from helpers import DATA, ROOT, SCENARIOS

from contract import Country, EcScenario
from plugin.fixtures import scenario as load_scenario
from plugin.fixtures import world
from plugin.world import EPOCH, SCENARIO_KEYS, schema_problems, trip_request

PINNED_RATES = {  # Regulation (EU) 2025/693 Article 1 table (hotel ceiling, daily allowance), EUR; UK from C(2026) 634
    "BE": (171, 132), "BG": (121, 78), "CZ": (149, 98), "DK": (208, 172), "DE": (154, 123), "EE": (118, 125),
    "IE": (191, 144), "GR": (134, 108), "ES": (154, 101), "FR": (212, 127), "HR": (132, 99), "IT": (178, 116),
    "CY": (145, 103), "LV": (128, 110), "LT": (114, 103), "LU": (178, 142), "HU": (135, 93), "MT": (166, 109),
    "NL": (190, 137), "AT": (158, 131), "PL": (126, 95), "PT": (121, 95), "RO": (109, 88), "SI": (140, 108),
    "SK": (120, 104), "FI": (170, 155), "SE": (198, 135), "GB": (226, 152),
}  # fmt: skip


def instructions(manifest):
    """The task's instructions block from nanoagent.yaml, de-indented."""
    lines = manifest.split("\n")
    start = next(index for index, line in enumerate(lines) if line.strip() == "instructions: |-") + 1
    body = []
    for line in lines[start:]:
        if line and not line.startswith("      "):
            break
        body.append(line[6:])
    return "\n".join(body).rstrip("\n")


@pytest.mark.parametrize("module", ["rules.py", "world.py"])
def test_the_verifier_runs_the_same_code(module: str) -> None:
    assert (ROOT / "src" / "plugin" / module).read_bytes() == (ROOT / "verifier" / module).read_bytes()


def test_the_handbook_is_the_task_instructions() -> None:
    handbook = (DATA / "handbook.md").read_text(encoding="utf-8")
    assert instructions((ROOT / "nanoagent.yaml").read_text(encoding="utf-8")) == handbook.rstrip("\n")
    assert len(handbook.split()) <= 1500


def test_the_handbook_pins_its_sources_and_states_the_toy_rules() -> None:
    handbook = (DATA / "handbook.md").read_text(encoding="utf-8")
    for needle in (
        "C(2025) 2495",
        "13 May 2025",
        "422471ab0b249edbed70d686e085fbae4d43726bd83e9abce2437172cc4f885b",
        "34268dbf27090572c7608db77432129a24af9019a106fb76605b7e47f1c5a379",
        "72f2ead02e850a9b06b4306e72ffdca5f24542ce07121955d8d7881a506fd2c2",
        "ff4e39e7ec770c4be2f40e0c25a5078afb0b315d4f35da2662164d4b73f8a482",
        "(EU) 2025/693",
        "C(2026) 634",
        "A human should confirm them against EUR-Lex",
        "## Clarifications (toy rules)",
        "## Rules not in scope",
        "## Step plan",
        "300 or more",
    ):
        assert needle in handbook, needle
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "A human should confirm" in readme and "Limitations" in readme


def test_the_rate_table_matches_the_pinned_acts() -> None:
    rows = world()["countries"]
    assert sorted(rows) == sorted(country.value for country in Country) == sorted(PINNED_RATES)
    for code, (hotel, daily) in PINNED_RATES.items():
        assert (rows[code]["hotel_ceiling_cents"], rows[code]["daily_allowance_cents"]) == (hotel * 100, daily * 100)
        assert rows[code]["source"] == ("c_2026_634" if code == "GB" else "reg_eu_2025_693")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_fixtures_follow_the_schema(scenario: str) -> None:
    assert schema_problems(world(), load_scenario(scenario)) == []


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_minute_stamps_agree_with_datetime(scenario: str) -> None:
    epoch = datetime.fromisoformat(f"{EPOCH}T00:00+00:00")
    view = trip_request(load_scenario(scenario))
    for direction in ("outward", "return_journey"):
        journey = view[direction]
        for prefix in ("depart", "arrive", "first_commitment"):
            text = journey[f"{prefix}_utc"]
            if text is None:
                assert journey[f"{prefix}_minute"] is None
                continue
            moment = datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
            assert journey[f"{prefix}_minute"] == int((moment - epoch).total_seconds() // 60)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenario_files_hold_facts_only(scenario: str) -> None:
    facts = load_scenario(scenario)
    assert tuple(facts) == SCENARIO_KEYS and facts["scenario"] == scenario
    text = json.dumps(facts)
    for answer_word in ("rate_country", "dsa_cents", "total_cents", "mission_minutes", "_class", "qualifying"):
        assert answer_word not in text


def test_every_scenario_has_a_file_and_no_more() -> None:
    assert sorted(path.stem for path in (DATA / "scenarios").glob("*.json")) == sorted(member.value for member in EcScenario)


def test_gitignore_keeps_the_bundled_data() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    assert not any(pattern in ignored for pattern in ("*.json", "*.md", "data/", "src/"))
