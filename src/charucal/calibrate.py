"""Calibrate multi-camera systems using a ChArUco board."""

from __future__ import annotations

__all__ = ["CalibrationCapture", "CalibrationResult", "Calibrator"]

import json
import os
import pathlib
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

import cv2
import numpy as np

import charucal
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

    #: A ``(3, 3)`` homography mapping the reference camera's pixel space to the physical world coordinates in meters,
    #: with the origin at the ChArUco's board detected position.
    topdown_matrix: npt.NDArray[np.float64]

    #: A ``(N, 3, 3)`` array of each camera's camera matrix for its ``source_shapes``, or ``None`` for calibrations
    #: made before charucal 0.3.0.
    camera_matrices: npt.NDArray[np.float64] | None

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
            "version": charucal.__version__,
            "created_at": datetime.now().isoformat(),
            "ref_idx": self.ref_idx,
            "source_shapes": [list(shape) for shape in self.source_shapes],
            "stitch_matrices": self.stitch_matrices.tolist(),
            "topdown_matrix": self.topdown_matrix.tolist(),
        }

        if self.camera_matrices is not None:
            payload["camera_matrices"] = self.camera_matrices.tolist()

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
        if version != charucal.__version__:
            warnings.warn(
                f"Calibration result version '{version}' does not match current package version '{charucal.__version__}'.",
                UserWarning,
                stacklevel=2,
            )

        camera_matrices = data.get("camera_matrices")

        return cls(
            stitch_matrices=np.array(data["stitch_matrices"], dtype=np.float64),
            topdown_matrix=np.array(data["topdown_matrix"], dtype=np.float64),
            camera_matrices=np.array(camera_matrices, dtype=np.float64) if camera_matrices is not None else None,
            source_shapes=[tuple(shape) for shape in data["source_shapes"]],
            ref_idx=data["ref_idx"],
        )


