"""CLI tool for previewing the top-down calibration result for a multi-camera system."""

from __future__ import annotations

__all__ = ["add_arguments", "run"]

import argparse
import time

import cv2

from charucal.calibrate import CalibrationResult
from charucal.cli.utils.args import (
    add_camera_arguments,
    build_cameras,
    is_image_mode,
    parse_resolution,
)
from charucal.cli.utils.fmt import fmt_controls, fmt_header, fmt_kv, fmt_rule, print_error
from charucal.cli.utils.io import load_frame_set, read_frames, resolve_image_globs
from charucal.cli.utils.term import redraw_block
from charucal.transform import CameraTransformer, RenderDistance

#: The name of the preview window.
_WINDOW_NAME = "charucal preview"

#: The smoothing factor for the FPS estimate, where ``1.0`` means no smoothing and lower values increase smoothing.
_FPS_SMOOTHING = 0.1

_QUIT_CHARS = frozenset({ord("q"), ord("Q"), 27})
_PREV_CHARS = frozenset({ord("h"), ord("H")})
_NEXT_CHARS = frozenset({ord("l"), ord("L")})
_ARROW_PREV = frozenset({65361, 2424832})
_ARROW_NEXT = frozenset({65363, 2555904})


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register all arguments for the preview tool.

    :param parser: The argument parser to populate.
    """
    parser.add_argument(
        "calibration",
        metavar="CALIBRATION",
        help="The path to the calibration JSON file.",
    )

    group = parser.add_argument_group("input")
    add_camera_arguments(group)

    group = parser.add_argument_group("render")
    group.add_argument(
        "--output-size",
        type=parse_resolution,
        default=(720, 720),
        metavar="WIDTHxHEIGHT",
        help="The maximum output canvas size in pixels (default: 720x720).",
    )
    group.add_argument(
        "--front",
        type=float,
        default=10.0,
        metavar="METERS",
        help="How far to show in front of the origin, in meters (default: 10.0).",
    )
    group.add_argument(
        "--side",
        type=float,
        default=5.0,
        metavar="METERS",
        help="How far to show to each side of the origin, in meters (default: 5.0).",
    )
    group.add_argument(
        "--rear",
        type=float,
        default=0.0,
        metavar="METERS",
        help="How far to show behind the origin, in meters (default: 0.0).",
    )
    group.add_argument(
        "--nearest",
        action="store_true",
        help="Use nearest-neighbor interpolation instead of bilinear for maximum throughput.",
    )


def run(args: argparse.Namespace) -> int:
    """Determine the input type and dispatch to the appropriate preview mode.

    :param args: The parsed argument namespace.
    :return: The process exit code.
    """
    try:
        calibration = CalibrationResult.load(args.calibration)
    except (ValueError, OSError) as e:
        print_error(str(e))
        return 1

    try:
        render_distance = RenderDistance(front=args.front, side=args.side, rear=args.rear)
    except ValueError as e:
        print_error(str(e))
        return 1

    interpolation = cv2.INTER_NEAREST if args.nearest else cv2.INTER_LINEAR

    if is_image_mode(args.cameras):
        return _run_images(args, calibration, render_distance, interpolation)

    return _run_camera(args, calibration, render_distance, interpolation)


def _run_camera(
    args: argparse.Namespace,
    calibration: CalibrationResult,
    render_distance: RenderDistance,
    interpolation: int,
) -> int:
    """Preview live camera feeds in top-down view.

    :param args: The parsed argument namespace.
    :param calibration: The loaded calibration result.
    :param render_distance: The physical scene extents to render.
    :param interpolation: The OpenCV interpolation flag.
    :return: The process exit code.
    """
    print(fmt_header("charucal  ·  preview", subtitle=f"Live capture  ·  {len(args.cameras)} camera(s)"))
    print()

    try:
        cameras = build_cameras(args)
    except RuntimeError as e:
        print_error(str(e))
        return 1

    exit_code = 0
    try:
        frames = read_frames(cameras)
        if frames is None:
            print_error("Failed to read initial frames from cameras.")
            return 1

        try:
            transformer = CameraTransformer(
                calibration,
                render_distance=render_distance,
                output_shape=args.output_size,
                input_shapes=[(f.shape[1], f.shape[0]) for f in frames],
                interpolation=interpolation,
            )
        except (ValueError, RuntimeError) as e:
            print_error(str(e))
            return 1

        cv2.namedWindow(_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

        prev_time = time.monotonic()
        fps = 0.0
        rendered_lines = 0

        while True:
            frames = read_frames(cameras)
            if frames is None:
                print_error("Camera stream interrupted.")
                exit_code = 1
                break

            now = time.monotonic()
            elapsed = now - prev_time
            prev_time = now
            if elapsed > 0.0:
                fps += _FPS_SMOOTHING * (1.0 / elapsed - fps)

            cv2.imshow(_WINDOW_NAME, transformer.transform(frames))

            rendered_lines = redraw_block(rendered_lines, _fmt_live_state(fps, transformer, render_distance))

            key = cv2.waitKeyEx(1)
            if _is_quit_key(key) or cv2.getWindowProperty(_WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        for cam in cameras:
            cam.release()

        cv2.destroyAllWindows()

    return exit_code


def _run_images(
    args: argparse.Namespace,
    calibration: CalibrationResult,
    render_distance: RenderDistance,
    interpolation: int,
) -> int:
    """Preview pre-captured image sets in top-down view.

    :param args: The parsed argument namespace.
    :param calibration: The loaded calibration result.
    :param render_distance: The physical scene extents to render.
    :param interpolation: The OpenCV interpolation flag.
    :return: The process exit code.
    """
    print(fmt_header("charucal  ·  preview", subtitle=f"Image sets  ·  {len(args.cameras)} camera(s)"))
    print()

    try:
        camera_paths = resolve_image_globs(args.cameras)
    except ValueError as e:
        print_error(str(e))
        return 1

    num_frames = len(camera_paths[0])

    first_frames = load_frame_set(camera_paths, 0)
    if first_frames is None:
        print_error("Failed to load the first frame set.")
        return 1

    try:
        transformer = CameraTransformer(
            calibration,
            render_distance=render_distance,
            output_shape=args.output_size,
            input_shapes=[(f.shape[1], f.shape[0]) for f in first_frames],
            interpolation=interpolation,
        )
    except (ValueError, RuntimeError) as e:
        print_error(str(e))
        return 1

    cv2.namedWindow(_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

    frame_idx = 0
    needs_redraw = True
    rendered_lines = 0

    while True:
        if needs_redraw:
            frame_set = load_frame_set(camera_paths, frame_idx)
            if frame_set is not None:
                cv2.imshow(_WINDOW_NAME, transformer.transform(frame_set))
                cv2.setWindowTitle(_WINDOW_NAME, f"charucal preview  -  Frame {frame_idx + 1} / {num_frames}")

            needs_redraw = False

        rendered_lines = redraw_block(
            rendered_lines, _fmt_image_state(frame_idx, num_frames, transformer, render_distance)
        )

        key = cv2.waitKeyEx(50)
        if _is_quit_key(key) or cv2.getWindowProperty(_WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break

        new_idx = frame_idx
        if _is_prev_key(key):
            new_idx = max(0, frame_idx - 1)
        elif _is_next_key(key):
            new_idx = min(num_frames - 1, frame_idx + 1)

        if new_idx != frame_idx:
            frame_idx = new_idx
            needs_redraw = True

    cv2.destroyAllWindows()
    return 0


def _fmt_live_state(fps: float, transformer: CameraTransformer, render_distance: RenderDistance) -> str:
    """Format the live preview terminal block.

    :param fps: The current frames-per-second estimate.
    :param transformer: The active camera transformer.
    :param render_distance: The physical scene extents being rendered.
    :return: The formatted terminal block string.
    """
    w, h = transformer.output_shape
    parts = [
        fmt_rule("Preview"),
        fmt_kv("Output size", f"{w} x {h} px"),
        fmt_kv("Scale", f"{transformer.pixels_per_meter:.1f} px / m"),
        fmt_kv("Front distance", f"{render_distance.front:.1f} m"),
        fmt_kv("Side distance", f"{render_distance.side:.1f} m"),
        fmt_kv("Rear distance", f"{render_distance.rear:.1f} m"),
        fmt_kv("FPS", f"{fps:.1f}"),
        "",
        fmt_controls([[("Q / ESC", "Quit", True)]]),
    ]
    return "\n".join(parts)


def _fmt_image_state(
    frame_idx: int,
    total: int,
    transformer: CameraTransformer,
    render_distance: RenderDistance,
) -> str:
    """Format the image-set preview terminal block.

    :param frame_idx: The zero-based index of the currently displayed frame.
    :param total: The total number of frames in the image set.
    :param transformer: The active camera transformer.
    :param render_distance: The physical scene extents being rendered.
    :return: The formatted terminal block string.
    """
    w, h = transformer.output_shape
    parts = [
        fmt_rule("Preview"),
        fmt_kv("Output size", f"{w} x {h} px"),
        fmt_kv("Scale", f"{transformer.pixels_per_meter:.1f} px / m"),
        fmt_kv("Front distance", f"{render_distance.front:.1f} m"),
        fmt_kv("Side distance", f"{render_distance.side:.1f} m"),
        fmt_kv("Rear distance", f"{render_distance.rear:.1f} m"),
        fmt_kv("Frame", f"{frame_idx + 1} / {total}"),
        "",
        fmt_controls([
            [("h/←", "Prev", frame_idx > 0), ("l/→", "Next", frame_idx < total - 1)],
            [("Q / ESC", "Quit", True)],
        ]),
    ]
    return "\n".join(parts)


def _is_quit_key(key: int) -> bool:
    """Check whether a ``cv2.waitKeyEx`` code signals quit.

    :param key: The raw key code returned by ``cv2.waitKeyEx``.
    :return: Whether the key is a quit signal.
    """
    return key != -1 and (key & 0xFF) in _QUIT_CHARS


def _is_prev_key(key: int) -> bool:
    """Check whether a ``cv2.waitKeyEx`` code signals navigation to the previous frame.

    :param key: The raw key code returned by ``cv2.waitKeyEx``.
    :return: Whether the key is a previous-frame signal.
    """
    return key != -1 and ((key & 0xFF) in _PREV_CHARS or key in _ARROW_PREV)


def _is_next_key(key: int) -> bool:
    """Check whether a ``cv2.waitKeyEx`` code signals navigation to the next frame.

    :param key: The raw key code returned by ``cv2.waitKeyEx``.
    :return: Whether the key is a next-frame signal.
    """
    return key != -1 and ((key & 0xFF) in _NEXT_CHARS or key in _ARROW_NEXT)
