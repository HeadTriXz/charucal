"""Utilities for parsing arguments from CLI arguments."""

__all__ = [
    "add_camera_arguments",
    "add_pattern_arguments",
    "build_cameras",
    "build_pattern",
    "is_image_mode",
    "parse_aruco_dict",
    "parse_camera_sources",
    "parse_resolution",
]

import argparse
from pathlib import Path

import cv2

from charucal import CalibrationPattern


def add_camera_arguments(parser: argparse.ArgumentParser | argparse._ArgumentGroup) -> None:
    """Attach camera source arguments to an argument parser.

    :param parser: The argument parser to extend.
    """
    parser.add_argument(
        "--camera",
        dest="cameras",
        nargs="+",
        action="append",
        required=True,
        metavar="SOURCE",
        help="The camera index, video path, or image globs. Repeat for each physical camera.",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default=None,
        metavar="WIDTHxHEIGHT",
        help="The resolution to use for the live cameras (e.g. 1920x1080).",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        metavar="INT",
        help="The frames per second to use for the live cameras (e.g. 30).",
    )


def add_pattern_arguments(parser: argparse.ArgumentParser | argparse._ArgumentGroup) -> None:
    """Attach ChArUco pattern arguments to an argument parser.

    :param parser: The argument parser to extend.
    """
    group = parser.add_argument_group("ChArUco pattern")
    group.add_argument(
        "--width",
        type=int,
        required=True,
        metavar="INT",
        help="The number of squares along the horizontal axis.",
    )
    group.add_argument(
        "--height",
        type=int,
        required=True,
        metavar="INT",
        help="The number of squares along the vertical axis.",
    )
    group.add_argument(
        "--square-length",
        type=float,
        required=True,
        metavar="METERS",
        help="The physical side length of one chessboard square in meters.",
    )
    group.add_argument(
        "--marker-length",
        type=float,
        required=True,
        metavar="METERS",
        help="The physical side length of one ArUco marker in meters.",
    )
    group.add_argument(
        "--dict",
        dest="aruco_dict",
        type=parse_aruco_dict,
        default="DICT_4X4_100",
        metavar="NAME",
        help=(
            "The ArUco dictionary to use. Accepts the full attribute name (DICT_4X4_100), "
            "the short name (4X4_100), or the raw integer constant (default: DICT_4X4_100)."
        ),
    )
    group.add_argument(
        "--max-marker-error",
        type=float,
        default=0.005,
        metavar="FRACTION",
        help="How far off a marker may be, as a fraction of the image diagonal (default: 0.005).",
    )
    group.add_argument(
        "--min-inlier-ratio",
        type=float,
        default=0.8,
        metavar="RATIO",
        help="The share of the detected markers that has to match the board (default: 0.8).",
    )
    group.add_argument(
        "--check-markers",
        action="store_true",
        help="Also use OpenCV's own marker check, which often rejects boards seen at a steep angle.",
    )


def build_cameras(args: argparse.Namespace) -> list[cv2.VideoCapture]:
    """Construct a list of :class:`cv2.VideoCapture` objects from parsed CLI arguments.

    :param args: The parsed namespace.
    :return: The opened camera captures.
    :raises RuntimeError: If any camera source fails to open.
    """
    sources = parse_camera_sources(args.cameras)
    if len(set(sources)) != len(sources):
        raise RuntimeError("Duplicate camera sources are not allowed.")

    cameras: list[cv2.VideoCapture] = []
    for source in sources:
        camera = cv2.VideoCapture(source)
        if not camera.isOpened():
            raise RuntimeError(f"Failed to open camera '{source}'.")

        if args.resolution is not None:
            width, height = parse_resolution(args.resolution)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if args.fps is not None:
            camera.set(cv2.CAP_PROP_FPS, args.fps)

        cameras.append(camera)

    return cameras


def build_pattern(args: argparse.Namespace) -> CalibrationPattern:
    """Construct a :class:`~charucal.CalibrationPattern` from parsed CLI arguments.

    :param args: The parsed namespace.
    :return: The configured calibration pattern.
    """
    return CalibrationPattern(
        width=args.width,
        height=args.height,
        square_length=args.square_length,
        marker_length=args.marker_length,
        aruco_dict=args.aruco_dict,
        max_marker_error=args.max_marker_error,
        min_inlier_ratio=args.min_inlier_ratio,
        check_markers=args.check_markers,
    )


def is_image_mode(cameras: list[list[str]]) -> bool:
    """Check if the provided camera arguments refer to image sets rather than live devices.

    :param cameras: The nested list of strings provided via ``--camera`` flags.
    :return: Whether the provided cameras are images.
    """
    for cam_args in cameras:
        if len(cam_args) > 1:
            return True

        arg = cam_args[0]
        if any(char in arg for char in ("*", "?")):
            return True

        if Path(arg).suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"):
            return True

    return False


def parse_camera_sources(cameras: list[list[str]]) -> list[int | str]:
    """Parse nested camera argument lists into a flat list of typed sources.

    :param cameras: The nested list of strings provided via ``--camera`` flags.
    :return: A flat list of integer camera indices or string video paths.
    """
    return [int(cam[0]) if cam[0].isdigit() else cam[0] for cam in cameras]


def parse_aruco_dict(value: str) -> int:
    """Resolve an ArUco dictionary name or integer string to its OpenCV constant.

    :param value: The dictionary name (e.g. ``DICT_4X4_100`` or ``4X4_100``) or integer.
    :return: The OpenCV integer constant for the dictionary.
    :raises argparse.ArgumentTypeError: If the value is not a known ArUco dictionary.
    """
    try:
        return int(value)
    except ValueError:
        pass

    attr = value.upper()
    if not attr.startswith("DICT_"):
        attr = f"DICT_{attr}"

    if not hasattr(cv2.aruco, attr):
        raise argparse.ArgumentTypeError(
            f"Unknown ArUco dictionary '{value}'. Pass a DICT_* attribute name from cv2.aruco or its integer value."
        )

    return int(getattr(cv2.aruco, attr))


def parse_resolution(value: str) -> tuple[int, int]:
    """Parse a resolution string of the form ``WIDTHxHEIGHT`` into a tuple.

    :param value: The resolution string (e.g. ``1920x1080``).
    :return: The ``(width, height)`` integer tuple.
    :raises argparse.ArgumentTypeError: If the format is invalid.
    """
    parts = value.lower().split("x")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise argparse.ArgumentTypeError(
            f"Invalid resolution '{value}'. Expected format WIDTHxHEIGHT (e.g. 1920x1080)."
        )

    return int(parts[0]), int(parts[1])
