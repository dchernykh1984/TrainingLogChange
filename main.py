import argparse
from datetime import datetime

from tcx_modifier import TCXModifier


def valid_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
        return s
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


if __name__ == "__main__":
    # Function to validate and parse datetime string

    # Create the parser
    parser = argparse.ArgumentParser(description='Process input and output file paths, and other parameters.')

    # Add the arguments
    parser.add_argument('input', type=str, help='Input file path')
    parser.add_argument('output', type=str, help='Output file path')
    parser.add_argument('--speedup', '-s', type=float, required=False, help='Speedup percentage (float)')
    parser.add_argument('--max_hr', type=int, required=False, help='Maximal heart rate (integer)')
    parser.add_argument('--max_power', type=float, required=False, help='Maximal power (float)')
    parser.add_argument('--max_cadence', type=int, required=False, help='Maximal cadence (integer)')
    parser.add_argument('--start_date', type=valid_date, required=False,
                        help='Start date time in format "%Y-%m-%dT%H:%M:%S.%fZ"')
    args = parser.parse_args()

    print(f"{args.speedup=}")
    print(f"{args.max_hr=}")
    print(f"{args.max_power=}")
    print(f"{args.max_cadence=}")
    print(f"{args.start_date=}")

    modifier = TCXModifier(args.input)
    if args.max_power:
        modifier.cleanup_power(args.max_power)
    if args.max_cadence:
        modifier.cleanup_canence(args.max_cadence)
    if args.max_hr:
        modifier.cleanup_heart_rate(args.max_hr)
    if args.speedup:
        modifier.speedup(args.speedup)
    if args.start_date:
        modifier.update_start_time(args.start_date)
    modifier.save(args.output)
