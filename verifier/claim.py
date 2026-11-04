"""The ec-mission-claim verdict, and the checks of its reference tool compute_mission_claim.

The verifier computes the correct claim itself (rules.oracle over the bundled fixtures) and checks the
submitted one against it in stages, each a list of constraints with stable ids (the reason codes):

1. answer key: the pinned reference equals the verifier's own oracle (else the plugin is broken);
2. referential integrity: each qualifying segment id names a segment of that direction;
3. internal consistency: each direction's class agrees with its mode and qualifying segment, the band
   agrees with the submitted minutes, amounts are not negative, and the total is the sum;
4. policy decision against the oracle: rate country, each direction's qualifying segment and class,
   mission minutes, band, allowance, hotel.

A stage is checked only when every earlier stage holds, and every constraint of a stage is checked.
The message names the first failing constraint and how many more fail. Stage 3 pins the band to the
submitted minutes, so dsa-band-correct can only fail alongside mission-minutes-correct, which comes
first: it is never the headline, but it names the band's own mistake in the constraint list. Shape
problems (types, Enum values, missing or extra fields) never get here: NanoAgent's build_output refuses
them first. The score is 1.0 when every constraint holds, else 0.0.
"""

from .checks import UNEXPECTED, fixtures, plain, result
from .rules import (
    BAND_PERCENT,
    BUFFER_MINUTES,
    MEETING_WINDOW,
    THRESHOLD_MINUTES,
    commitment_gap,
    dsa_band,
    dsa_breakdown,
    night_ceiling,
    night_reimbursed,
    oracle,
    overnight_long_flight,
    qualifying_segment,
)
from .world import utc_minute

DIRECTION_NAMES = {"outward": "outward", "return": "return_journey"}

TEXT = {
    "reference-matches-oracle": "The pinned answer key equals the verifier's own oracle",
    "outward-segment-exists": "outward_qualifying_segment_id is null or names an outward segment",
    "return-segment-exists": "return_qualifying_segment_id is null or names a return segment",
    "outward-class-consistent": "The outward class agrees with its mode and qualifying segment",
    "return-class-consistent": "The return class agrees with its mode and qualifying segment",
    "band-fits-minutes": "dsa_band is the band of the submitted mission_minutes (rule 6, C4)",
    "amounts-not-negative": "mission_minutes is positive; dsa_cents and hotel_cents are at least 0",
    "total-is-sum": "total_cents equals dsa_cents + hotel_cents (C8)",
    "rate-country-correct": "The rate row is the mission country's (C7)",
    "outward-qualifying-correct": "The outward qualifying segment is the one C1 gives",
    "outward-class-correct": "The outward class is the one C1-C2 give",
    "return-qualifying-correct": "The return qualifying segment is the one C1 gives",
    "return-class-correct": "The return class is the one C1-C2 give",
    "mission-minutes-correct": "mission_minutes follows C3",
    "dsa-band-correct": "dsa_band follows rule 6 and C4 for the correct minutes",
    "dsa-correct": "dsa_cents follows C4-C5",
    "hotel-correct": "hotel_cents follows C6",
}


def verify_input(value):
    return result(True, "input is valid")  # a scenario Enum member is all the input there is


def verify_output(input_value, output_value, workspace):
    try:
        world, scenario = fixtures(plain(input_value)["scenario"])
        key = oracle(world, scenario)
        if plain(output_value) != key:
            return result(False, "compute_mission_claim differs from the verifier's oracle", expected=key)
        return result(True, "the answer key matches the verifier's oracle")
    except UNEXPECTED as error:
        return result(False, f"verifier-error: {error!r}")


def verify_task(arguments, output, reference, workspace):
    try:
        world, scenario = fixtures(plain(arguments)["scenario"])
        key = oracle(world, scenario)
        pinned = None if reference is None else plain(reference)
        given = plain(output)
        if not isinstance(given, dict) or sorted(given) != sorted(key):
            return result(False, "verifier-error: the output is not an EcClaimOutput", expected=key)
        return judge(world, scenario, key, pinned, given)
    except UNEXPECTED as error:
        return result(False, f"verifier-error: {error!r}")