def _compute_conic_coefficients(g: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Expand ``g^T w k`` for the image of the absolute conic ``w = [[1, 0, a], [0, 1, b], [a, b, c]]``.

    :param g: The first homography column.
    :param k: The second homography column.
    :return: The coefficients of ``1``, ``a``, ``b`` and ``c``.
    """
    return np.array([g[0] * k[0] + g[1] * k[1], g[0] * k[2] + g[2] * k[0], g[1] * k[2] + g[2] * k[1], g[2] * k[2]])


def _compute_mean_reprojection_error(homography: np.ndarray, src: np.ndarray, dst: np.ndarray) -> float:
    """Compute the mean reprojection error for a homography on a set of point correspondences.

    :param homography: The homography to evaluate.
    :param src: The source points in pixel coordinates.
    :param dst: The destination points in world coordinates.
    :return: The mean reprojection error in pixels.
    """
    projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), homography).reshape(-1, 2)
    return float(np.mean(np.linalg.norm(projected - dst, axis=1)))


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
    :return: The homography mapping the source camera's pixel space to the reference camera's pixel space.
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
        raise ValueError(f"Expected at least 4 shared corners across all captures, got {len(src_points)}.")

    homography, inlier_mask = cv2.findHomography(src_points, ref_points, cv2.RANSAC, 5.0)
    if homography is None:
        raise RuntimeError("RANSAC failed to compute the stitch homography.")
    if inlier_mask is not None and int(inlier_mask.sum()) < 4:
        raise RuntimeError("Too few RANSAC inliers for the stitch homography.")

    return homography.astype(np.float64)


def find_topdown_homography(detected_grids: list[CalibrationGrid], pattern: CalibrationPattern) -> np.ndarray:
    """Find the homography mapping the reference camera's pixel space to world meters.

    :param detected_grids: The detected corners in the reference camera, one per capture.
    :param pattern: The calibration pattern describing the physical board.
    :return: The homography mapping the reference camera's pixel space to world meters.
    """
    world_grid = pattern.to_grid()
    world_flat = world_grid.flatten()

    best_homography: np.ndarray | None = None
    best_inliers: int = 0
    best_error: float = float("inf")

    for detected in detected_grids:
        corners, ids = detected.visible_corners
        if len(corners) < 4:
            continue

        world_points = world_flat[ids]
        homography, inlier_mask = cv2.findHomography(corners, world_points, cv2.RANSAC, 5.0)
        if homography is None:
            continue

        inlier_flags = (
            inlier_mask.ravel().astype(bool) if inlier_mask is not None else np.ones(len(corners), dtype=bool)
        )
        num_inliers = int(inlier_flags.sum())
        if num_inliers < 4:
            continue

        error = _compute_mean_reprojection_error(homography, corners[inlier_flags], world_points[inlier_flags])
        if num_inliers > best_inliers or (num_inliers == best_inliers and error < best_error):
            best_homography = homography
            best_inliers = num_inliers
            best_error = error

    if best_homography is None:
        raise ValueError("No valid homography could be estimated from any capture.")

    return best_homography.astype(np.float64)


def find_focal_length(
    detected_grids: list[CalibrationGrid],
    pattern: CalibrationPattern,
    source_shape: tuple[int, int],
) -> float:
    """Find a camera's focal length from its view of the board on the ground.

    :param detected_grids: The detected corners in the camera, one per capture.
    :param pattern: The calibration pattern describing the physical board.
    :param source_shape: The ``(width, height)`` of the camera image in pixels.
    :return: The focal length in pixels.
    """
    world_flat = pattern.to_grid().flatten()
    board_points = np.zeros((len(world_flat), 3), dtype=np.float32)
    board_points[:, :2] = world_flat

    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []

    for detected in detected_grids:
        corners, ids = detected.visible_corners
        if len(corners) < 4:
            continue

        object_points.append(board_points[ids.ravel()])
        image_points.append(corners)

    if not object_points:
        raise ValueError("Expected at least 4 corners in a capture to find the focal length.")

    flags = (
        cv2.CALIB_FIX_PRINCIPAL_POINT
        | cv2.CALIB_FIX_ASPECT_RATIO
        | cv2.CALIB_ZERO_TANGENT_DIST
        | cv2.CALIB_FIX_K1
        | cv2.CALIB_FIX_K2
        | cv2.CALIB_FIX_K3
    )

    try:
        _, camera_matrix, *_ = cv2.calibrateCamera(
            object_points, image_points, source_shape, np.eye(3), np.zeros(5), flags=flags
        )
    except cv2.error as e:
        raise ValueError(f"Failed to find the focal length: {e}") from e

    return float(camera_matrix[1, 1])


def find_camera_matrix(
    world_to_camera: npt.NDArray[np.float64],
    focal_length: float,
    source_shape: tuple[int, int],
) -> npt.NDArray[np.float64]:
    """Find the camera matrix that reproduces a camera's ground homography with the given focal length.

    :param world_to_camera: The homography mapping ground points in meters to camera pixels.
    :param focal_length: The focal length in pixels.
    :param source_shape: The ``(width, height)`` of the camera image in pixels.
    :return: The ``(3, 3)`` camera matrix.
    """
    width, height = source_shape
    center = np.array([width / 2.0, height / 2.0])

    pixel_to_normalized = np.array([
        [1.0 / focal_length, 0.0, -center[0] / focal_length],
        [0.0, 1.0 / focal_length, -center[1] / focal_length],
        [0.0, 0.0, 1.0],
    ])

    normalized = pixel_to_normalized @ world_to_camera
    normalized /= np.linalg.norm(normalized[:, :2])
    h1, h2 = normalized[:, 0], normalized[:, 1]

    rows = np.stack([
        _compute_conic_coefficients(h1, h2),
        _compute_conic_coefficients(h1, h1) - _compute_conic_coefficients(h2, h2),
    ])

    base = np.linalg.lstsq(rows[:, 1:], -rows[:, 0], rcond=None)[0]
    direction = np.linalg.svd(rows[:, 1:])[2][-1]

    quad_a = direction[:2] @ direction[:2]
    quad_b = 2.0 * base[:2] @ direction[:2] - direction[2]
    quad_c = base[:2] @ base[:2] + 1.0 - base[2]
    discriminant = max(quad_b * quad_b - 4.0 * quad_a * quad_c, 0.0)

    steps = [0.0]
    if quad_a > 1e-12:
        steps = [(-quad_b + sign * np.sqrt(discriminant)) / (2.0 * quad_a) for sign in (1.0, -1.0)]

    offsets = [-(base[:2] + step * direction[:2]) for step in steps]
    offset = min(offsets, key=lambda candidate: float(candidate @ candidate))

    principal_point = center + focal_length * offset
    return np.array([
        [focal_length, 0.0, principal_point[0]],
        [0.0, focal_length, principal_point[1]],
        [0.0, 0.0, 1.0],
    ])


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

        camera_matrices = np.stack([
            find_camera_matrix(
                np.linalg.inv(topdown_matrix @ stitch_matrices[i]),
                find_focal_length([capture.grids[i] for capture in captures], self._pattern, shape),
                shape,
            )
            for i, shape in enumerate(captures[0].source_shapes)
        ])

        return CalibrationResult(
            stitch_matrices=stitch_matrices,
            topdown_matrix=topdown_matrix,
            camera_matrices=camera_matrices,
            source_shapes=captures[0].source_shapes,
            ref_idx=ref_idx,
        )

    def detect(self, images: Sequence[npt.NDArray[np.uint8]]) -> CalibrationCapture:
        """Detect the calibration pattern in the provided images without computing homographies.

        :param images: A sequence of images captured by the cameras. The order of the images should correspond
            to the order of the cameras.
        :return: The detected calibration grids and source shapes.
        """
        if not images:
            raise ValueError("At least one image is required for calibration.")

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
