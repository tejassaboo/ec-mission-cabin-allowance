"""Structured input and structured output: every contract field is typed and described, every policy fact
reaches the agent in a typed field (never only in prose), and nothing the verifier grades is free text."""

import dataclasses
import typing
from enum import Enum

import contract
from contract import AirCabin, Country, EcClaimOutput, Journey, Meal, Mode, ScenarioInput, TripRequestOutput

CONTRACT_CLASSES = [
    value
    for value in vars(contract).values()
    if isinstance(value, type) and dataclasses.is_dataclass(value) and value.__module__ == contract.__name__
]


def annotated_fields(cls):
    """(name, type, description) for every field, from the class's Annotated hints."""
    hints = typing.get_type_hints(cls, include_extras=True)
    for field in dataclasses.fields(cls):
        hint = hints[field.name]
        assert typing.get_origin(hint) is typing.Annotated, f"{cls.__name__}.{field.name} is not Annotated"
        base, *metadata = typing.get_args(hint)
        yield field.name, base, metadata[0]


def test_every_field_is_annotated_with_a_description() -> None:
    assert len(CONTRACT_CLASSES) >= 10
    for cls in CONTRACT_CLASSES:
        for name, _, description in annotated_fields(cls):
            assert isinstance(description, str) and len(description.split()) >= 3, f"{cls.__name__}.{name}"


def test_the_task_input_is_a_single_scenario_enum() -> None:
    assert [(name, base) for name, base, _ in annotated_fields(ScenarioInput)] == [("scenario", contract.EcScenario)]


def test_every_policy_fact_reaches_the_agent_in_a_typed_field() -> None:
    request = {name: base for name, base, _ in annotated_fields(TripRequestOutput)}
    journey = {name: base for name, base, _ in annotated_fields(Journey)}
    segment = {name: base for name, base, _ in annotated_fields(contract.Segment)}
    night = {name: base for name, base, _ in annotated_fields(contract.HotelNight)}
    assert request["destination_country"] is Country and request["meals_provided"] == list[Meal]
    assert journey["mode"] is Mode and journey["cabins_sold"] == list[AirCabin]
    assert journey["depart_minute"] is int and journey["arrive_minute"] is int
    assert journey["first_commitment_minute"] == (int | None)
    assert segment["in_air_minutes"] == (int | None) and segment["overnight"] is bool
    assert night["room_rate_cents"] is int and night["local_tax_cents"] is int and night["breakfast_included"] is bool


def test_the_graded_output_has_no_free_text() -> None:
    fields = list(annotated_fields(EcClaimOutput))
    assert [name for name, _, _ in fields][:5] == [
        "rate_country",
        "outward_class",
        "outward_qualifying_segment_id",
        "return_class",
        "return_qualifying_segment_id",
    ]  # the cabin is expressed per direction, not once per trip
    for name, base, _ in fields:
        if name.endswith("_segment_id"):
            assert base == (str | None)  # a segment id, checked against the fixtures
            continue
        assert base is int or (isinstance(base, type) and issubclass(base, Enum)), f"{name}: {base}"


def test_formats_units_and_null_meanings_are_described() -> None:
    for cls in CONTRACT_CLASSES:
        for name, base, description in annotated_fields(cls):
            if name.endswith(("_utc", "night_of")):
                assert "YYYY-MM-DD" in description, f"{cls.__name__}.{name}"
            if name.endswith("_cents"):
                assert "cents" in description, f"{cls.__name__}.{name}"
            if name.endswith(("_minutes", "_minute")):
                assert "minutes" in description, f"{cls.__name__}.{name}"
            if typing.get_origin(base) is not None and type(None) in typing.get_args(base):
                assert "null" in description, f"{cls.__name__}.{name} does not say what null means"
            if typing.get_origin(base) is list:
                assert any(word in description for word in ("order", "each once", "one per", "one entry")), f"{cls.__name__}.{name}"
