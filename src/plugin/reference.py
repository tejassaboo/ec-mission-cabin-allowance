from slimconfig import build_output

from contract import EcClaimOutput, ScenarioInput
from plugin.fixtures import scenario, world
from plugin.rules import oracle


def compute_mission_claim(given: ScenarioInput) -> EcClaimOutput:
    """The answer key: the one correct claim, from the handbook's rules over the bundled fixtures."""
    return build_output(oracle(world(), scenario(given.scenario.value)), EcClaimOutput)
