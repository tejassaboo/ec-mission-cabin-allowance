# EC Mission Cabin Allowance

**No affiliation with the European Commission.**

A `nanoagent.plugin/v0001` plugin. An agent prepares one mission claim for a Brussels-based European
Commission staff member under a toy handbook paraphrased from the Commission's 2025 Guide to Missions
and Authorised Travel, C(2025) 2495 of 13 May 2025. It reads the mission, looks up the destination's
rate row, and submits a typed claim. A deterministic Python verifier, with no LLM, checks the claim
against an oracle that it computes itself.

## Task

- **Input:** `ScenarioInput` with a single field, `scenario`, which names one of eight bundled
  missions, for example `{"scenario": "mission-3318"}`.
- **Tools:** the agent calls `get_trip_request`, then `get_country_rates`, then `submit`. This is
  three of the six hosted steps.
- **Output:** `EcClaimOutput`, with these fields:
  - `rate_country`: the country whose rate row applies;
  - `outward_class` and `return_class`: economy, premium_economy, business or rail_first_class, one
    per direction, because the Guide judges the outward and return journeys separately;
  - `outward_qualifying_segment_id` and `return_qualifying_segment_id`: the first segment of at least
    300 flying minutes in that direction, or null;
  - `mission_minutes`, including the fixed rail (60) or air (120) allowance at each end;
  - `dsa_band`: up_to_6h, over_6h_to_12h, over_12h_to_24h or pro_rata;
  - `dsa_cents`, `hotel_cents` and `total_cents`, in EUR cents.
- **Success:** every field equals the one claim that the handbook's rules give.

The handbook is `src/plugin/data/handbook.md`. It is also the task's `instructions` in
`nanoagent.yaml`, and a test keeps the two identical. It has the pinned sources with their sha256
hashes, the paraphrased rules 1–10, the "Clarifications (toy rules)" C1–C9, the rules not in scope,
and the step plan.

| Scenario | Trap | Correct claim |
|---|---|---|
| `mission-4127` | One 299-min flight and a request for business "because it's basically five hours" | ES; economy / economy, no qualifying segment; 2330 min pro_rata; DSA 16342 + hotel 13800 = 30142 |
| `mission-5203` | 300 min qualifies, but it is a daytime flight, so premium economy, not the requested business; return 290 min stays economy; breakfast in the room raises the ceiling to 16915 | ES; premium_economy (O1) / economy; 3740 min; 26232 − 2×1515 = 23202 + 32000 = 55202 |
| `mission-3318` | A 140-min hop plus an overnight 300-min connecting flight: the whole outward direction qualifies, and the meeting 150 min after landing makes it business | ES; business (O2) / economy; 4605 min; 32299 − 2×2525 = 27249 + 29800 = 57049 |
| `mission-6044` | The outward legs (140, 170) do not qualify; the overnight 305-min return with a meeting 145 min after landing does. Exactly 1440 min, which is still the 100 % band | ES; economy / business (R1); 1440 min over_12h_to_24h; 10100 − 2525 = 7575 |
| `mission-2290` | Rail day trip: 240 min + 60 + 60 = 360, the top of the 20 % band; the breakfast reduction comes off the amount received | FR; rail_first_class both; 360 min up_to_6h; 2540 − 381 = 2159 |
| `mission-7712` | One minute more: 361 min, the 50 % band | FR; rail_first_class both; 361 min over_6h_to_12h; 6350 |
| `mission-8835` | Nights at exactly the €178 ceiling and at €178.01; a "Benelux" distractor quoting the Dutch ceiling | LU; rail_first_class both; 3647 min; 35963 + 17800 + 17800 = 71563 |
| `mission-9150` | UK rate row; €220 + €10 levy (over only because of the tax, so paid) vs €229 + €10 (room itself over, so capped at €226); a dinner provided | GB; rail_first_class both; 3609 min; 38095 − 3800 = 34295 + 23000 + 22600 = 79895 |

## Tools

