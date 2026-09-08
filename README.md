# TrainingLogChange

Scripts for modifying a recorded training log: speeding the track up/down, shifting the
start date and cleaning up bogus sensor readings.

## Which format was chosen: TCX

The original README said the choice between **FIT** and **GPX** had not been made yet.
Looking at the code, the question is settled: the implementation works with **TCX**
(Garmin Training Center XML, `.tcx`).

Evidence in the code:

* [tcx_modifier.py](tcx_modifier.py) defines `TCXModifier`, the only modifier class in the repo, and
  [main.py](main.py) uses it directly.
* The file is parsed as XML with `lxml.etree` ([tcx_modifier.py:26](tcx_modifier.py#L26)) and written back
  with an XML declaration in UTF-8 ([tcx_modifier.py:34-40](tcx_modifier.py#L34-L40)).
* The tags it reads and rewrites are TCX-specific: `TotalTimeSeconds`, `MaximumSpeed`,
  `Speed`, `Time`, `StartTime`, `Lap/@StartTime`, `HeartRateBpm/Value`
  ([tcx_modifier.py:16-22](tcx_modifier.py#L16-L22)). Tags are matched by local name
  (`element.tag.split("}")[-1]`), so the TCX namespaces -- including the
  `ActivityExtension` namespace that carries power and cadence -- are handled transparently.

Why TCX rather than the alternatives:

* **GPX** is a route format. It carries track points and time, but heart rate, power,
  cadence and lap summaries (`TotalTimeSeconds`, `MaximumSpeed`) only exist there as
  vendor extensions, so a speed-up would have to rewrite half-standardised data.
* **FIT** is a compact binary format. Editing it means a dedicated encoder/decoder
  library and re-writing CRCs and message definitions; there is nothing to eyeball
  when a value comes out wrong.
* **TCX** is plain XML with all the fields this tool touches already in the schema, so
  it can be edited with a stock XML library and diffed by hand. Garmin Connect, Strava
  and most other services both export and import it.

## Usage

```
python main.py INPUT OUTPUT [--speedup S] [--max_hr N] [--max_power P] [--max_cadence C] [--start_date D]
```

| Argument | Type | Description |
| --- | --- | --- |
| `input` | path | Source `.tcx` file |
| `output` | path | Where the modified `.tcx` is written |
| `--speedup`, `-s` | float | Speed multiplier: `1.1` makes the activity 10% faster. Scales `Speed`/`MaximumSpeed` up and `TotalTimeSeconds` down, and compresses every `Time` towards the start of the activity |
| `--max_hr` | int | Heart rate values above this are treated as sensor errors |
| `--max_power` | float | Power values above this are treated as sensor errors and zeroed (a power meter can report ~2 kW for a second while the rider is not pedalling at all) |
| `--max_cadence` | int | Cadence values above this are treated as sensor errors and zeroed (a magnetic cadence sensor can report ~200 rpm for a second) |
| `--start_date` | `%Y-%m-%dT%H:%M:%S.%fZ` | New start time, e.g. `2024-03-31T23:53:51.000Z`. Every `Time` and each `Lap/@StartTime` is shifted by the same offset |

Example -- make a ride 5% faster and move it to a different day:

```
python main.py ride.tcx ride_fixed.tcx --speedup 1.05 --start_date 2024-03-31T23:53:51.000Z
```

The options are independent and are applied in this order: power cleanup, cadence
cleanup, heart rate cleanup, speed-up, start date.

## Requirements

Python 3.11+ and [lxml](https://lxml.de/). Dependencies and the lint/type/test tooling
are declared in `pyproject.toml`:

```
uv sync            # or: pip install -e . --group dev
pre-commit install
```

## Status

All operations are implemented for TCX: `speedup`, `update_start_time` and the
`cleanup_*` family.

A cleanup zeroes the out-of-range samples and then repairs the lap summary above
them (`MaximumHeartRateBpm`, `MaxWatts`, `MaxBikeCadence`, `MaxRunCadence`), so a
lap cannot keep claiming a peak that no longer appears in its track. Lap
averages are left as recorded.
