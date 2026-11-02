"""Shared core of this plugin: the fixture schema and loader, date and UTC-minute arithmetic, and the tool
views the tools and the verifier both build.

Pure standard library (json, re, pathlib) and no clock, so the sandboxed verifier can run it too. It is
vendored byte-identical into src/plugin/ and verifier/ (a test checks the two copies). Times are UTC
stamps turned into whole minutes here: nothing does timezone arithmetic or uses datetime.
"""

import json
import re
from pathlib import Path

DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
UTC_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})Z")
CODE = re.compile(r"[A-Z]{3}")
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
EPOCH = "2027-01-01"  # minute stamps count whole minutes from 2027-01-01T00:00Z

COUNTRY_KEYS = ("country", "country_name", "daily_allowance_cents", "hotel_ceiling_cents", "source")
SCENARIO_KEYS = (
    "scenario",
    "request_text",
    "mission_performer",
    "place_of_employment",
    "destination_city",
    "destination_country",
    "outward",
    "return_journey",
    "hotel_nights",
    "meals_provided",
)
JOURNEY_KEYS = ("mode", "segments", "cabins_sold", "first_commitment_utc")
SEGMENT_KEYS = ("segment_id", "service", "origin", "destination", "depart_utc", "arrive_utc", "in_air_minutes", "overnight")
NIGHT_KEYS = ("night_of", "room_rate_cents", "local_tax_cents", "breakfast_included")
DIRECTIONS = ("outward", "return_journey")


def day_number(text):
    """Days from 1970-01-01 to the date YYYY-MM-DD; ValueError for anything but a real calendar date."""
    match = DATE.fullmatch(text)
    if match is None:
        raise ValueError(f"{text!r} is not a YYYY-MM-DD date")
    year, month, day = (int(part) for part in match.groups())
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if not 1 <= month <= 12 or not 1 <= day <= MONTH_DAYS[month - 1] + (month == 2 and leap):
        raise ValueError(f"{text!r} is not a calendar date")
    shifted = year - (month <= 2)  # Howard Hinnant's days_from_civil
    era = shifted // 400
    year_of_era = shifted - era * 400
    day_of_year = (153 * ((month + 9) % 12) + 2) // 5 + day - 1
    return era * 146097 + year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year - 719468


def utc_minute(stamp):
    """Whole minutes from 2027-01-01T00:00Z to the UTC stamp YYYY-MM-DDTHH:MMZ."""
    match = UTC_STAMP.fullmatch(stamp)
    if match is None:
        raise ValueError(f"{stamp!r} is not a YYYY-MM-DDTHH:MMZ stamp")
    date, hours, minutes = match.group(1), int(match.group(2)), int(match.group(3))
    if hours > 23 or minutes > 59:
        raise ValueError(f"{stamp!r} is not a time of day")
    return (day_number(date) - day_number(EPOCH)) * 1440 + hours * 60 + minutes


def load_world(data):
    """The rate table, keyed by country code, from data/countries.json."""
    rows = json.loads((Path(data) / "countries.json").read_text(encoding="utf-8"))
    return {"countries": {row["country"]: row for row in rows}}


def load_scenario(data, scenario_id):
    """One scenario's facts, from data/scenarios/<id>.json; ValueError for an unknown id."""
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(scenario_id)):
        raise ValueError(f"{scenario_id!r} is not a scenario id")
    path = Path(data) / "scenarios" / f"{scenario_id}.json"
    if not path.is_file():
        raise ValueError(f"no scenario {scenario_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def journey_view(journey):
    """A journey as get_trip_request shows it: the stored facts plus its end-to-end UTC stamps and minutes."""
    segments = journey["segments"]
    commitment = journey["first_commitment_utc"]
    return {
        "mode": journey["mode"],
        "segments": [dict(segment) for segment in segments],
        "depart_utc": segments[0]["depart_utc"],
        "depart_minute": utc_minute(segments[0]["depart_utc"]),
        "arrive_utc": segments[-1]["arrive_utc"],
        "arrive_minute": utc_minute(segments[-1]["arrive_utc"]),
        "cabins_sold": list(journey["cabins_sold"]),
        "first_commitment_utc": commitment,
        "first_commitment_minute": None if commitment is None else utc_minute(commitment),
    }


def trip_request(scenario):
    """The get_trip_request output for a scenario: its facts, never an answer."""
    view = {key: scenario[key] for key in SCENARIO_KEYS}
    for direction in DIRECTIONS:
        view[direction] = journey_view(scenario[direction])
    return view


def rates_view(world, countries):
    """The get_country_rates output: one row per requested country, in the order requested."""
    return {"rates": [dict(world["countries"][country]) for country in countries]}


def schema_problems(world, scenario):
    """Every way the fixtures break their schema, as messages; [] when they hold."""
    problems = []
    for code, row in world["countries"].items():
        if tuple(row) != COUNTRY_KEYS:
            problems.append(f"country {code}: keys {list(row)}")
    if tuple(scenario) != SCENARIO_KEYS:
        problems.append(f"scenario keys {list(scenario)}")
        return problems
    if scenario["destination_country"] not in world["countries"]:
        problems.append(f"no rate row for {scenario['destination_country']}")
    seen = []
    for direction in DIRECTIONS:
        journey = scenario[direction]
        if tuple(journey) != JOURNEY_KEYS or not journey["segments"]:
            problems.append(f"{direction}: keys {list(journey)} or no segments")
            continue
        for segment in journey["segments"]:
            if tuple(segment) != SEGMENT_KEYS:
                problems.append(f"{direction} segment keys {list(segment)}")
                continue
            seen.append(segment["segment_id"])
            span = utc_minute(segment["arrive_utc"]) - utc_minute(segment["depart_utc"])
            if span <= 0:
                problems.append(f"segment {segment['segment_id']} arrives before it leaves")
            if journey["mode"] == "air" and segment["in_air_minutes"] != span:
                problems.append(f"segment {segment['segment_id']}: in_air_minutes {segment['in_air_minutes']} != {span}")
            if journey["mode"] == "rail" and segment["in_air_minutes"] is not None:
                problems.append(f"rail segment {segment['segment_id']} has in_air_minutes")
            if not (CODE.fullmatch(segment["origin"]) and CODE.fullmatch(segment["destination"])):
                problems.append(f"segment {segment['segment_id']}: bad codes")
        for earlier, later in zip(journey["segments"], journey["segments"][1:]):
            if earlier["destination"] != later["origin"] or utc_minute(later["depart_utc"]) < utc_minute(earlier["arrive_utc"]):
                problems.append(f"{direction}: {earlier['segment_id']} does not connect to {later['segment_id']}")
        if (journey["mode"] == "rail") != (journey["cabins_sold"] == []):
            problems.append(f"{direction}: cabins_sold must be empty exactly for rail")
    if len(set(seen)) != len(seen):
        problems.append("segment ids repeat")
    outward, back = scenario["outward"]["segments"], scenario["return_journey"]["segments"]
    if outward[-1]["destination"] != back[0]["origin"] or outward[0]["origin"] != back[-1]["destination"]:
        problems.append("the return journey does not mirror the outward journey's ends")
    if utc_minute(back[0]["depart_utc"]) <= utc_minute(outward[-1]["arrive_utc"]):
        problems.append("the return leaves before the outward journey arrives")
    for night in scenario["hotel_nights"]:
        if tuple(night) != NIGHT_KEYS:
            problems.append(f"hotel night keys {list(night)}")
        else:
            day_number(night["night_of"])
    return problems
