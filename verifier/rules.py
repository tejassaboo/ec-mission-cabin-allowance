"""The toy EC Guide to Missions handbook as code: the oracle the reference tool and the verifier share.

Pure standard library and integer arithmetic only (money in EUR cents, time in whole minutes), so the
sandboxed verifier can run it. Vendored byte-identical into src/plugin/ and verifier/ (a test checks it).
Every constant and branch below is a rule or clarification of src/plugin/data/handbook.md.
"""

from .world import DIRECTIONS, utc_minute

THRESHOLD_MINUTES = 300  # C1: a segment of at least five hours' continuous flying time
MEETING_WINDOW = 180  # C2: "a meeting immediately after arrival" means within 0..180 minutes
BUFFER_MINUTES = {"air": 120, "rail": 60}  # C3: fixed time to reach the airport or station, each end
BAND_PERCENT = {"up_to_6h": 20, "over_6h_to_12h": 50, "over_12h_to_24h": 100}  # rule 6
MEAL_PERCENT = {"breakfast": 15, "lunch": 25, "dinner": 25}  # rule 8
HOTEL_BREAKFAST_PERCENT = 15  # rule 7
DAY_MINUTES = 1440


def half_up(numerator, denominator):
    """numerator / denominator rounded half up, for non-negative integers."""
    return (2 * numerator + denominator) // (2 * denominator)


def qualifying_segment(journey):
    """C1: the first segment, in travel order, with in_air_minutes >= 300; None when none (rail never qualifies)."""
    for segment in journey["segments"]:
        if segment["in_air_minutes"] is not None and segment["in_air_minutes"] >= THRESHOLD_MINUTES:
            return segment
    return None


def overnight_long_flight(journey):
    """C2: some segment of at least 300 minutes is an overnight flight."""
    return any(
        segment["in_air_minutes"] is not None and segment["in_air_minutes"] >= THRESHOLD_MINUTES and segment["overnight"]
        for segment in journey["segments"]
    )


def commitment_gap(journey):
    """Minutes from the journey's last arrival to its first commitment; None when there is no commitment."""
    if journey["first_commitment_utc"] is None:
        return None
    return utc_minute(journey["first_commitment_utc"]) - utc_minute(journey["segments"][-1]["arrive_utc"])


def meeting_on_arrival(journey):
    gap = commitment_gap(journey)
    return gap is not None and 0 <= gap <= MEETING_WINDOW


def journey_class(journey):
    """C1-C2: the class of one whole direction."""
    if journey["mode"] == "rail":
        return "rail_first_class"
    if qualifying_segment(journey) is None:
        return "economy"
    sold = journey["cabins_sold"]
    premium_suitable = not (overnight_long_flight(journey) and meeting_on_arrival(journey))
    if "premium_economy" in sold and premium_suitable:
        return "premium_economy"
    if "business" in sold:
        return "business"
    if "premium_economy" in sold:
        return "premium_economy"
    return "economy"


def mission_minutes(scenario):
    """C3: last arrival of the return - first departure of the outward journey + one buffer at each end."""
    outward, back = scenario["outward"], scenario["return_journey"]
    span = utc_minute(back["segments"][-1]["arrive_utc"]) - utc_minute(outward["segments"][0]["depart_utc"])
    return span + BUFFER_MINUTES[outward["mode"]] + BUFFER_MINUTES[back["mode"]]


def dsa_band(minutes):
    """Rule 6: up to and including 360 / more than 360 up to 720 / more than 720 up to 1440 / more than 1440."""
    if minutes <= 360:
        return "up_to_6h"
    if minutes <= 720:
        return "over_6h_to_12h"
    if minutes <= DAY_MINUTES:
        return "over_12h_to_24h"
    return "pro_rata"


def dsa_breakdown(rate, scenario):
    """C4-C5: (minutes, band, allowance before reductions, meal reductions, hotel-breakfast reductions, due)."""
    minutes = mission_minutes(scenario)
    band = dsa_band(minutes)
    daily = rate["daily_allowance_cents"]
    if band == "pro_rata":
        gross = half_up(daily * minutes, DAY_MINUTES)
        meal_base = daily
    else:
        gross = daily * BAND_PERCENT[band] // 100
        meal_base = gross  # a partial allowance is reduced from the amount received
    meals = sum(half_up(meal_base * MEAL_PERCENT[meal], 100) for meal in scenario["meals_provided"])
    breakfasts = sum(
        half_up(daily * HOTEL_BREAKFAST_PERCENT, 100) for night in scenario["hotel_nights"] if night["breakfast_included"]
    )
    return {
        "minutes": minutes,
        "band": band,
        "gross_cents": gross,
        "meal_reduction_cents": meals,
        "hotel_breakfast_reduction_cents": breakfasts,
        "due_cents": max(0, gross - meals - breakfasts),
    }


def night_ceiling(rate, night):
    """Rule 7: the hotel ceiling, raised by 15 % of the daily allowance when breakfast is in the room price."""
    raised = half_up(rate["daily_allowance_cents"] * HOTEL_BREAKFAST_PERCENT, 100) if night["breakfast_included"] else 0
    return rate["hotel_ceiling_cents"] + raised


def night_reimbursed(rate, night):
    """C6: the charged price when within the ceiling or over it solely because of local tax; else the ceiling."""
    ceiling = night_ceiling(rate, night)
    charged = night["room_rate_cents"] + night["local_tax_cents"]
    if charged <= ceiling or night["room_rate_cents"] <= ceiling:
        return charged
    return ceiling


def hotel_cents(rate, scenario):
    return sum(night_reimbursed(rate, night) for night in scenario["hotel_nights"])


def oracle(world, scenario):
    """The one correct claim for a scenario, as EcClaimOutput's plain JSON."""
    rate = world["countries"][scenario["destination_country"]]
    classes = {}
    for direction in DIRECTIONS:
        journey = scenario[direction]
        segment = qualifying_segment(journey)
        classes[direction] = (journey_class(journey), None if segment is None else segment["segment_id"])
    dsa = dsa_breakdown(rate, scenario)
    hotel = hotel_cents(rate, scenario)
    return {
        "rate_country": scenario["destination_country"],
        "outward_class": classes["outward"][0],
        "outward_qualifying_segment_id": classes["outward"][1],
        "return_class": classes["return_journey"][0],
        "return_qualifying_segment_id": classes["return_journey"][1],
        "mission_minutes": dsa["minutes"],
        "dsa_band": dsa["band"],
        "dsa_cents": dsa["due_cents"],
        "hotel_cents": hotel,
        "total_cents": dsa["due_cents"] + hotel,
    }
