"""Shared verdict helpers: a result, plain JSON forms of the contract instances, and the bundled
fixtures read from the plugin folder. Pure functions of their arguments and the files on disk."""

import dataclasses
from enum import Enum
from pathlib import Path

from .world import load_scenario, load_world

DATA = Path(__file__).resolve().parents[1] / "src" / "plugin" / "data"
# What a check could raise on a value it never expected: the entry points turn it into a failed
# verdict that names it, because a verifier that raises leaves the run with no verdict at all.
UNEXPECTED = (ArithmeticError, AttributeError, LookupError, OSError, RecursionError, TypeError, ValueError)


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def plain(value):
    """A contract instance (or anything inside one) as plain JSON values: Enum members as their values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return plain(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {plain(key): plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value


def fixtures(scenario_id):
    """(the rate table, the scenario's facts), from the plugin's bundled data."""
    return load_world(DATA), load_scenario(DATA, scenario_id)


def compared(name, given, wanted):
    """A verify_output verdict: the tool's output equals what the fixtures give, or the first key that differs."""
    if given == wanted:
        return result(True, f"{name} output matches the bundled fixtures")
    different = sorted(key for key in set(given) | set(wanted) if given.get(key) != wanted.get(key))
    return result(False, f"{name} output differs from the bundled fixtures at {', '.join(different)}")
