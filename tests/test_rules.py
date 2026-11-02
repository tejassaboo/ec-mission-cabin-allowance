"""The handbook's rules on synthetic missions: every threshold at N and N+1, the whole-direction rule
against VT-style per-segment logic, the meeting window, the bands, rounding, reductions and the hotel."""

import pytest

from plugin.fixtures import world
from plugin.rules import (
    dsa_band,
    dsa_breakdown,
    half_up,
    hotel_cents,
    journey_class,
    mission_minutes,
    night_reimbursed,
    oracle,
    qualifying_segment,
)
from plugin.world import is_overnight, utc_minute

SOLD = ["economy", "premium_economy", "business"]
SPAIN = {"daily_allowance_cents": 10100, "hotel_ceiling_cents": 15400}


def stamp(minute):
    """The UTC stamp of a minute count from 2027-03-01T00:00Z (all within March 2027)."""
    day, rest = divmod(minute, 1440)
    return f"2027-03-{day + 1:02d}T{rest // 60:02d}:{rest % 60:02d}Z"


def flight(segment_id, start, minutes, overnight=False, origin="BRU", destination="LPA"):
    return {
        "segment_id": segment_id,
        "service": "AX 1",
        "origin": origin,
        "destination": destination,
        "depart_utc": stamp(start),
        "arrive_utc": stamp(start + minutes),
        "in_air_minutes": minutes,
        "overnight": overnight,
    }


def air(*segments, commitment_after=None, sold=SOLD):
    arrive = utc_minute(segments[-1]["arrive_utc"]) - utc_minute("2027-03-01T00:00Z")
    commitment = None if commitment_after is None else stamp(arrive + commitment_after)
    return {"mode": "air", "segments": list(segments), "cabins_sold": list(sold), "first_commitment_utc": commitment}


def rail(segment_id, start, minutes):
    segment = {**flight(segment_id, start, minutes), "in_air_minutes": None, "origin": "ZYR", "destination": "XDB"}
    return {"mode": "rail", "segments": [segment], "cabins_sold": [], "first_commitment_utc": None}


def mission(outward, back, nights=(), meals=(), country="ES"):
    return {
        "scenario": "synthetic",
        "request_text": "",
        "mission_performer": {"staff_id": "S1", "name": "Test", "directorate_general": "DG TEST"},
        "place_of_employment": "Brussels",
        "destination_city": "Somewhere",
        "destination_country": country,
        "outward": outward,
        "return_journey": back,
        "hotel_nights": list(nights),
        "meals_provided": list(meals),
    }


@pytest.mark.parametrize(("minutes", "cabin"), [(299, "economy"), (300, "premium_economy"), (301, "premium_economy")])
def test_the_five_hour_threshold_is_at_least_300(minutes: int, cabin: str) -> None:
    assert journey_class(air(flight("O1", 600, minutes))) == cabin


def test_one_long_connecting_segment_qualifies_the_whole_direction() -> None:
    outward = air(flight("O1", 600, 140, destination="MAD"), flight("O2", 800, 300, origin="MAD"))
    assert qualifying_segment(outward)["segment_id"] == "O2"
    assert journey_class(outward) == "premium_economy"
    # VT-style per-segment logic would book the 140-minute hop in economy and only O2 above it. Here the
    # class belongs to the direction: the output has one outward class, and it is above economy.
    vt_style = ["economy" if segment["in_air_minutes"] < 300 else "premium_economy" for segment in outward["segments"]]
    assert vt_style == ["economy", "premium_economy"]
    assert {journey_class(outward)} != set(vt_style)


def test_legs_never_add_up() -> None:
    outward = air(flight("O1", 600, 200, destination="MAD"), flight("O2", 900, 200, origin="MAD"))
    assert qualifying_segment(outward) is None and journey_class(outward) == "economy"


def test_the_first_qualifying_segment_is_named() -> None:
    outward = air(flight("O1", 0, 320, destination="MAD"), flight("O2", 400, 400, origin="MAD"))
    assert qualifying_segment(outward)["segment_id"] == "O1"


def test_outward_and_return_are_judged_independently() -> None:
    facts = mission(air(flight("O1", 600, 290)), air(flight("R1", 3000, 300, origin="LPA", destination="BRU")))
    claim = oracle(world(), facts)
    assert (claim["outward_class"], claim["outward_qualifying_segment_id"]) == ("economy", None)
    assert (claim["return_class"], claim["return_qualifying_segment_id"]) == ("premium_economy", "R1")


