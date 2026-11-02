"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import claim, rates, trip_request
from .checks import UNEXPECTED, result

TOOLS = {Tool.GET_TRIP_REQUEST: trip_request, Tool.GET_COUNTRY_RATES: rates, Tool.COMPUTE_MISSION_CLAIM: claim}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.EC_MISSION_CLAIM: claim.verify_task}


def verify_input(tool, value):
    try:
        module = TOOLS[Tool(tool)]
    except UNEXPECTED as error:
        return result(False, f"verifier-error: unknown tool {tool!r}: {error}")
    return module.verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    try:
        module = TOOLS[Tool(tool)]
    except UNEXPECTED as error:
        return result(False, f"verifier-error: unknown tool {tool!r}: {error}")
    return module.verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    try:
        check = TASKS[Task(task)]
    except UNEXPECTED as error:
        return result(False, f"verifier-error: unknown task {task!r}: {error}")
    return check(arguments, output, reference, workspace)
