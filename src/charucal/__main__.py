"""The main entry point for the charucal CLI tools."""

__all__ = ["main"]

import argparse
import io
import sys

from charucal.cli.commands import calibrate, preview


def main() -> None:
    """The main entry point for the charucal CLI tools."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="charucal",
        description="Multi-camera calibration using ChArUco boards.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    calibrate_parser = subparsers.add_parser("calibrate", help="Calibrate a multi-camera system.")
    calibrate.add_arguments(calibrate_parser)
    calibrate_parser.set_defaults(func=calibrate.run)

    preview_parser = subparsers.add_parser("preview", help="Preview the top-down result.")
    preview.add_arguments(preview_parser)
    preview_parser.set_defaults(func=preview.run)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
