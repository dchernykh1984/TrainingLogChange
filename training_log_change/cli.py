"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime

from training_log_change.base import ActivityFormatError, TrackModifier
from training_log_change.factory import (
    MODIFIERS,
    UnsupportedFormatError,
    format_of,
    open_track,
)
from training_log_change.xml_base import parse_timestamp


def valid_date(text: str) -> datetime:
    parsed = parse_timestamp(text)
    if parsed is None:
        raise argparse.ArgumentTypeError(
            f"not a valid ISO 8601 date: '{text}'; expected something like "
            "'2024-03-31T23:53:51.000Z'"
        )
    return parsed[0]


def build_parser() -> argparse.ArgumentParser:
    supported = ", ".join(sorted(MODIFIERS))
    parser = argparse.ArgumentParser(
        prog="training-log-change",
        description=(
            "Change a recorded training activity: speed it up, move it in time "
            f"and drop bogus sensor readings. Supported formats: {supported}."
        ),
    )
    parser.add_argument("input", type=str, help="Input file path")
    parser.add_argument("output", type=str, help="Output file path")
    parser.add_argument(
        "--speedup",
        "-s",
        type=float,
        help="Speed multiplier, e.g. 1.1 for a 10%% speedup",
    )
    parser.add_argument(
        "--max-hr",
        "--max_hr",
        dest="max_hr",
        type=int,
        help="Zero heart rate readings above this value",
    )
    parser.add_argument(
        "--max-power",
        "--max_power",
        dest="max_power",
        type=float,
        help="Zero power readings above this value",
    )
    parser.add_argument(
        "--max-cadence",
        "--max_cadence",
        dest="max_cadence",
        type=int,
        help="Zero cadence readings above this value",
    )
    parser.add_argument(
        "--start-date",
        "--start_date",
        dest="start_date",
        type=valid_date,
        help="Move the activity to this start time, e.g. 2024-03-31T23:53:51.000Z",
    )
    return parser


def apply(modifier: TrackModifier, args: argparse.Namespace) -> list[str]:
    """Run the requested changes, in the order the original script used."""
    applied: list[str] = []
    if args.max_power is not None:
        modifier.cleanup_power(args.max_power)
        applied.append(f"power capped at {args.max_power}")
    if args.max_cadence is not None:
        modifier.cleanup_cadence(args.max_cadence)
        applied.append(f"cadence capped at {args.max_cadence}")
    if args.max_hr is not None:
        modifier.cleanup_heart_rate(args.max_hr)
        applied.append(f"heart rate capped at {args.max_hr}")
    if args.speedup is not None:
        modifier.speedup(args.speedup)
        applied.append(f"sped up by {args.speedup}")
    if args.start_date is not None:
        modifier.update_start_time(args.start_date)
        applied.append(f"start moved to {args.start_date.isoformat()}")
    return applied


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        source_format = format_of(args.input)
        if format_of(args.output) != source_format:
            parser.error(
                "input and output must be the same format; converting between "
                "formats is not supported"
            )
        modifier = open_track(args.input)
    except UnsupportedFormatError as exc:
        parser.error(str(exc))
    except (ActivityFormatError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    applied = apply(modifier, args)
    if not applied:
        print("nothing to do: no modification was requested", file=sys.stderr)
        return 1

    modifier.save(args.output)
    print(f"{args.input} -> {args.output}: {', '.join(applied)}")
    return 0