@pytest.mark.parametrize(
    ("gap", "overnight", "cabin"),
    [
        (None, True, "premium_economy"),
        (-1, True, "premium_economy"),
        (0, True, "business"),
        (180, True, "business"),
        (181, True, "premium_economy"),
        (0, False, "premium_economy"),
    ],
)
def test_meeting_window_and_overnight(gap, overnight: bool, cabin: str) -> None:
    assert journey_class(air(flight("O1", 1300, 300, overnight=overnight), commitment_after=gap)) == cabin


def test_overnight_must_be_the_long_segment() -> None:
    journey = air(flight("O1", 0, 140, overnight=True, destination="MAD"), flight("O2", 200, 300, origin="MAD"), commitment_after=30)
    assert journey_class(journey) == "premium_economy"


@pytest.mark.parametrize(
    ("sold", "overnight", "cabin"),
    [
        (["economy", "business"], False, "business"),
        (["economy", "premium_economy"], True, "premium_economy"),
        (["economy"], True, "economy"),
        (["economy"], False, "economy"),
    ],
)
def test_cabins_sold_fall_back_in_order(sold, overnight: bool, cabin: str) -> None:
    assert journey_class(air(flight("O1", 1300, 300, overnight=overnight), commitment_after=60, sold=sold)) == cabin


def test_rail_is_first_class_and_never_qualifies() -> None:
    journey = rail("O1", 0, 400)
    assert journey_class(journey) == "rail_first_class" and qualifying_segment(journey) is None


@pytest.mark.parametrize(
    ("minutes", "band"),
    [(1, "up_to_6h"), (360, "up_to_6h"), (361, "over_6h_to_12h"), (720, "over_6h_to_12h"), (721, "over_12h_to_24h"), (1440, "over_12h_to_24h"), (1441, "pro_rata")],
)
def test_band_boundaries(minutes: int, band: str) -> None:
    assert dsa_band(minutes) == band


def test_buffers_follow_each_direction_s_mode() -> None:
    assert mission_minutes(mission(rail("O1", 0, 35), rail("R1", 205, 35))) == 240 + 120
    assert mission_minutes(mission(air(flight("O1", 0, 60)), air(flight("R1", 180, 60, origin="LPA", destination="BRU")))) == 240 + 240
    assert mission_minutes(mission(air(flight("O1", 0, 60)), rail("R1", 180, 60))) == 240 + 180


@pytest.mark.parametrize(("span", "dsa"), [(1200, 10100), (1201, 10107)])
def test_24_hours_exactly_is_a_full_day_and_one_minute_more_is_pro_rata(span: int, dsa: int) -> None:
    facts = mission(air(flight("O1", 0, 60)), air(flight("R1", span - 60, 60, origin="LPA", destination="BRU")))
    assert dsa_breakdown(SPAIN, facts)["due_cents"] == dsa  # 10100 x 1441 / 1440 = 10107.01


def test_pro_rata_rounds_half_up() -> None:
    assert [half_up(n, 2) for n in (1, 3, 4)] == [1, 2, 2]
    assert half_up(10100 * 2330, 1440) == 16342  # 16342.36


def test_meal_reductions_come_off_the_amount_received_in_short_bands() -> None:
    short = mission(rail("O1", 0, 35), rail("R1", 205, 35), meals=["breakfast"])  # 360 min: 20 % of 10100 = 2020
    assert dsa_breakdown(SPAIN, short)["meal_reduction_cents"] == 303  # 15 % of 2020
    half = mission(rail("O1", 0, 35), rail("R1", 206, 35), meals=["lunch", "dinner"])  # 361: 50 % = 5050
    assert dsa_breakdown(SPAIN, half)["meal_reduction_cents"] == 2 * 1263  # 25 % of 5050 = 1262.5 -> 1263
    long = mission(rail("O1", 0, 35), rail("R1", 2000, 35), meals=["lunch"])
    assert dsa_breakdown(SPAIN, long)["meal_reduction_cents"] == 2525  # pro rata: 25 % of the full 10100


def test_reductions_never_take_the_allowance_below_zero() -> None:
    facts = mission(rail("O1", 0, 35), rail("R1", 100, 35), meals=["breakfast", "lunch", "dinner", "lunch", "dinner", "lunch"])
    assert dsa_breakdown(SPAIN, facts)["due_cents"] == 0


def night(room, tax=0, breakfast=False):
    return {"night_of": "2027-03-01", "room_rate_cents": room, "local_tax_cents": tax, "breakfast_included": breakfast}


@pytest.mark.parametrize(
    ("room", "tax", "breakfast", "paid"),
    [
        (15400, 0, False, 15400),  # exactly the ceiling
        (15401, 0, False, 15400),  # one cent over
        (15000, 900, False, 15900),  # over only because of local tax: deemed authorised
        (15400, 900, False, 16300),
        (15401, 900, False, 15400),  # the room itself is over: capped, tax and all
        (16915, 0, True, 16915),  # ceiling raised by 15 % of 10100 = 1515
        (16916, 0, True, 16915),
    ],
)
def test_hotel_night_ceiling(room: int, tax: int, breakfast: bool, paid: int) -> None:
    assert night_reimbursed(SPAIN, night(room, tax, breakfast)) == paid


