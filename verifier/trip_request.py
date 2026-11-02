from .checks import UNEXPECTED, compared, fixtures, plain, result
from .world import trip_request


def verify_input(value):
    return result(True, "input is valid")  # a scenario Enum member is all the input there is


def verify_output(input_value, output_value, workspace):
    try:
        _, scenario = fixtures(plain(input_value)["scenario"])
        return compared("get_trip_request", plain(output_value), trip_request(scenario))
    except UNEXPECTED as error:
        return result(False, f"verifier-error: {error!r}")
