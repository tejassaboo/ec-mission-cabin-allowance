"""What the tests share: paths, the scenarios, the hand-written cases, and values built the way
NanoAgent's sandbox builds them (build_output from plain JSON)."""

import json
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import EcClaimOutput, EcScenario, ScenarioInput
from plugin import compute_mission_claim

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "plugin" / "data"
TASK = "ec-mission-claim"
SCENARIOS = [member.value for member in EcScenario]


def case(scenario):
    """The hand-written case: {scenario, note, expected, broken: [{why, change, reason}]}."""
    return json.loads((ROOT / "tests" / "cases" / f"{scenario}.json").read_text(encoding="utf-8"))


def arguments(scenario):
    return build_output({"scenario": scenario}, ScenarioInput)


def reference(scenario):
    """The pinned reference, as NanoAgent pins it: the reference tool's output, built into its class."""
    return build_output(plain_output(compute_mission_claim(arguments(scenario))), EcClaimOutput)


def verdict(scenario, output, *, pinned=True):
    """verify_task on a plain-JSON submission, with the reference pinned as in a real run."""
    return verifier.verify_task(
        TASK, arguments(scenario), build_output(output, EcClaimOutput), reference(scenario) if pinned else None, "."
    )