| Tool | Does | Code |
|---|---|---|
| `get_trip_request` | Returns a scenario's mission: the performer's words, the destination country, the outward and return journeys (segments with UTC times, in-air minutes and overnight flags, end-to-end minute stamps, cabins sold, the first commitment after arrival), hotel nights and meals provided | `src/plugin/trip.py` |
| `get_country_rates` | Returns the daily allowance and hotel ceiling, in EUR cents, of each requested country, with the legal act that sets it. It applies no policy | `src/plugin/rates.py` |
| `compute_mission_claim` | The answer key: the oracle (`rules.oracle`) over the bundled fixtures. It is the task's `reference`, never shown to the agent | `src/plugin/reference.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `ec-mission-claim` | Works out an EC mission's travel class per direction, daily subsistence allowance and hotel reimbursement under the toy Guide to Missions handbook | `agent`, with `get_trip_request` and `get_country_rates`; reference `compute_mission_claim` |

## Environment

- Offline and self-contained. It uses `hosts: []`, an empty `.env`, and `write: []`, and has no clock.
- Fixtures are in `src/plugin/data/`:
  - `countries.json`: the 27 Member State rows of Regulation (EU) 2025/693 and the UK row of C(2026) 634, in EUR cents;
  - `scenarios/<id>.json`, hand-written, which holds facts only and never an answer; `request_text` is flavour, and every fact it mentions is also a typed field.
- Only UTC stamps are stored. `world.py` turns them into whole minutes since 2027-01-01T00:00Z with integer
  date arithmetic, and `get_trip_request` shows both, so neither the agent nor the verifier does timezone math.
- The plugin's core is `src/plugin/world.py` (fixture schema and loader, minute arithmetic, tool views) and the
  oracle `src/plugin/rules.py`. Both are vendored byte-identical into `verifier/`, and a test checks the copies.
- Python 3.12 or later, with dependencies pinned by `uv.lock`.

### Sources and their caveat

| Source | Version | Pinned copy (sha256) |
|---|---|---|
| Guide to Missions, C(2025) 2495 final | Commission Decision of 13.5.2025 | EMA annex `422471ab0b249edbed70d686e085fbae4d43726bd83e9abce2437172cc4f885b`; EU-Rail copy `34268dbf27090572c7608db77432129a24af9019a106fb76605b7e47f1c5a379` |
| Member State rates, Regulation (EU) 2025/693 | OJ 12.5.2025, in force 13.5.2025 | Council ST 6686/25 `72f2ead02e850a9b06b4306e72ffdca5f24542ce07121955d8d7881a506fd2c2` (table matches an OJ mirror) |
| UK rates, C(2026) 634 | 5.2.2026 | EU-Rail annex `ff4e39e7ec770c4be2f40e0c25a5078afb0b315d4f35da2662164d4b73f8a482` |

**EUR-Lex refused automated download**, so the pins above are EU-agency copies. A human should confirm
them against the EUR-Lex texts of C(2025) 2495 and Regulation (EU) 2025/693 before relying on them.

### Limitations

- The sources are agency-hosted copies; the EUR-Lex originals are unverified by hash (see above).
- The cabin rule's "when suitable" and "times of meetings" are judgment calls, settled by the toy rule C2
  (a 180-minute meeting window, overnight flag on the long segment). The Guide says premium economy
  "should be envisaged"; C2 makes that preference binding.
- "Overnight" is not defined by the Guide. C2 defines a segment's `overnight` flag as "under way at some minute
  from 00:00 to 04:59 UTC", which is within an hour of local night for every mission here (Western Europe,
  winter time). The fixtures carry the flag, `schema_problems` checks it against the definition, and the agent
  reads it rather than recomputing it.
- Scenario ids are neutral (`mission-<staff number>`). The first build used city-and-boundary ids such as
  `lille-rail-360`, and in three paid runs the model looked up the country's rates in the same step as it read
  the request, that is, from the id alone; the ids were renamed in the logic audit so that the tools alone
  carry the facts.
- How hotel-breakfast and meal reductions interact with a pro-rata allowance is not spelled out; C5 fixes it.
- Non-EU rates other than the UK exist only in a 2021 agency copy, so no scenario uses them.
- Fares, mission extensions, long stays and the other items under "Rules not in scope" are not modelled.

## Verifier

`verifier/claim.py` reads the fixtures through `Path(__file__)`, computes the oracle with the shared `rules.py`,
and checks the submission in four ordered stages. Each check has a stable reason code. The message names the
first failing check and its numbers (for example `no outward segment flies >= 300 min (O1 299 min), so economy`),
and later stages are skipped.

