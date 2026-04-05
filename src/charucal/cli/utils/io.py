"""Utilities for loading and reading frames from cameras."""

from __future__ import annotations

__all__ = ["load_frame_set", "read_frames", "resolve_image_globs"]

import glob as _glob
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt


def resolve_image_globs(cameras: list[list[str]]) -> list[list[Path]]:
    """Resolve camera glob patterns into sorted, validated lists of image paths.

    :param cameras: The per-camera lists of glob patterns or explicit paths.
    :return: The per-camera lists of resolved :class:`~pathlib.Path` objects.
    :raises ValueError: If any pattern matches no files, or camera frame counts differ.
    """
    resolved: list[list[Path]] = []
    for cam_idx, patterns in enumerate(cameras):
        paths: list[Path] = []
        for p in patterns:
            matched = sorted(Path(m) for m in _glob.glob(p))
            if not matched:
                raise ValueError(f"Could not find any files matching pattern '{p}' for camera {cam_idx}.")

            paths.extend(matched)

        resolved.append(paths)

    if len({len(p) for p in resolved}) > 1:
        raise ValueError("All cameras must have the same number of frames.")

    return resolved


def load_frame_set(camera_paths: list[list[Path]], frame_idx: int) -> list[npt.NDArray[np.uint8]] | None:
    """Load one frame per camera at a given index.

    :param camera_paths: The per-camera lists of image paths.
    :param frame_idx: The frame index to load.
    :return: The loaded images, or ``None`` if any image fails to load.
    """
    frames: list[npt.NDArray[np.uint8]] = []
    for paths in camera_paths:
        img = cv2.imread(str(paths[frame_idx]))
        if img is None:
            return None

        frames.append(img)

    return frames


def read_frames(cameras: list[cv2.VideoCapture]) -> list[npt.NDArray[np.uint8]] | None:
    """Read the current frame from every open camera capture.

    :param cameras: The list of open :class:`cv2.VideoCapture` objects.
    :return: The current frames, or ``None`` if any read fails.
    """
    frames: list[npt.NDArray[np.uint8]] = []
    for cap in cameras:
        ret, frame = cap.read()
        if not ret:
            return None

        frames.append(frame)

    return frames
