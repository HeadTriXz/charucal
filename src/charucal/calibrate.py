"""Calibrate multi-camera systems using a ChArUco board."""

from __future__ import annotations

__all__ = ["CalibrationCapture", "CalibrationResult", "Calibrator"]

import json
import os
import pathlib
import warnings
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version as _version
from typing import TYPE_CHECKING, Any, Sequence

import cv2
import numpy as np

from charucal.grid import CalibrationGrid

if TYPE_CHECKING:
    import numpy.typing as npt

    from charucal.pattern import CalibrationPattern


@dataclass
class CalibrationCapture:
    """The result of detecting the calibration pattern in a multi-camera system."""

    #: A list of detected calibration grids for each camera.
    grids: list[CalibrationGrid]

    #: The source frame dimensions ``(width, height)`` for each camera.
    source_shapes: Sequence[tuple[int, int]]

    @property
    def is_complete(self) -> bool:
        """Whether every camera detected at least one corner."""
        return all(not grid.is_empty() for grid in self.grids)

    @property
    def num_cameras(self) -> int:
        """The number of cameras in the multi-camera system."""
        return len(self.grids)


@dataclass
class CalibrationResult:
    """The result of calibrating a multi-camera system."""

    #: A ``(N, 3, 3)`` array of homographies mapping each camera's pixel space to the reference camera's pixel space.
    stitch_matrices: npt.NDArray[np.float64]

    #: A ``(3, 3)`` homography mapping the reference camera's pixel space to the physical world coordinates in metres,
    #: with the origin at the ChArUco's board detected position.
    topdown_matrix: npt.NDArray[np.float64]

    #: The source frame dimensions ``(width, height)`` for each camera.
    source_shapes: Sequence[tuple[int, int]]

    #: The index of the reference camera.
    ref_idx: int

    @property
    def num_cameras(self) -> int:
        """The number of cameras in the multi-camera system."""
        return self.stitch_matrices.shape[0]

    def save(self, path: str | os.PathLike[str]) -> None:
        """Save the calibration result to a ``.json`` file.

        :param path: The path to save the calibration result to.
        """
        path = pathlib.Path(path)
        if path.suffix != ".json":
            path = path.with_suffix(".json")

        payload: dict[str, Any] = {
            "version": _version("charucal"),
            "created_at": datetime.now().isoformat(),
            "ref_idx": self.ref_idx,
            "source_shapes": [list(shape) for shape in self.source_shapes],
            "stitch_matrices": self.stitch_matrices.tolist(),
            "topdown_matrix": self.topdown_matrix.tolist(),
        }

        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> CalibrationResult:
        """Load the calibration result from a ``.json`` file.

        :param path: The path to load the calibration result from.
        :return: The calibration result.
        """
        path = pathlib.Path(path)
        if path.suffix != ".json":
            raise ValueError(f"Expected a .json file, got '{path.suffix}'")

        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("version")
        if version != _version("charucal"):
            warnings.warn(
                f"Calibration result version '{version}' does not match current package version '{_version('charucal')}'.",
                UserWarning,
                stacklevel=2,
            )

        return cls(
            stitch_matrices=np.array(data["stitch_matrices"], dtype=np.float64),
            topdown_matrix=np.array(data["topdown_matrix"], dtype=np.float64),
            source_shapes=[tuple(shape) for shape in data["source_shapes"]],
            ref_idx=data["ref_idx"],
        )


def select_reference_camera(grids: list[CalibrationGrid]) -> int:
    """Select the reference camera based on the inter-camera connectivity.

    :param grids: The detected calibration grids for each camera.
    :return: The index of the reference camera.
    """
    valid = np.stack([grid.visible_mask.ravel() for grid in grids])
    connections = (valid[:, None, :] & valid[None, :, :]).sum(axis=2)
    connections -= np.diag(valid.sum(axis=1))

    return int(np.argmax(connections.sum(axis=1)))


def find_stitch_homography(src_grids: list[CalibrationGrid], ref_grids: list[CalibrationGrid]) -> np.ndarray:
    """Find the homography mapping a source camera view to the reference camera.

    :param src_grids: The detected corners in the source camera, one per capture.
    :param ref_grids: The detected corners in the reference camera, one per capture.
    """
    if len(src_grids) != len(ref_grids):
        raise ValueError(
            f"Expected the same number of source and reference grids, got {len(src_grids)} and {len(ref_grids)}."
        )

    all_src_points: list[np.ndarray] = []
    all_ref_points: list[np.ndarray] = []

    for src, ref in zip(src_grids, ref_grids, strict=True):
        common_mask = src.visible_mask & ref.visible_mask
        if common_mask.sum() < 4:
            continue

        all_src_points.append(src.grid[common_mask])
        all_ref_points.append(ref.grid[common_mask])

    if not all_src_points:
        raise ValueError("No shared corners found across any capture.")

    src_points = np.concatenate(all_src_points)
    ref_points = np.concatenate(all_ref_points)

    if len(src_points) < 4:
        raise ValueError(f"Only {len(src_points)} shared corners across all captures; at least 4 needed.")

    homography, inlier_mask = cv2.findHomography(src_points, ref_points, cv2.RANSAC, 5.0)
    if homography is None:
        raise RuntimeError("RANSAC failed to compute the stitch homography.")
    if inlier_mask is not None and int(inlier_mask.sum()) < 4:
        raise RuntimeError("Too few RANSAC inliers for the stitch homography.")

    return homography.astype(np.float64)


