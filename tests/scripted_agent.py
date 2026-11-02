"""A scripted agent with no LLM, written from the handbook (src/plugin/data/handbook.md) alone: it imports
nothing of the plugin's rules. It follows the step plan through a ``call(tool, arguments)`` function and
returns the submission it would make, so the tests can run each scenario end to end."""

from fractions import Fraction

ALLOWANCE = {"air": 120, "rail": 60}
MEAL = {"breakfast": Fraction(15, 100), "lunch": Fraction(25, 100), "dinner": Fraction(25, 100)}


def cents(value):
    """Round a non-negative Fraction half up to a whole cent."""
    return int(value + Fraction(1, 2))


def direction(journey):
    """(class, qualifying segment id) of one direction, per C1 and C2."""
    if journey["mode"] == "rail":
        return "rail_first_class", None
    long = [segment for segment in journey["segments"] if segment["in_air_minutes"] >= 300]
    if not long:
        return "economy", None
    overnight = any(segment["overnight"] for segment in long)
    commitment = journey["first_commitment_minute"]
    meeting = commitment is not None and 0 <= commitment - journey["arrive_minute"] <= 180
    sold = journey["cabins_sold"]
    if "premium_economy" in sold and not (overnight and meeting):
        return "premium_economy", long[0]["segment_id"]
    for cabin in ("business", "premium_economy"):
        if cabin in sold:
            return cabin, long[0]["segment_id"]
    return "economy", long[0]["segment_id"]


def run(scenario, call):
    """(the tool calls made, in order, as (tool, arguments); the submission)."""
    calls = [("get_trip_request", {"scenario": scenario})]
    mission = call(*calls[-1])
    country = mission["destination_country"]
    calls.append(("get_country_rates", {"countries": [country]}))
    rate = call(*calls[-1])["rates"][0]
    outward, back = mission["outward"], mission["return_journey"]
    minutes = back["arrive_minute"] - outward["depart_minute"] + ALLOWANCE[outward["mode"]] + ALLOWANCE[back["mode"]]
    daily = rate["daily_allowance_cents"]
    if minutes > 1440:
        band, amount, base = "pro_rata", cents(Fraction(daily * minutes, 1440)), daily
    else:
        band, share = next((name, share) for limit, name, share in ((360, "up_to_6h", 20), (720, "over_6h_to_12h", 50), (1440, "over_12h_to_24h", 100)) if minutes <= limit)
        amount = daily * share // 100
        base = amount
    reductions = sum(cents(base * MEAL[meal]) for meal in mission["meals_provided"])
    reductions += sum(cents(Fraction(daily * 15, 100)) for night in mission["hotel_nights"] if night["breakfast_included"])
    dsa = max(0, amount - reductions)
    hotel = 0
    for night in mission["hotel_nights"]:
        ceiling = rate["hotel_ceiling_cents"] + (cents(Fraction(daily * 15, 100)) if night["breakfast_included"] else 0)
        charge = night["room_rate_cents"] + night["local_tax_cents"]
        hotel += charge if night["room_rate_cents"] <= ceiling else ceiling
    outward_class, outward_segment = direction(outward)
    return_class, return_segment = direction(back)
    return calls, {
        "rate_country": country,
        "outward_class": outward_class,
        "outward_qualifying_segment_id": outward_segment,
        "return_class": return_class,
        "return_qualifying_segment_id": return_segment,
        "mission_minutes": minutes,
        "dsa_band": band,
        "dsa_cents": dsa,
        "hotel_cents": hotel,
        "total_cents": dsa + hotel,
    }
