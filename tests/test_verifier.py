"""The verifier against hand-written submissions (no agent): the brief's section 7 matrix. Correct,
incorrect, missing, consistency and verifier-caught malformed cases run through verify_task; shape
problems are refused by build_output before any verifier runs, exactly as in NanoAgent."""

import json

import pytest
from helpers import SCENARIOS, TASK, arguments, case, reference, verdict
from slimconfig import build_output

import verifier
from contract import EcClaimOutput, RatesInput

ORDER = [
    "reference-matches-oracle",
    "outward-segment-exists",
    "return-segment-exists",
    "outward-class-consistent",
    "return-class-consistent",
    "band-fits-minutes",
    "amounts-not-negative",
    "total-is-sum",
    "rate-country-correct",
    "outward-qualifying-correct",
    "outward-class-correct",
    "return-qualifying-correct",
    "return-class-correct",
    "mission-minutes-correct",
    "dsa-band-correct",
    "dsa-correct",
    "hotel-correct",
]
MADRID = case("las-palmas-via-madrid")["expected"]
TENERIFE = case("tenerife-red-eye-return")["expected"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_hand_written_answer_passes(scenario: str) -> None:
    result = verdict(scenario, case(scenario)["expected"])
    assert result["valid"] is True and result["score"] == 1.0, result["message"]
    assert [entry["id"] for entry in result["details"]["constraints"]] == ORDER
    assert all(entry["ok"] is True for entry in result["details"]["constraints"])


@pytest.mark.parametrize(
    ("scenario", "index"), [(scenario, index) for scenario in SCENARIOS for index in range(len(case(scenario)["broken"]))]
)
def test_each_broken_answer_fails_with_its_reason_code(scenario: str, index: int) -> None:
    broken = case(scenario)["broken"][index]
    result = verdict(scenario, {**case(scenario)["expected"], **broken["change"]})
    assert result["valid"] is False and result["score"] == 0.0
    assert result["message"].split(":")[0] == broken["reason"], (broken["why"], result["message"])
    failing = [entry for entry in result["details"]["constraints"] if entry["ok"] is False]
    assert failing[0]["id"] == broken["reason"]


def test_a_failed_stage_leaves_later_stages_unchecked() -> None:
    result = verdict("las-palmas-via-madrid", {**MADRID, "outward_qualifying_segment_id": "X9"})
    states = {entry["id"]: entry["ok"] for entry in result["details"]["constraints"]}
    assert states["outward-segment-exists"] is False
    assert all(states[identifier] is None for identifier in ORDER[3:])


def test_messages_name_the_rule_and_the_numbers() -> None:
    result = verdict("las-palmas-inspection-299", {**case("las-palmas-inspection-299")["expected"], "outward_class": "business", "outward_qualifying_segment_id": "O1"})
    assert result["message"] == "outward-class-consistent: named qualifying segment O1 flies 299 min, which is not >= 300"
    result = verdict("las-palmas-via-madrid", {**MADRID, "outward_class": "economy", "outward_qualifying_segment_id": None})
    assert "O2 is the first outward segment with >= 300 min (O1 140 min, O2 300 min)" in result["message"]
    assert "qualifies the whole outward journey" in result["message"]
    result = verdict("lille-rail-360", {**case("lille-rail-360")["expected"], "mission_minutes": 480, "dsa_band": "over_6h_to_12h", "dsa_cents": 5397, "total_cents": 5397})
    assert "240 min, plus 60 (rail) + 60 (rail) = 360" in result["message"] and result["message"].endswith("(+2 more)")


def test_a_message_counts_the_other_failures() -> None:
    result = verdict("las-palmas-via-madrid", {**MADRID, "outward_class": "premium_economy", "return_class": "economy", "dsa_cents": 1, "total_cents": 29801})
    assert result["message"].startswith("outward-class-correct:") and result["message"].endswith("(+1 more)")


def test_a_wrong_answer_key_is_caught_before_the_submission() -> None:
    wrong_key = build_output({**MADRID, "outward_class": "premium_economy"}, EcClaimOutput)
    result = verifier.verify_task(TASK, arguments("las-palmas-via-madrid"), build_output(MADRID, EcClaimOutput), wrong_key, ".")
    assert result["valid"] is False and result["message"].startswith("reference-matches-oracle")


def test_without_a_pinned_reference_the_oracle_still_decides() -> None:
    assert verdict("las-palmas-via-madrid", MADRID, pinned=False)["valid"] is True
    assert verdict("las-palmas-via-madrid", {**MADRID, "outward_class": "premium_economy"}, pinned=False)["valid"] is False


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"return_qualifying_segment_id": "O1"}, "return-segment-exists"),  # an outward id on the return
        ({"return_qualifying_segment_id": None}, "return-class-consistent"),  # business with no segment named
        ({"return_class": "rail_first_class"}, "return-class-consistent"),  # rail class on a flight
        ({"outward_qualifying_segment_id": "O2"}, "outward-class-consistent"),  # a 170-min segment named
        ({"dsa_cents": -1, "total_cents": -1}, "amounts-not-negative"),
        ({"mission_minutes": 0}, "amounts-not-negative"),
        ({"total_cents": 7576}, "total-is-sum"),  # one cent off the sum
        ({"mission_minutes": 1441}, "band-fits-minutes"),  # 1441 is pro rata, not the 100 % band
        ({"mission_minutes": 1441, "dsa_band": "pro_rata", "dsa_cents": 7582, "total_cents": 7582}, "mission-minutes-correct"),
        ({"rate_country": "PT"}, "rate-country-correct"),
        ({"return_class": "economy", "return_qualifying_segment_id": "R1"}, "return-class-correct"),  # qualifies, but books economy
        ({"dsa_cents": 7576, "total_cents": 7576}, "dsa-correct"),  # one cent over
        ({"hotel_cents": 1, "total_cents": 7576}, "hotel-correct"),  # a hotel where there was none
    ],
)
def test_incorrect_missing_and_inconsistent_answers(change: dict, reason: str) -> None:
    result = verdict("tenerife-red-eye-return", {**TENERIFE, **change})
    assert result["valid"] is False and result["message"].split(":")[0] == reason, result["message"]