def test_breakfast_in_the_room_reduces_the_allowance_per_night() -> None:
    facts = mission(rail("O1", 0, 35), rail("R1", 2900, 35), nights=[night(15000, breakfast=True), night(15000)])
    parts = dsa_breakdown(SPAIN, facts)
    assert parts["hotel_breakfast_reduction_cents"] == 1515
    assert hotel_cents(SPAIN, facts) == 30000


def test_cross_policy_sanity_row_ec() -> None:
    # Brief section 11, corrected (TIER2_DESIGNS.md): leg 1 = 360 in air, layover 90, leg 2 = 420 in air.
    # Some segment >= 300, so the direction qualifies; under the sanity assumptions (premium economy not
    # sold, or an overnight flight with a meeting on arrival) the class is business.
    legs = (flight("L1", 0, 360, destination="DXB"), flight("L2", 450, 420, overnight=True, origin="DXB"))
    assert [segment["in_air_minutes"] for segment in legs] == [360, 420]
    assert utc_minute(legs[1]["arrive_utc"]) - utc_minute(legs[0]["depart_utc"]) == 870
    assert journey_class(air(*legs, sold=["economy", "business"])) == "business"
    assert journey_class(air(*legs, commitment_after=60)) == "business"
    assert journey_class(air(*legs)) == "premium_economy"  # "when suitable": no meeting on arrival


@pytest.mark.parametrize("text", ["2027-02-29T10:00Z", "2027-03-01T24:00Z", "2027-03-01 10:00Z", "2027-13-01T10:00Z"])
def test_stamps_must_be_real(text: str) -> None:
    with pytest.raises(ValueError):
        utc_minute(text)


def test_minute_stamps() -> None:
    assert utc_minute("2027-01-01T00:00Z") == 0
    assert utc_minute("2027-03-01T00:00Z") == (31 + 28) * 1440
    assert utc_minute("2028-03-01T00:00Z") - utc_minute("2028-02-28T00:00Z") == 2 * 1440  # 2028 is a leap year


def test_utc_minute_arithmetic_ignores_the_dst_change() -> None:
    # EU clocks go forward at 2027-03-28T01:00Z. Stamps are UTC, so a span across it is still six hours,
    # although Brussels wall clocks would show seven; and a span across midnight or a month end is plain minutes.
    assert utc_minute("2027-03-28T04:00Z") - utc_minute("2027-03-27T22:00Z") == 360
    assert utc_minute("2027-03-01T00:01Z") - utc_minute("2027-02-28T23:59Z") == 2
    assert utc_minute("2028-01-01T00:30Z") - utc_minute("2027-12-31T23:30Z") == 60


def test_a_transit_country_never_sets_the_rate() -> None:
    # Brussels to Las Palmas through Lisbon: the mission is in Spain, so Spain's 10100 applies, not Portugal's 9500.
    outward = air(flight("O1", 600, 150, destination="LIS"), flight("O2", 800, 180, origin="LIS"))
    back = air(flight("R1", 3000, 290, origin="LPA", destination="BRU"))
    claim = oracle(world(), mission(outward, back, country="ES"))
    assert claim["rate_country"] == "ES"
    assert claim["dsa_cents"] == half_up(10100 * claim["mission_minutes"], 1440)


@pytest.mark.parametrize(
    ("depart", "arrive", "overnight"),
    [
        ("2027-03-09T22:00Z", "2027-03-10T03:05Z", True),  # crosses midnight
        ("2027-02-15T23:30Z", "2027-02-16T04:30Z", True),
        ("2027-03-09T19:00Z", "2027-03-09T21:20Z", False),  # evening, lands before midnight
        ("2027-03-09T23:00Z", "2027-03-09T23:59Z", False),  # ends one minute before the window
        ("2027-03-09T23:00Z", "2027-03-10T00:01Z", True),  # under way at 00:00Z
        ("2027-03-10T04:59Z", "2027-03-10T07:00Z", True),  # departs in the last minute of the window
        ("2027-03-10T05:00Z", "2027-03-10T07:00Z", False),  # departs as the window ends
        ("2027-03-09T07:00Z", "2027-03-09T12:00Z", False),
    ],
)
def test_the_overnight_flag_is_the_c2_night_window(depart: str, arrive: str, overnight: bool) -> None:
    assert is_overnight(depart, arrive) is overnight
