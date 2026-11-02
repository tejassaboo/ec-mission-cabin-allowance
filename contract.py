"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GET_TRIP_REQUEST = "get_trip_request"
    GET_COUNTRY_RATES = "get_country_rates"
    COMPUTE_MISSION_CLAIM = "compute_mission_claim"


class Task(Enum):
    EC_MISSION_CLAIM = "ec-mission-claim"


class EcScenario(Enum):
    """One mission per member; its facts are bundled with the plugin."""

    MISSION_4127 = "mission-4127"
    MISSION_5203 = "mission-5203"
    MISSION_3318 = "mission-3318"
    MISSION_6044 = "mission-6044"
    MISSION_2290 = "mission-2290"
    MISSION_7712 = "mission-7712"
    MISSION_8835 = "mission-8835"
    MISSION_9150 = "mission-9150"


class Country(Enum):
    """ISO 3166-1 alpha-2 codes of every country with a bundled rate row: the 27 EU Member States and the UK."""

    AT = "AT"
    BE = "BE"
    BG = "BG"
    CY = "CY"
    CZ = "CZ"
    DE = "DE"
    DK = "DK"
    EE = "EE"
    ES = "ES"
    FI = "FI"
    FR = "FR"
    GB = "GB"
    GR = "GR"
    HR = "HR"
    HU = "HU"
    IE = "IE"
    IT = "IT"
    LT = "LT"
    LU = "LU"
    LV = "LV"
    MT = "MT"
    NL = "NL"
    PL = "PL"
    PT = "PT"
    RO = "RO"
    SE = "SE"
    SI = "SI"
    SK = "SK"


class RateSource(Enum):
    """The legal act a rate row comes from."""

    REG_EU_2025_693 = "reg_eu_2025_693"  # intra-EU scale, in force 13 May 2025
    C_2026_634 = "c_2026_634"  # amends C(2002) 98 to add the United Kingdom, 5 Feb 2026


class Mode(Enum):
    """The main means of transport of one direction of the mission."""

    AIR = "air"
    RAIL = "rail"


class AirCabin(Enum):
    """A cabin an air journey's fares are sold in."""

    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"


class TravelClass(Enum):
    """The class one direction of the mission may be booked in."""

    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    RAIL_FIRST_CLASS = "rail_first_class"


class DsaBand(Enum):
    """How the daily subsistence allowance is counted for the mission's duration."""

    UP_TO_6H = "up_to_6h"  # 20 % of the daily allowance
    OVER_6H_TO_12H = "over_6h_to_12h"  # 50 %
    OVER_12H_TO_24H = "over_12h_to_24h"  # 100 %
    PRO_RATA = "pro_rata"  # more than 24 hours: daily allowance x minutes / 1440