1. **Answer key:** `reference-matches-oracle`. The pinned reference must equal the verifier's own oracle.
2. **Referential integrity:**
   - `outward-segment-exists`
   - `return-segment-exists`
3. **Internal consistency:**
   - `outward-class-consistent` and `return-class-consistent`: rail gets rail_first_class and no segment; an
     above-economy air class names a segment of at least 300 minutes; the class is sold
   - `band-fits-minutes`
   - `amounts-not-negative`
   - `total-is-sum`
4. **Decision against the oracle:**
   - `rate-country-correct`
   - `outward-qualifying-correct`, `outward-class-correct`
   - `return-qualifying-correct`, `return-class-correct`
   - `mission-minutes-correct`
   - `dsa-band-correct`
   - `dsa-correct`
   - `hotel-correct`

How it scores:

- The score is 1.0 when the claim is valid and 0.0 otherwise.
- `details` holds every constraint and the expected claim, as plain JSON.
- Shape errors never reach the verifier, because NanoAgent's `build_output` refuses them first. These include a
  wrong type, an unknown Enum value, a missing or extra field, and `null` for a required field.
- The verifier is pure stdlib and never raises. An unknown task or tool id, or an unexpected value, becomes a
  `verifier-error` verdict.
- Tool outputs are also checked against the fixtures (`verify_output`).

## Validation

`tests/` covers the brief's whole test matrix:

- correct, incorrect, missing and malformed outputs, with malformed cases as `build_output` rejections;
- boundaries: 299/300 flying minutes; meeting gaps of −1/0/180/181; DSA bands at 360/361, 720/721 and
  1440/1441 minutes; a hotel night at the ceiling and one cent over; the breakfast-raised ceiling; local tax;
- the whole-direction rule against VT-style per-segment logic: a 140-min hop on a qualifying outward
  journey is booked in the direction's class, and outward and return are independent;
- consistency and uniqueness (at most one segment of 300+ minutes per direction, so "first" never decides, and
  no pro-rata or percentage amount lands on an exact half cent);
- oracle == the hand-written `tests/cases/<scenario>.json` for every scenario;
- the `rules.py` and `world.py` identity checks; handbook == `instructions`;
- fixture integrity (segments connect, in-air minutes equal the UTC span, minute stamps recomputed with `datetime`);
- tool-output size, kept under about 1k tokens, and a real MCP server round trip;
- the brief's §11 cross-policy row for EC, corrected: 360 + 420 legs gives business at the 300-minute threshold;
- a scripted, no-LLM end-to-end run per scenario: an agent written from the handbook alone follows the step plan,
  its gold answer passes, and broken answers fail with the expected reason code;
- structured input and output: every contract field is typed and described; the graded output holds only
  Enums, ints and segment ids; `request_text` is flavour only (the answer is unchanged when it is blanked);
- the verifier returns a failed verdict, and never raises, for an unknown task or tool id, an unknown rate
  country and malformed data;
- audit additions: UTC minute arithmetic across the DST change, midnight, a month end and a year end; a transit
  country never sets the rate; every fixture's `overnight` flag equals the C2 night window; scenario ids are
  neutral; "red-eye" and "long-haul" never appear as rule terms.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions, tools, the ec-mission-claim task and its handbook instructions
├── contract.py      # typed inputs and outputs of every tool and the task (Enums, int cents, int minutes)
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # empty: the plugin needs no environment variables
├── src/plugin/      # MCP server (__main__.py), tools, world.py (core), rules.py (oracle)
│   └── data/        # handbook.md, countries.json and scenarios/
├── tests/           # verifier matrix, oracle cases, scripted agent, rules, tools, fixtures, contract
├── ui/              # renderers.js and renderers.css: outputs drawn from their JSON Schema
├── product/         # product.yaml and icon.svg
└── verifier/        # deterministic verifier: claim.py (task), trip_request.py, rates.py, rules.py, world.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

To run the agent, use `nanoagent plugin agent config=agent.yaml home=<run folder>` with `arguments` set to a JSON
file such as `{"scenario": "mission-3318"}`. It needs `OPENROUTER_API_KEY` in the environment, not in
this repo.