@pytest.mark.parametrize(
    "raw",
    [
        {**TENERIFE, "dsa_cents": "7575"},  # cents as a string
        {**TENERIFE, "dsa_cents": 75.75},  # a float for int cents
        {**TENERIFE, "mission_minutes": True},
        {**TENERIFE, "return_class": "Business"},  # wrong case
        {**TENERIFE, "return_class": "first"},  # not a class
        {**TENERIFE, "dsa_band": "full_day"},  # unknown Enum value
        {**TENERIFE, "rate_country": "Spain"},
        {key: value for key, value in TENERIFE.items() if key != "hotel_cents"},  # missing field
        {key: value for key, value in TENERIFE.items() if key != "outward_qualifying_segment_id"},  # nullable still required
        {**TENERIFE, "notes": "red-eye"},  # extra field
        {**TENERIFE, "outward_class": None},  # null for a non-optional field
        ["ES", "economy"],  # not an object
    ],
)
def test_malformed_outputs_are_refused_before_the_verifier(raw) -> None:
    with pytest.raises(ValueError):
        build_output(raw, EcClaimOutput)


def test_non_json_output_never_parses() -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads("{rate_country: ES, outward_class: economy}")


@pytest.mark.parametrize(
    ("arguments_value", "output_value"),
    [
        (None, None),
        ("nonsense", 7),
        (arguments("tenerife-red-eye-return"), None),
        (arguments("tenerife-red-eye-return"), {"rate_country": "ES"}),
        ({"scenario": "no-such-mission"}, TENERIFE),
        ({"scenario": "../../etc/passwd"}, TENERIFE),
        (arguments("tenerife-red-eye-return"), {**TENERIFE, "dsa_cents": "lots"}),
        (arguments("tenerife-red-eye-return"), {**TENERIFE, "outward_qualifying_segment_id": ["O1"]}),
    ],
)
def test_the_verifier_never_raises(arguments_value, output_value) -> None:
    """Malformed data that slipped past build_output still gets a failed, plain-JSON verdict, never an exception."""
    result = verifier.verify_task(TASK, arguments_value, output_value, None, ".")
    assert result["valid"] is False and result["score"] == 0.0
    json.dumps(result)


def test_an_unknown_task_or_tool_id_is_a_failed_verdict_not_an_exception() -> None:
    gold = build_output(TENERIFE, EcClaimOutput)
    for result in (
        verifier.verify_task("claim-mission", arguments("tenerife-red-eye-return"), gold, None, "."),
        verifier.verify_task(None, arguments("tenerife-red-eye-return"), gold, None, "."),
        verifier.verify_task("get_trip_request", arguments("tenerife-red-eye-return"), gold, None, "."),
        verifier.verify_input("lookup_rates", arguments("tenerife-red-eye-return")),
        verifier.verify_output("lookup_rates", None, None, "."),
        verifier.verify_output("get_trip_request", None, None, "."),
        verifier.verify_output("get_country_rates", {"countries": ["XX"]}, None, "."),
        verifier.verify_output("compute_mission_claim", {"scenario": "nope"}, None, "."),
    ):
        assert result["valid"] is False and result["message"].startswith("verifier-error")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_verdicts_are_deterministic_plain_json(scenario: str) -> None:
    broken = {**case(scenario)["expected"], **case(scenario)["broken"][0]["change"]}
    for output in (case(scenario)["expected"], broken):
        first, second = verdict(scenario, output), verdict(scenario, output)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)  # no default=: plain JSON only
        assert isinstance(first["score"], float) and 0.0 <= first["score"] <= 1.0


@pytest.mark.parametrize(
    ("raw", "valid"),
    [({"countries": ["ES"]}, True), ({"countries": ["ES", "GB"]}, True), ({"countries": []}, False), ({"countries": ["ES", "ES"]}, False)],
)
def test_rates_input_checks(raw: dict, valid: bool) -> None:
    assert verifier.verify_input("get_country_rates", build_output(raw, RatesInput))["valid"] is valid


def test_the_reference_tool_output_is_checked_against_the_oracle() -> None:
    good = verifier.verify_output("compute_mission_claim", arguments("lille-rail-361"), reference("lille-rail-361"), ".")
    bad = verifier.verify_output("compute_mission_claim", arguments("lille-rail-361"), reference("lille-rail-360"), ".")
    assert good["valid"] is True and bad["valid"] is False
