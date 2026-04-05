"""CLI tool for calibrating a multi-camera system using a ChArUco board."""

from __future__ import annotations

__all__ = ["add_arguments", "run"]

import argparse
import time

import cv2

from charucal.calibrate import CalibrationCapture, Calibrator
from charucal.cli.utils.args import (
    add_camera_arguments,
    add_pattern_arguments,
    build_cameras,
    build_pattern,
    is_image_mode,
)
from charucal.cli.utils.fmt import (
    Styled,
    fmt_controls,
    fmt_grids,
    fmt_header,
    fmt_kv,
    fmt_rule,
    print_error,
    print_success,
    print_warning,
)
from charucal.cli.utils.io import load_frame_set, read_frames, resolve_image_globs
from charucal.cli.utils.term import raw_terminal, read_keypress, redraw_block
from charucal.grid import CalibrationGrid

#: The duration to show temporary status messages after user actions (in seconds).
_STATUS_DURATION: float = 2.5


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register all arguments for the calibration tool.

    :param parser: The argument parser to populate.
    """
    add_pattern_arguments(parser)

    group = parser.add_argument_group("input")
    add_camera_arguments(group)

    group = parser.add_argument_group("output")
    group.add_argument(
        "--output",
        default="calibration.json",
        metavar="PATH",
        help="The destination path for the calibration JSON file.",
    )
    group.add_argument(
        "--ref-camera",
        type=int,
        default=None,
        metavar="INDEX",
        help="The reference camera index.",
    )


def run(args: argparse.Namespace) -> int:
    """Determine the input type and dispatch to the appropriate calibration mode.

    :param args: The parsed argument namespace.
    :return: The process exit code.
    """
    if is_image_mode(args.cameras):
        return _run_images(args)

    return _run_camera(args)


def _run_camera(args: argparse.Namespace) -> int:
    """Execute interactive live calibration from camera feeds.

    :param args: The parsed argument namespace.
    :return: The process exit code.
    """
    print(fmt_header("charucal  ·  calibrate", subtitle=f"Live capture  ·  {len(args.cameras)} camera(s)"))
    print()

    try:
        cameras = build_cameras(args)
    except RuntimeError as e:
        print_error(str(e))
        return 1

    pattern = build_pattern(args)
    calibrator = Calibrator(pattern, ref_idx=args.ref_camera)

    labels = [f"Camera {i + 1}" for i in range(len(args.cameras))]

    try:
        captures = _camera_capture_loop(cameras, calibrator, pattern.get_shape(), labels)
    except RuntimeError as e:
        print_error(str(e))
        return 1
    finally:
        for cam in cameras:
            cam.release()

    if captures is None:
        print_warning("Aborted.")
        return 1

    print()
    print(fmt_rule("Calibrating"))
    print()

    return _calibrate_and_save(calibrator, captures, args.output)


def _run_images(args: argparse.Namespace) -> int:
    """Execute calibration from pre-captured image sets.

    :param args: The parsed argument namespace.
    :return: The process exit code.
    """
    print(fmt_header("charucal  ·  calibrate", subtitle=f"Image sets  ·  {len(args.cameras)} camera(s)"))

    try:
        camera_paths = resolve_image_globs(args.cameras)
    except ValueError as e:
        print_error(str(e))
        return 1

    num_cameras = len(camera_paths)
    num_frames = len(camera_paths[0])
    labels = [f"Camera {i + 1}" for i in range(num_cameras)]

    print()
    print(fmt_kv("Cameras", str(num_cameras)))
    print(fmt_kv("Frames", str(num_frames)))
    print()

    pattern = build_pattern(args)
    calibrator = Calibrator(pattern, ref_idx=args.ref_camera)

    accepted: list[CalibrationCapture] = []
    skipped = 0
    rendered_lines = 0

    for frame_idx in range(num_frames):
        progress = f"  Processing  {frame_idx + 1} / {num_frames}  ·  {len(accepted)} accepted  ·  {skipped} skipped"
        rendered_lines = redraw_block(rendered_lines, progress)

        frames = load_frame_set(camera_paths, frame_idx)
        if frames is None:
            skipped += 1
            continue

        try:
            capture = calibrator.detect(frames)
        except ValueError:
            skipped += 1
            continue

        if capture.is_complete:
            accepted.append(capture)
        else:
            skipped += 1

    summary = f"  {Styled('●').bright_green()}  {len(accepted)} captures accepted  ·  {skipped} skipped"
    redraw_block(rendered_lines, summary)
    print("\n")

    if not accepted:
        print_error("No complete captures found. Check visibility across all cameras.")
        return 1

    captures = _images_review_loop(accepted, labels)
    if captures is None:
        print_warning("Aborted.")
        return 1

    print()
    print(fmt_rule("Calibrating"))
    print()

    return _calibrate_and_save(calibrator, captures, args.output)


def _fmt_capture_state(
    grids: list[CalibrationGrid],
    is_complete: bool,
    num_captures: int,
    status_msg: str,
    status_ok: bool,
    labels: list[str] | None = None,
) -> str:
    """Format the live capture UI block.

    :param grids: The detection grids for the current frame.
    :param is_complete: A flag for full board visibility across all cameras.
    :param num_captures: The count of saved captures.
    :param status_msg: A temporary status string shown after a user action.
    :param status_ok: A flag controlling whether the status is styled as success or warning.
    :param labels: The optional grid titles.
    :return: The formatted UI string.
    """
    parts: list[str] = [
        fmt_grids(grids, labels),
        "",
        fmt_kv("Captures saved", str(num_captures)),
    ]

    if status_msg:
        icon = Styled("✓").bright_green() if status_ok else Styled("⚠").yellow()
        parts.append(f"  {icon}  {status_msg}")
    elif is_complete:
        parts.append(f"  {Styled('●').bright_green()}  Ready to capture")
    else:
        parts.append(f"  {Styled('●').red()}  Waiting for board...")

    parts.append("")
    controls = [
        [("SPACE", "Capture", is_complete)],
        [("ENTER", "Calibrate", True), ("Q", "Abort", True)],
    ]
    parts.append(fmt_controls(controls))

    return "\n".join(parts)


def _fmt_review_state(
    grids: list[CalibrationGrid],
    idx: int,
    total: int,
    excluded: set[int],
    labels: list[str] | None = None,
) -> str:
    """Format the image review UI block.

    :param grids: The detection grids for the selected capture.
    :param idx: The current capture index.
    :param total: The total number of captures.
    :param excluded: The set of excluded capture indices.
    :param labels: The optional grid titles.
    :return: The formatted UI string.
    """
    included = total - len(excluded)
    is_excluded = idx in excluded

    toggle_label = "Include" if is_excluded else "Exclude"
    capture_status = f"  {Styled('●').red()}  Excluded" if is_excluded else f"  {Styled('●').bright_green()}  Included"

    parts = [
        fmt_grids(grids, labels),
        "",
        fmt_kv("Capture", f"{idx + 1} / {total}"),
        fmt_kv("Included", f"{included} / {total}"),
        capture_status,
        "",
        fmt_controls([
            [("h/←", "Prev", idx > 0), ("l/→", "Next", idx < total - 1), ("SPACE", toggle_label, True)],
            [("ENTER", "Calibrate", included > 0), ("Q", "Abort", True)],
        ]),
    ]

    return "\n".join(parts)


def _images_review_loop(
    accepted: list[CalibrationCapture],
    labels: list[str] | None = None,
) -> list[CalibrationCapture] | None:
    """Handle the interactive navigation and exclusion of pre-processed captures.

    :param accepted: The valid captures to review.
    :param labels: The optional grid titles.
    :return: The included captures, or ``None`` if the user aborts.
    """
    idx = 0
    excluded: set[int] = set()
    rendered_lines = 0

    try:
        with raw_terminal():
            while True:
                output = _fmt_review_state(accepted[idx].grids, idx, len(accepted), excluded, labels)
                rendered_lines = redraw_block(rendered_lines, output)

                match read_keypress():
                    case "h" | "\x1b[D":
                        idx = max(0, idx - 1)
                    case "l" | "\x1b[C":
                        idx = min(len(accepted) - 1, idx + 1)
                    case " ":
                        if idx in excluded:
                            excluded.remove(idx)
                        else:
                            excluded.add(idx)
                    case "\r" | "\n" if len(excluded) < len(accepted):
                        return [capture for i, capture in enumerate(accepted) if i not in excluded]
                    case "q" | "Q" | "\x1b":
                        return None

                time.sleep(0.05)
    except KeyboardInterrupt:
        return None


def _camera_capture_loop(
    cameras: list[cv2.VideoCapture],
    calibrator: Calibrator,
    board_shape: tuple[int, int],
    labels: list[str] | None = None,
) -> list[CalibrationCapture] | None:
    """Handle the interactive live capture process.

    :param cameras: The open camera handles.
    :param calibrator: The detection engine.
    :param board_shape: The ``(width, height)`` board dimensions in squares.
    :param labels: The optional grid titles.
    :return: The gathered captures, or ``None`` if the user aborts.
    """
    empty_grids = [CalibrationGrid.empty(board_shape) for _ in cameras]
    captures: list[CalibrationCapture] = []

    status_msg = ""
    status_ok = False
    status_expires = 0.0

    rendered_lines = 0

    try:
        with raw_terminal():
            while True:
                frames = read_frames(cameras)
                if frames is None:
                    raise RuntimeError("Camera stream interrupted.")

                try:
                    capture = calibrator.detect(frames)
                except ValueError:
                    capture = None

                if time.monotonic() > status_expires:
                    status_msg = ""

                is_complete = capture is not None and capture.is_complete
                grids = capture.grids if capture else empty_grids

                output = _fmt_capture_state(grids, is_complete, len(captures), status_msg, status_ok, labels)
                rendered_lines = redraw_block(rendered_lines, output)

                match read_keypress():
                    case " ":
                        if is_complete:
                            captures.append(capture)
                            status_msg = f"Capture {len(captures)} saved!"
                            status_ok = True
                        else:
                            status_msg = "Board not fully visible!"
                            status_ok = False

                        status_expires = time.monotonic() + _STATUS_DURATION
                    case "\r" | "\n":
                        return captures
                    case "q" | "Q" | "\x1b":
                        return None

                time.sleep(0.05)
    except KeyboardInterrupt:
        return None


def _calibrate_and_save(calibrator: Calibrator, captures: list[CalibrationCapture], output_path: str) -> int:
    """Perform final calibration math and write the result to disk.

    :param calibrator: The calibrator instance.
    :param captures: The list of captured frames to use.
    :param output_path: The destination file path.
    :return: The exit status.
    """
    try:
        result = calibrator.calibrate(*captures)
        result.save(output_path)
    except (ValueError, RuntimeError, OSError) as e:
        print_error(f"Failed: {e}")
        return 1

    print(fmt_kv("Result", f"Calibrated {result.num_cameras} cameras"))
    print_success(f"Saved to '{output_path}'")
    return 0
