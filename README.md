# TrainingLogChange

Change a recorded training activity: speed it up, move it to a different date,
and drop the sensor readings that are obviously wrong. Reads and writes **TCX**,
**FIT** and **GPX**.

## Formats

The tool started out TCX-only. Garmin now uploads **FIT** to Strava by default,
so the format the device actually produces was the one format it could not
touch; FIT and GPX were added for that reason.

| | TCX | FIT | GPX |
| --- | --- | --- | --- |
| What it is | Garmin Training Center XML | Garmin's binary activity format | The interchange format everything reads |
| Read and written with | `lxml` | `fit-tool` | `lxml` |
| Speed | `Speed`, `MaximumSpeed`, lap `MaxSpeed`/`AvgSpeed` | `speed`, `enhanced_speed`, `avg_speed`, `max_speed` | not in the format |
| Duration | `TotalTimeSeconds` | `total_elapsed_time`, `total_timer_time`, `total_moving_time` | not in the format |
| Heart rate | `HeartRateBpm` | `heart_rate` | `gpxtpx:hr` |
| Cadence | `Cadence`, `RunCadence` | `cadence` | `gpxtpx:cad` |
| Power | `Watts` | `power` | `gpxpx:PowerInWatts` or `<power>` |
| Summaries repaired | per lap | per lap and session | none to repair |

**The output is always the same format as the input.** Each modifier edits the
file in its own native representation -- a parsed XML tree, or decoded FIT
messages -- rather than projecting it onto a common model, so laps, vendor
extensions and FIT developer fields survive a load and save untouched. For FIT
that is exact: loading a file and saving it without asking for a change produces
the same bytes. Converting between formats is deliberately not supported; it
would mean dropping whatever the target format has no place for.

## Usage

```
training-log-change INPUT OUTPUT [--speedup S] [--max-hr N] [--max-power P]
                                 [--max-cadence C] [--start-date D]
```

`python main.py INPUT OUTPUT ...` works too, and the original underscored option
names (`--max_hr`, `--start_date`, ...) are still accepted.

| Argument | Type | Description |
| --- | --- | --- |
| `input` | path | Source `.tcx`, `.fit` or `.gpx` file |
| `output` | path | Where the result is written, in the same format |
| `--speedup`, `-s` | float | Speed multiplier: `1.1` makes the activity 10% faster |
| `--max-hr` | int | Heart rate readings above this are zeroed |
| `--max-power` | float | Power readings above this are zeroed |
| `--max-cadence` | int | Cadence readings above this are zeroed |
| `--start-date` | ISO 8601 | New start time, e.g. `2024-03-31T23:53:51.000Z` |

Options are independent and are applied in this order: power, cadence, heart
rate, speedup, start date. Asking for nothing is an error rather than a silent
copy.

Example -- make a ride 5% faster and move it to a different day:

```
training-log-change ride.fit ride_fixed.fit --speedup 1.05 \
    --start-date 2024-03-31T23:53:51.000Z
```

### What a speedup does

`--speedup 1.1` scales the recorded speeds up by 10%, scales the recorded
durations down, and pulls every timestamp towards the start of the activity so
the same track is covered in less time. The start does not move. Distance is
deliberately left alone: covering the same route in less time is exactly what
makes the activity faster.

GPX has neither speed nor duration in its schema, so there a speedup is entirely
a matter of compressing the timestamps, and the speed is whatever the reader
computes from the points.

Cadence is not scaled in any format. A rider who goes 10% faster has probably
changed gear rather than spun 10% faster, and guessing which would be worse than
leaving the recorded value alone.

### What a cleanup does

A power meter sometimes reports 2 kW for one second while the cyclist is not
pedalling at all, a magnetic cadence sensor reports 200 rpm, and a chest strap
losing contact reports a heart rate nobody can reach. `--max-power`,
`--max-cadence` and `--max-hr` zero those samples.

The lap that recorded the spike also summarises it, so zeroing the sample alone
would leave the lap claiming a peak that appears nowhere in its track. A summary
that is itself out of range (`MaximumHeartRateBpm`, `MaxWatts`,
`MaxBikeCadence`, `MaxRunCadence`; `max_heart_rate`, `max_power`, `max_cadence`,
`max_running_cadence` in FIT) is reset to the highest value the lap still has.
In FIT, records are a flat stream rather than children of a lap, so each lap and
session is repaired from the samples inside its own start-to-end window. GPX
records no summaries, so there is nothing to repair.

That replacement value has to come from somewhere. A lap whose track carries no
readings of the kind being cleaned falls back to the peak of the rest of the
activity, and if the file has no readings to go on at all the summaries are left
as recorded -- a lap reporting a maximum of zero beside a non-zero average is a
worse file than the one that came in.

Lap averages are left as recorded. Recomputing an average from unevenly spaced
samples is guesswork, and a wrong average is worse than a stale one.

### Timestamps

Timestamps are written back the way the file spelled them: TCX keeps its
milliseconds, GPX keeps its whole seconds, and a numeric UTC offset stays a
numeric UTC offset instead of being rewritten as if it were UTC.

FIT stores time in two shapes -- an instant, and the zone-less local wall clock
the athlete saw. The wall clock follows the instant recorded beside it, so its
UTC offset is preserved by both a speedup and a move.

## Development

Python 3.11+.

```
uv sync            # or: pip install -e . --group dev
pre-commit install
pytest
```

`pyproject.toml` holds the dependencies and the ruff, mypy and pytest
configuration. The pre-commit hooks run whitespace and line-ending checks, ruff,
ruff-format, mypy, and commitizen on the commit message.