def judge(world, scenario, key, pinned, given):
    rate = world["countries"][scenario["destination_country"]]
    stages = [
        [("reference-matches-oracle", lambda: reference_problem(key, pinned))],
        [
            ("outward-segment-exists", lambda: exists_problem(scenario, given, "outward")),
            ("return-segment-exists", lambda: exists_problem(scenario, given, "return")),
        ],
        [
            ("outward-class-consistent", lambda: consistency_problem(scenario, given, "outward")),
            ("return-class-consistent", lambda: consistency_problem(scenario, given, "return")),
            ("band-fits-minutes", lambda: band_fit_problem(given)),
            ("amounts-not-negative", lambda: range_problem(given)),
            ("total-is-sum", lambda: total_problem(given)),
        ],
        [
            ("rate-country-correct", lambda: country_problem(scenario, key, given)),
            ("outward-qualifying-correct", lambda: qualifying_problem(scenario, key, given, "outward")),
            ("outward-class-correct", lambda: class_problem(scenario, key, given, "outward")),
            ("return-qualifying-correct", lambda: qualifying_problem(scenario, key, given, "return")),
            ("return-class-correct", lambda: class_problem(scenario, key, given, "return")),
            ("mission-minutes-correct", lambda: minutes_problem(scenario, key, given)),
            ("dsa-band-correct", lambda: band_problem(key, given)),  # implied by the two checks above
            ("dsa-correct", lambda: dsa_problem(rate, scenario, key, given)),
            ("hotel-correct", lambda: hotel_problem(rate, scenario, key, given)),
        ],
    ]
    constraints, blocked = [], None
    for stage in stages:
        for identifier, check in stage:
            if blocked is not None:
                constraints.append(entry(identifier, None, None, None, f"not checked: {blocked} failed"))
                continue
            problem = check()
            if problem is None:
                constraints.append(entry(identifier, True, None, None, ""))
            else:
                constraints.append(entry(identifier, False, *problem))
        failed = [item for item in constraints if item["ok"] is False]
        if failed and blocked is None:
            blocked = failed[0]["id"]
    failed = [item for item in constraints if item["ok"] is False]
    if not failed:
        return result(True, f"the claim is correct: {summary(given)}", constraints=constraints, expected=key)
    more = f" (+{len(failed) - 1} more)" if len(failed) > 1 else ""
    return result(False, f"{failed[0]['id']}: {failed[0]['message']}{more}", constraints=constraints, expected=key)


def entry(identifier, ok, expected, actual, message):
    return {"id": identifier, "constraint": TEXT[identifier], "ok": ok, "expected": expected, "actual": actual, "message": message}


def summary(claim):
    return (
        f"outward {claim['outward_class']}, return {claim['return_class']}, {claim['mission_minutes']} min "
        f"({claim['dsa_band']}), DSA {claim['dsa_cents']} + hotel {claim['hotel_cents']} = {claim['total_cents']} cents"
    )


def journey(scenario, side):
    return scenario[DIRECTION_NAMES[side]]


def segment_of(scenario, side, segment_id):
    return next((item for item in journey(scenario, side)["segments"] if item["segment_id"] == segment_id), None)


def reference_problem(key, pinned):
    if pinned is not None and pinned != key:
        return key, pinned, "the pinned answer key differs from the verifier's oracle, so the plugin itself is broken"
    return None


def exists_problem(scenario, given, side):
    segment_id = given[f"{side}_qualifying_segment_id"]
    if segment_id is None or segment_of(scenario, side, segment_id) is not None:
        return None
    ids = [item["segment_id"] for item in journey(scenario, side)["segments"]]
    return ids, segment_id, f"{segment_id!r} is not a {side} segment; the {side} segments are {', '.join(ids)}"


def consistency_problem(scenario, given, side):
    trip, chosen, segment_id = journey(scenario, side), given[f"{side}_class"], given[f"{side}_qualifying_segment_id"]
    if trip["mode"] == "rail":
        if chosen != "rail_first_class" or segment_id is not None:
            return ["rail_first_class", None], [chosen, segment_id], (
                f"the {side} journey is by rail, so its class is rail_first_class and it has no qualifying segment"
            )
        return None
    if chosen == "rail_first_class":
        return None, chosen, f"the {side} journey is by air, so rail_first_class cannot apply"
    if segment_id is None:
        if chosen != "economy":
            return "economy", chosen, f"{chosen} on the {side} journey needs a qualifying segment of >= {THRESHOLD_MINUTES} min, and none is named"
        return None
    minutes = segment_of(scenario, side, segment_id)["in_air_minutes"]
    if minutes < THRESHOLD_MINUTES:
        return THRESHOLD_MINUTES, minutes, f"named qualifying segment {segment_id} flies {minutes} min, which is not >= {THRESHOLD_MINUTES}"
    if chosen not in trip["cabins_sold"]:
        return trip["cabins_sold"], chosen, f"{chosen} is not sold on the {side} journey (sold: {', '.join(trip['cabins_sold'])})"
    return None


def band_fit_problem(given):
    minutes = given["mission_minutes"]
    if minutes <= 0:
        return None  # amounts-not-negative reports it
    band = dsa_band(minutes)
    if given["dsa_band"] != band:
        return band, given["dsa_band"], f"{minutes} min falls in band {band}, not {given['dsa_band']}"
    return None


