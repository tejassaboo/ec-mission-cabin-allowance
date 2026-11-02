from slimconfig import build_output

from contract import RatesInput, RatesOutput
from plugin.fixtures import world
from plugin.world import rates_view


def get_country_rates(given: RatesInput) -> RatesOutput:
    """The daily allowance and hotel ceiling of each requested country. It applies no policy."""
    countries = [country.value for country in given.countries]
    if not countries or len(set(countries)) != len(countries):
        raise ValueError("countries must name at least one country, each once")
    return build_output(rates_view(world(), countries), RatesOutput)
