"""The bundled fixtures under data/, loaded once per plugin process."""

from functools import cache
from pathlib import Path

from plugin.world import load_scenario, load_world

DATA = Path(__file__).resolve().parent / "data"


@cache
def world():
    return load_world(DATA)


def scenario(scenario_id):
    return load_scenario(DATA, scenario_id)