class Meal(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


@dataclass
class ScenarioInput(Output):
    scenario: Annotated[EcScenario, "Which mission to work, e.g. mission-3318"]


@dataclass
class MissionPerformer(Output):
    staff_id: Annotated[str, "Staff id, e.g. S4127"]
    name: Annotated[str, "The mission performer's full name (descriptive only)"]
    directorate_general: Annotated[str, "Commission department, e.g. DG MARE (descriptive only)"]


@dataclass
class Segment(Output):
    segment_id: Annotated[str, "Segment id, unique across the mission, e.g. O1 (outward) or R2 (return)"]
    service: Annotated[str, "Flight or train number as sold, e.g. AX 731 (descriptive only)"]
    origin: Annotated[str, "Three-letter IATA airport or station code of departure"]
    destination: Annotated[str, "Three-letter IATA airport or station code of arrival"]
    depart_utc: Annotated[str, "Departure, UTC, YYYY-MM-DDTHH:MMZ"]
    arrive_utc: Annotated[str, "Arrival, UTC, YYYY-MM-DDTHH:MMZ"]
    in_air_minutes: Annotated[int | None, "This one flight's continuous flying minutes, takeoff to landing; null for a train"]
    overnight: Annotated[
        bool, "True when this flight or train is under way at any minute from 00:00 to 04:59 UTC (toy rule C2); given, never recomputed"
    ]


@dataclass
class Journey(Output):
    mode: Annotated[Mode, "Main means of transport of this direction: air or rail"]
    segments: Annotated[list[Segment], "Flights or trains in travel order, at least one"]
    depart_utc: Annotated[str, "Departure of the first segment, UTC, YYYY-MM-DDTHH:MMZ"]
    depart_minute: Annotated[int, "The same departure as whole minutes since 2027-01-01T00:00Z"]
    arrive_utc: Annotated[str, "Arrival of the last segment, UTC, YYYY-MM-DDTHH:MMZ"]
    arrive_minute: Annotated[int, "The same arrival as whole minutes since 2027-01-01T00:00Z"]
    cabins_sold: Annotated[
        list[AirCabin], "Cabins sold on every segment of this air journey, each once, in order economy < premium_economy < business; empty for rail"
    ]
    first_commitment_utc: Annotated[
        str | None, "Start of the first meeting or work commitment after this journey arrives, UTC, YYYY-MM-DDTHH:MMZ; null for none"
    ]
    first_commitment_minute: Annotated[
        int | None, "The same commitment start as whole minutes since 2027-01-01T00:00Z; null for none"
    ]


@dataclass
class HotelNight(Output):
    night_of: Annotated[str, "The evening the night starts, YYYY-MM-DD, destination local"]
    room_rate_cents: Annotated[int, "Room price for this night, before local taxes, EUR cents"]
    local_tax_cents: Annotated[int, "Local accommodation tax added for this night, EUR cents; 0 for none"]
    breakfast_included: Annotated[bool, "True when the invoice states breakfast is included in the room price"]


@dataclass
class TripRequestOutput(Output):
    scenario: Annotated[EcScenario, "The scenario this mission belongs to"]
    request_text: Annotated[
        str,
        "The mission performer's words, for flavour only: every fact is in the typed fields below, and the words may ask for things policy forbids",
    ]
    mission_performer: Annotated[MissionPerformer, "Who travels; based in Brussels"]
    place_of_employment: Annotated[str, "City of the place of employment, where the mission starts and ends (descriptive only)"]
    destination_city: Annotated[str, "City where the mission is carried out (descriptive only)"]
    destination_country: Annotated[Country, "Country where the mission is carried out; its rate row applies"]
    outward: Annotated[Journey, "Travel from the place of employment to the mission destination"]
    return_journey: Annotated[Journey, "Travel from the mission destination back to the place of employment"]
    hotel_nights: Annotated[list[HotelNight], "Hotel invoice lines, one per night in date order; empty for no hotel"]
    meals_provided: Annotated[
        list[Meal], "Meals provided free by an institution or other organisation, one entry per meal, any order; empty for none"
    ]


@dataclass
class RatesInput(Output):
    countries: Annotated[list[Country], "Countries to look up, each once, e.g. [ES, FR]"]


@dataclass
class CountryRate(Output):
    country: Annotated[Country, "The country this row is for"]
    country_name: Annotated[str, "The country's English name (descriptive only)"]
    daily_allowance_cents: Annotated[int, "Full daily subsistence allowance for one day of mission, EUR cents"]
    hotel_ceiling_cents: Annotated[int, "Maximum hotel allowance per night, EUR cents"]
    source: Annotated[RateSource, "The legal act that sets this row"]


@dataclass
class RatesOutput(Output):
    rates: Annotated[list[CountryRate], "One row per requested country, in the order requested"]


@dataclass
class EcClaimOutput(Output):
    rate_country: Annotated[Country, "Country whose rate row the allowance and hotel ceiling use"]
    outward_class: Annotated[TravelClass, "Class the whole outward journey may be booked in"]
    outward_qualifying_segment_id: Annotated[
        str | None, "First outward segment, in travel order, with in_air_minutes >= 300; null when none qualifies"
    ]
    return_class: Annotated[TravelClass, "Class the whole return journey may be booked in"]
    return_qualifying_segment_id: Annotated[
        str | None, "First return segment, in travel order, with in_air_minutes >= 300; null when none qualifies"
    ]
    mission_minutes: Annotated[int, "Mission duration in minutes, including the fixed travel-time allowances (C3)"]
    dsa_band: Annotated[DsaBand, "Duration band the daily subsistence allowance is counted in"]
    dsa_cents: Annotated[int, "Daily subsistence allowance due after every reduction, EUR cents, at least 0"]
    hotel_cents: Annotated[int, "Hotel cost reimbursed over all nights, EUR cents; 0 for no hotel"]
    total_cents: Annotated[int, "dsa_cents + hotel_cents, EUR cents"]


TOOLS = {
    Tool.GET_TRIP_REQUEST: (ScenarioInput, TripRequestOutput),
    Tool.GET_COUNTRY_RATES: (RatesInput, RatesOutput),
    Tool.COMPUTE_MISSION_CLAIM: (ScenarioInput, EcClaimOutput),
}
TASKS = {Task.EC_MISSION_CLAIM: (ScenarioInput, EcClaimOutput)}
