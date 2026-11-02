from .checks import DATA, UNEXPECTED, compared, plain, result
from .world import load_world, rates_view


def verify_input(value):
    try:
        countries = plain(value)["countries"]
        if not countries or len(set(countries)) != len(countries):
            return result(False, "countries must name at least one country, each once")
        return result(True, "input is valid")
    except UNEXPECTED as error:
        return result(False, f"input is invalid: {error!r}")


def verify_output(input_value, output_value, workspace):
    try:
        wanted = rates_view(load_world(DATA), plain(input_value)["countries"])
        return compared("get_country_rates", plain(output_value), wanted)
    except UNEXPECTED as error:
        return result(False, f"verifier-error: {error!r}")
