from slimconfig import build_output

from contract import ScenarioInput, TripRequestOutput
from plugin.fixtures import scenario
from plugin.world import trip_request


def get_trip_request(given: ScenarioInput) -> TripRequestOutput:
    """The scenario's mission: the performer's words and the structured facts, never an answer."""
    return build_output(trip_request(scenario(given.scenario.value)), TripRequestOutput)