def find_topdown_homography(detected_grids: list[CalibrationGrid], pattern: CalibrationPattern) -> np.ndarray:
    """Find the homography mapping the reference camera's pixel space to world metres.

    :param detected_grids: The detected corners in the reference camera, one per capture.
    :param pattern: The calibration pattern describing the physical board.
    """
    world_grid = pattern.to_grid()
    world_flat = world_grid.flatten()

    all_image_points: list[np.ndarray] = []
    all_world_points: list[np.ndarray] = []

    for detected in detected_grids:
        corners, ids = detected.visible_corners

        all_image_points.append(corners)
        all_world_points.append(world_flat[ids])

    image_points = np.concatenate(all_image_points)
    world_points = np.concatenate(all_world_points)

    if len(image_points) < 4:
        raise ValueError(f"Only {len(image_points)} corners across all captures; at least 4 needed.")

    homography, inlier_mask = cv2.findHomography(image_points, world_points, cv2.RANSAC, 5.0)
    if homography is None:
        raise RuntimeError("RANSAC failed to compute the top-down homography.")
    if inlier_mask is not None and int(inlier_mask.sum()) < 4:
        raise RuntimeError("Too few RANSAC inliers for the top-down homography.")

    return homography.astype(np.float64)


class Calibrator:
    """A class for calibrating multi-camera systems using ChArUco boards."""

    #: The ChArUco pattern to use for calibration.
    _pattern: CalibrationPattern

    #: The index of the reference camera. When ``None``, the reference is chosen automatically.
    _ref_idx: int | None

    def __init__(self, pattern: CalibrationPattern, *, ref_idx: int | None = None) -> None:
        """Initialize the calibrator.

        :param pattern: The ChArUco pattern to use for calibration.
        :param ref_idx: The index of the reference camera. When ``None``, the reference is chosen automatically.
        """
        self._pattern = pattern
        self._ref_idx = ref_idx

    def calibrate(self, *captures: CalibrationCapture) -> CalibrationResult:
        """Calibrate the multi-camera system.

        :param captures: The captures to use for calibration.
        :return: The result of the calibration.
        """
        if not captures:
            raise ValueError("At least one capture is required for calibration.")

        self._validate_captures(captures)

        ref_idx = self._ref_idx
        if ref_idx is None:
            ref_idx = select_reference_camera(captures[0].grids)

        n = captures[0].num_cameras
        stitch_matrices = np.empty((n, 3, 3), dtype=np.float64)
        for i in range(n):
            if i == ref_idx:
                stitch_matrices[i] = np.eye(3)
            else:
                stitch_matrices[i] = find_stitch_homography(
                    [capture.grids[i] for capture in captures],
                    [capture.grids[ref_idx] for capture in captures],
                )

        topdown_matrix = find_topdown_homography(
            [capture.grids[ref_idx] for capture in captures],
            self._pattern,
        )

        return CalibrationResult(
            stitch_matrices=stitch_matrices,
            topdown_matrix=topdown_matrix,
            source_shapes=captures[0].source_shapes,
            ref_idx=ref_idx,
        )

    def detect(self, images: Sequence[npt.NDArray[np.uint8]]) -> CalibrationCapture:
        """Detect the calibration pattern in the provided images without computing homographies.

        :param images: A sequence of images captured by the cameras. The order of the images should correspond
            to the order of the cameras.
        :return: The detected calibration grids and source shapes.
        """
        if len(images) < 2:
            raise ValueError("At least two images are required for detection.")

        grids = [self._pattern.detect(image) for image in images]
        source_shapes = [(image.shape[1], image.shape[0]) for image in images]

        return CalibrationCapture(grids=grids, source_shapes=source_shapes)

    @staticmethod
    def _validate_captures(captures: Sequence[CalibrationCapture]) -> None:
        """Validate the provided captures for calibration.

        :param captures: The captures to validate.
        :raises ValueError: If any capture is invalid.
        """
        if not captures:
            raise ValueError("At least one capture is required for calibration.")

        num_cameras = captures[0].num_cameras
        ref_shapes = captures[0].source_shapes

        for i, capture in enumerate(captures):
            if capture.num_cameras != num_cameras:
                raise ValueError(
                    f"Capture at index {i} has {capture.num_cameras} cameras, but the first capture has {num_cameras}. "
                    "All captures must have the same number of cameras."
                )

            if capture.source_shapes != ref_shapes:
                raise ValueError(
                    f"Capture at index {i} has source shapes {capture.source_shapes}, but the first capture has {ref_shapes}. "
                    "All captures must use the same camera resolutions."
                )