def range_problem(given):
    bad = {name: given[name] for name in ("dsa_cents", "hotel_cents") if given[name] < 0}
    if given["mission_minutes"] <= 0:
        bad["mission_minutes"] = given["mission_minutes"]
    if bad:
        return None, bad, "out of range: " + ", ".join(f"{name} {value}" for name, value in sorted(bad.items()))
    return None


def total_problem(given):
    wanted = given["dsa_cents"] + given["hotel_cents"]
    if given["total_cents"] != wanted:
        return wanted, given["total_cents"], (
            f"total {given['total_cents']} != dsa {given['dsa_cents']} + hotel {given['hotel_cents']} = {wanted}"
        )
    return None


def country_problem(scenario, key, given):
    if given["rate_country"] == key["rate_country"]:
        return None
    return key["rate_country"], given["rate_country"], (
        f"the mission is carried out in {scenario['destination_city']}, {scenario['destination_country']}, "
        f"so {scenario['destination_country']}'s row applies, not {given['rate_country']}'s"
    )


def flights(trip):
    return ", ".join(f"{item['segment_id']} {item['in_air_minutes']} min" for item in trip["segments"])


def qualifying_problem(scenario, key, given, side):
    """Stage 3 already pinned a rail direction to null and a named segment to >= 300 min, so a difference
    here is an air direction with a long segment that the submission did not name (or named a later one)."""
    name = f"{side}_qualifying_segment_id"
    if given[name] == key[name]:
        return None
    trip = journey(scenario, side)
    long = qualifying_segment(trip)
    return key[name], given[name], (
        f"{long['segment_id']} is the first {side} segment with >= {THRESHOLD_MINUTES} min ({flights(trip)}); "
        f"one such segment qualifies the whole {side} journey"
    )


def class_problem(scenario, key, given, side):
    """Stage 3 already pinned rail to rail_first_class and a direction with no long segment to economy, so a
    difference here is a qualifying air direction booked in the wrong one of its sold cabins (C2)."""
    name = f"{side}_class"
    if given[name] == key[name]:
        return None
    trip = journey(scenario, side)
    gap = commitment_gap(trip)
    meeting = "no commitment after arrival" if gap is None else f"the first commitment is {gap} min after arrival (window 0 to {MEETING_WINDOW})"
    overnight = "an overnight" if overnight_long_flight(trip) else "no overnight"
    return key[name], given[name], (
        f"the {side} journey qualifies; it has {overnight} long flight and {meeting}; "
        f"sold: {', '.join(trip['cabins_sold'])}, so {key[name]} (C2)"
    )


def minutes_problem(scenario, key, given):
    if given["mission_minutes"] == key["mission_minutes"]:
        return None
    outward, back = scenario["outward"], scenario["return_journey"]
    span = utc_minute(back["segments"][-1]["arrive_utc"]) - utc_minute(outward["segments"][0]["depart_utc"])
    return key["mission_minutes"], given["mission_minutes"], (
        f"return arrival - outward departure = {span} min, plus {BUFFER_MINUTES[outward['mode']]} ({outward['mode']}) "
        f"+ {BUFFER_MINUTES[back['mode']]} ({back['mode']}) = {key['mission_minutes']}"
    )


def band_problem(key, given):
    if given["dsa_band"] == key["dsa_band"]:
        return None
    return key["dsa_band"], given["dsa_band"], f"{key['mission_minutes']} min is band {key['dsa_band']}"


def dsa_problem(rate, scenario, key, given):
    if given["dsa_cents"] == key["dsa_cents"]:
        return None
    parts = dsa_breakdown(rate, scenario)
    daily = rate["daily_allowance_cents"]
    if parts["band"] == "pro_rata":
        how = f"{daily} x {parts['minutes']} / 1440 = {parts['gross_cents']} (half up)"
    else:
        how = f"{BAND_PERCENT[parts['band']]} % of {daily} = {parts['gross_cents']}"
    return key["dsa_cents"], given["dsa_cents"], (
        f"{how}, minus meals {parts['meal_reduction_cents']}, minus hotel breakfasts "
        f"{parts['hotel_breakfast_reduction_cents']} = {parts['due_cents']}"
    )


def hotel_problem(rate, scenario, key, given):
    if given["hotel_cents"] == key["hotel_cents"]:
        return None
    nights = [
        f"{night['night_of']}: room {night['room_rate_cents']} + tax {night['local_tax_cents']} vs ceiling "
        f"{night_ceiling(rate, night)} -> {night_reimbursed(rate, night)}"
        for night in scenario["hotel_nights"]
    ]
    return key["hotel_cents"], given["hotel_cents"], "; ".join(nights) or "no hotel nights"
