"""Provides an efficient transformer for remapping multi-camera images into a single top-down view."""

from __future__ import annotations

__all__ = ["CameraPose", "CameraTransformer", "RenderDistance"]

import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

    from charucal.calibrate import CalibrationResult


_EPS = 1e-10


@dataclass
class RenderDistance:
    """The physical extent of the scene captured in the top-down image."""

    #: The distance in meters from the origin to the far edge.
    front: float

    #: The distance in meters from the origin to each side edge.
    side: float

    #: The distance in meters from the origin to the near edge.
    rear: float = 0.0

    def __post_init__(self) -> None:
        """Initialize the render distance dataclass."""
        if self.front <= 0.0:
            raise ValueError(f"Expected front to be positive, got {self.front}.")

        if self.side <= 0.0:
            raise ValueError(f"Expected side to be positive, got {self.side}.")

        if self.rear < 0.0:
            raise ValueError(f"Expected rear to be zero or positive, got {self.rear}.")


@dataclass
class CameraPose:
    """The pose of a camera in the world frame."""

    #: The camera's ``(x, y, z)`` position in meters, where ``z`` is its height above the ground.
    position: npt.NDArray[np.float64]

    #: The ``(3, 3)`` rotation from the camera frame to the world frame.
    rotation: npt.NDArray[np.float64]


@dataclass
class CameraLayer:
    """The precomputed remap and mask data for a single camera's contribution to the output canvas."""

    #: The row extent of this camera's region of interest in the trimmed output canvas.
    row_slice: slice

    #: The column extent of this camera's region of interest in the trimmed output canvas.
    col_slice: slice

    #: The fixed-point x-coordinate map produced by ``cv2.convertMaps``.
    map1: npt.NDArray[np.int16]

    #: The fixed-point y-coordinate map produced by ``cv2.convertMaps``.
    map2: npt.NDArray[np.uint16]

    #: A mask selecting the output pixels owned by this camera within the ROI.
    mask: npt.NDArray[np.uint8]

    #: The pre-allocated destination buffer written into by ``cv2.remap`` each frame.
    dst: npt.NDArray[np.uint8]


def _apply_remap(image: npt.NDArray[np.uint8], layer: CameraLayer, interpolation: int) -> None:
    """Apply a precomputed remap to a single camera image, writing into the pre-allocated destination buffer.

    :param image: The source camera image to remap.
    :param layer: The precomputed camera layer for this camera.
    :param interpolation: The OpenCV interpolation flag to use.
    """
    cv2.remap(
        image,
        layer.map1,
        layer.map2,
        interpolation=interpolation,
        dst=layer.dst,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _compute_orientation_correction(
    topdown_matrix: npt.NDArray[np.float64],
    ref_width: int,
    ref_height: int,
) -> tuple[npt.NDArray[np.float64], tuple[float, float]]:
    """Rotate the top-down homography so the camera's horizontal axis aligns with the world x-axis.

    The physical ChArUco board can be placed at any orientation. This function computes the corrective
    rotation analytically from the homography matrix itself, so it is unconditionally valid regardless
    of board placement or camera field of view.

    :param topdown_matrix: The homography mapping reference-camera pixels to world coordinates.
    :param ref_width: The width of the reference camera image in pixels.
    :param ref_height: The height of the reference camera image in pixels.
    :return: The corrected homography and the camera's world-coordinate origin ``(x, y)``.
    """
    center_x = ref_width / 2.0
    bottom_row = float(ref_height)

    left_proj = topdown_matrix @ np.array([center_x - 1.0, bottom_row, 1.0])
    right_proj = topdown_matrix @ np.array([center_x + 1.0, bottom_row, 1.0])

    if abs(left_proj[2]) < _EPS or abs(right_proj[2]) < _EPS:
        raise RuntimeError(
            "The bottom row of the reference camera projects onto the horizon, "
            "so the direction of the horizontal axis cannot be determined."
        )

    camera_x_axis = right_proj[:2] / right_proj[2] - left_proj[:2] / left_proj[2]
    skew_angle = np.arctan2(float(camera_x_axis[1]), float(camera_x_axis[0]))

    cos_a = np.cos(-skew_angle)
    sin_a = np.sin(-skew_angle)
    rotation = np.array([
        [cos_a, -sin_a, 0.0],
        [sin_a, cos_a, 0.0],
        [0.0, 0.0, 1.0],
    ])

    oriented_matrix = rotation @ topdown_matrix

    camera_proj = oriented_matrix @ np.array([center_x, bottom_row, 1.0])
    if abs(camera_proj[2]) < _EPS:
        raise RuntimeError(
            "The reference-camera bottom-center projects onto the world horizon after orientation correction."
        )

    camera_world_origin = camera_proj[:2] / camera_proj[2]
    return oriented_matrix, (float(camera_world_origin[0]), float(camera_world_origin[1]))


def _build_world_to_pixel_homography(
    render_distance: RenderDistance,
    output_shape: tuple[int, int],
    camera_world_origin: tuple[float, float],
) -> tuple[npt.NDArray[np.float64], float, tuple[int, int]]:
    """Build the homography mapping world coordinates to output-pixel space.

    :param render_distance: The physical scene extents to render.
    :param output_shape: The ``(width, height)`` maximum output canvas in pixels.
    :param camera_world_origin: The camera's position in world coordinates ``(x, y)``.
    :return: The world-to-pixel homography, the pixels-per-meter scale, and the usable canvas size.
    """
    out_w, out_h = output_shape
    camera_x, camera_y = camera_world_origin

    depth = render_distance.front + render_distance.rear
    pixels_per_meter = min(out_w / (2.0 * render_distance.side), out_h / depth)

    canvas_w = int(round(2.0 * render_distance.side * pixels_per_meter))
    canvas_h = int(round(depth * pixels_per_meter))

    offset_x = -pixels_per_meter * (camera_x - render_distance.side)
    offset_y = -pixels_per_meter * (camera_y - render_distance.front)

    world_to_pixel = np.array([
        [pixels_per_meter, 0.0, offset_x],
        [0.0, pixels_per_meter, offset_y],
        [0.0, 0.0, 1.0],
    ])

    return world_to_pixel, pixels_per_meter, (canvas_w, canvas_h)


def _build_output_to_camera_homography(
    camera_to_output: npt.NDArray[np.float64],
    input_shape: tuple[int, int],
) -> npt.NDArray[np.float64]:
    """Build the homography mapping output pixels to camera pixels.

    :param camera_to_output: The homography mapping camera pixels to output pixels.
    :param input_shape: The ``(width, height)`` of the camera image in pixels.
    :return: The output-to-camera homography, scaled so points in front of the camera have a positive scale.
    """
    width, height = input_shape
    bottom_center = camera_to_output @ np.array([width / 2.0, float(height), 1.0])

    output_to_camera = np.linalg.inv(camera_to_output)
    if bottom_center[2] < 0.0:
        output_to_camera = -output_to_camera

    return output_to_camera


def _build_executor(n_jobs: int) -> ThreadPoolExecutor | None:
    """Build a thread pool for the given concurrency level, or ``None`` for single-threaded operation.

    :param n_jobs: The number of worker threads. ``-1`` uses all available CPUs, ``1`` disables parallelism.
    :return: A configured thread pool, or ``None`` if ``n_jobs`` is ``1``.
    """
    if n_jobs == 1:
        return None

    workers = os.cpu_count() or 4 if n_jobs == -1 else n_jobs
    return ThreadPoolExecutor(max_workers=workers)


def _compute_remap_coordinates(
    camera_to_output: npt.NDArray[np.float64],
    output_shape: tuple[int, int],
    source_shape: tuple[int, int],
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    """Compute per-output-pixel source coordinates for a single camera via backward mapping.

    :param camera_to_output: The homography mapping source-camera pixels to output pixels.
    :param output_shape: The ``(width, height)`` of the output canvas in pixels.
    :param source_shape: The ``(width, height)`` of the source camera image in pixels.
    :return: The ``(map_x, map_y)`` float32 coordinate arrays, with ``-1`` marking out-of-bounds pixels.
    """
    out_w, out_h = output_shape
    src_w, src_h = source_shape

    grid_x, grid_y = np.meshgrid(
        np.arange(out_w, dtype=np.float64),
        np.arange(out_h, dtype=np.float64),
    )

    output_pixels = np.stack([grid_x.ravel(), grid_y.ravel(), np.ones(out_w * out_h, dtype=np.float64)], axis=0)
    source_coords = np.linalg.inv(camera_to_output) @ output_pixels

    homogeneous_w = source_coords[2]
    safe_w = np.where(np.abs(homogeneous_w) > _EPS, homogeneous_w, 1.0)

    src_x = (source_coords[0] / safe_w).reshape(out_h, out_w)
    src_y = (source_coords[1] / safe_w).reshape(out_h, out_w)

    out_of_bounds = (
        (np.abs(homogeneous_w) < _EPS).reshape(out_h, out_w)
        | ~np.isfinite(src_x)
        | ~np.isfinite(src_y)
        | (src_x < 0.0)
        | (src_x >= float(src_w))
        | (src_y < 0.0)
        | (src_y >= float(src_h))
    )

    src_x[out_of_bounds] = -1.0
    src_y[out_of_bounds] = -1.0

    return src_x.astype(np.float32), src_y.astype(np.float32)


def _build_camera_layers(
    remap_coords: list[tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]],
    render_order: list[int],
) -> tuple[list[CameraLayer | None], int]:
    """Build per-camera warp layers with cropped ROI maps and ownership masks.

    :param remap_coords: The ``(map_x, map_y)`` coordinate arrays for each camera.
    :param render_order: The compositing draw order; later entries overwrite earlier ones.
    :return: The per-camera warp layers and the first valid output row index.
    """
    out_h, out_w = remap_coords[0][0].shape

    any_valid_per_row = np.zeros(out_h, dtype=bool)
    for map_x, _ in remap_coords:
        any_valid_per_row |= (map_x >= 0.0).any(axis=1)

    valid_rows = np.flatnonzero(any_valid_per_row)
    if valid_rows.size == 0:
        raise RuntimeError("No valid pixels found in any output row across all cameras.")

    first_valid_row = int(valid_rows[0])
    trimmed_h = out_h - first_valid_row

    cropped_data: list[dict | None] = []
    for map_x, map_y in remap_coords:
        trimmed_x = map_x[first_valid_row:]
        trimmed_y = map_y[first_valid_row:]

        valid_pixels = trimmed_x >= 0.0
        valid_row_mask = np.any(valid_pixels, axis=1)
        valid_col_mask = np.any(valid_pixels, axis=0)

        if not np.any(valid_row_mask) or not np.any(valid_col_mask):
            cropped_data.append(None)
            continue

        row_indices = np.where(valid_row_mask)[0]
        col_indices = np.where(valid_col_mask)[0]
        row_min, row_max = int(row_indices[0]), int(row_indices[-1]) + 1
        col_min, col_max = int(col_indices[0]), int(col_indices[-1]) + 1

        cropped_data.append({
            "row_slice": slice(row_min, row_max),
            "col_slice": slice(col_min, col_max),
            "map_x": trimmed_x[row_min:row_max, col_min:col_max],
            "map_y": trimmed_y[row_min:row_max, col_min:col_max],
            "valid": valid_pixels[row_min:row_max, col_min:col_max],
        })

    pixel_owner = np.full((trimmed_h, out_w), -1, dtype=np.int16)
    for camera_idx in render_order:
        data = cropped_data[camera_idx]
        if data is None:
            continue

        pixel_owner[data["row_slice"], data["col_slice"]][data["valid"]] = camera_idx

    warp_layers: list[CameraLayer | None] = []
    for camera_idx, data in enumerate(cropped_data):
        if data is None:
            warp_layers.append(None)
            continue

        ownership_mask = pixel_owner[data["row_slice"], data["col_slice"]] == camera_idx
        map1, map2 = cv2.convertMaps(data["map_x"], data["map_y"], cv2.CV_16SC2)
        roi_h, roi_w = data["map_x"].shape

        warp_layers.append(
            CameraLayer(
                row_slice=data["row_slice"],
                col_slice=data["col_slice"],
                map1=map1,
                map2=map2,
                mask=ownership_mask[:, :, np.newaxis].astype(np.uint8),
                dst=np.empty((roi_h, roi_w, 3), dtype=np.uint8),
            )
        )

    return warp_layers, first_valid_row


def _compute_camera_pose(
    world_to_camera: npt.NDArray[np.float64],
    camera_matrix: npt.NDArray[np.float64],
) -> CameraPose:
    """Find the pose of a camera from the homography mapping ground points to its pixels.

    :param world_to_camera: The homography mapping world points on the ground to camera pixels, scaled so points
        in front of the camera have a positive scale.
    :param camera_matrix: The camera's camera matrix.
    :return: The camera's pose in the world frame.
    """
    extrinsics = np.linalg.solve(camera_matrix, world_to_camera)
    scale = 2.0 / (np.linalg.norm(extrinsics[:, 0]) + np.linalg.norm(extrinsics[:, 1]))

    r1 = extrinsics[:, 0] * scale
    r2 = extrinsics[:, 1] * scale
    translation = extrinsics[:, 2] * scale

    u, _, vt = np.linalg.svd(np.column_stack([r1, r2, np.cross(r1, r2)]))
    world_to_camera_rotation = u @ vt

    rotation = world_to_camera_rotation.T
    position = -rotation @ translation

    return CameraPose(position=position, rotation=rotation)


class CameraTransformer:
    """Transforms multi-camera images into a single top-down view."""

    #: The calibration result used to build the remap maps.
    _calibration: CalibrationResult

    #: Per-camera homographies mapping input pixels to trimmed output pixels.
    _camera_to_output: list[npt.NDArray[np.float64]]

    #: The pre-allocated compositing canvas.
    _canvas: npt.NDArray[np.uint8]

    #: The thread pool used for parallel warping, or ``None`` for single-threaded operation.
    _executor: ThreadPoolExecutor | None

    #: The ``(width, height)`` of the input images for each camera.
    _input_shapes: list[tuple[int, int]]

    #: The ``cv2`` interpolation flag used by ``cv2.remap`` during each call to :meth:`transform`.
    _interpolation: int

    #: The ``(x, y)`` position of the world origin in the output image, in pixels.
    _origin: tuple[float, float]

    #: The ``(width, height)`` of the output image in pixels.
    _output_shape: tuple[int, int]

    #: Per-camera homographies mapping trimmed output pixels to input pixels.
    _output_to_camera: list[npt.NDArray[np.float64]]

    #: The number of output pixels per meter of world distance.
    _pixels_per_meter: float

    #: The per-camera warp layers used for compositing.
    _warp_layers: list[CameraLayer | None]

    def __init__(
        self,
        calibration: CalibrationResult,
        *,
        render_distance: RenderDistance,
        output_shape: tuple[int, int],
        input_shapes: Sequence[tuple[int, int]] | None = None,
        interpolation: int = cv2.INTER_LINEAR,
        n_jobs: int = -1,
    ) -> None:
        """Initialize the transformer and precompute all remap operations.

        :param calibration: The result of a prior multi-camera calibration.
        :param render_distance: The physical scene extents to render (in meters).
        :param output_shape: The ``(width, height)`` of the output canvas in pixels.
        :param input_shapes: The ``(width, height)`` of the input images. If ``None``, the source shapes from
            the calibration are used.
        :param interpolation: The OpenCV interpolation flag passed to ``cv2.remap``. Use ``cv2.INTER_LINEAR``
            for better quality at the cost of speed, or ``cv2.INTER_NEAREST`` for maximum throughput at
            reduced quality. Defaults to ``cv2.INTER_LINEAR``.
        :param n_jobs: The number of worker threads. ``-1`` uses all available CPUs, ``1`` disables parallelism.
        """
        self._calibration = calibration
        self._executor = _build_executor(n_jobs)
        self._interpolation = interpolation

        self._input_shapes = list(input_shapes) if input_shapes is not None else list(calibration.source_shapes)
        if len(self._input_shapes) != calibration.num_cameras:
            raise ValueError(f"Expected {calibration.num_cameras} input shapes, got {len(self._input_shapes)}.")

        ref_to_output, self._pixels_per_meter, canvas_shape = self._build_ref_homography(
            calibration, render_distance, output_shape
        )
        self._warp_layers, self._camera_to_output, self._output_shape, self._canvas = self._build_warp_layers(
            calibration, ref_to_output, canvas_shape
        )

        self._output_to_camera = [
            _build_output_to_camera_homography(homography, shape)
            for homography, shape in zip(self._camera_to_output, self._input_shapes, strict=True)
        ]

        ref_width, ref_height = self._input_shapes[calibration.ref_idx]
        self._origin = self._project_point(ref_width / 2.0, ref_height, calibration.ref_idx)

    @property
    def output_shape(self) -> tuple[int, int]:
        """The ``(width, height)`` of the output image in pixels."""
        return self._output_shape

    @property
    def pixels_per_meter(self) -> float:
        """The number of output pixels corresponding to one meter in the scene."""
        return self._pixels_per_meter

    def get_distance(self, pixels: float) -> float:
        """Convert a pixel distance in the output image to meters.

        :param pixels: The distance in output pixels.
        :return: The equivalent distance in meters.
        """
        return pixels / self._pixels_per_meter

    def get_pixels(self, meters: float) -> float:
        """Convert a physical distance in meters to output pixels.

        :param meters: The distance in meters.
        :return: The equivalent distance in output pixels.
        """
        return meters * self._pixels_per_meter

    def get_distance_forward(self, y: float) -> float:
        """Return the forward distance in meters from the origin to a horizontal scanline.

        :param y: The y-coordinate of the scanline in the output image.
        :return: The distance in meters.
        """
        _, origin_y = self._origin
        return self.get_distance(origin_y - y)

    def get_distance_to_point(self, x: float, y: float) -> float:
        """Return the Euclidean distance in meters from the origin to an output pixel.

        :param x: The x-coordinate of the output pixel.
        :param y: The y-coordinate of the output pixel.
        :return: The distance in meters.
        """
        world_x, world_y = self.get_world_point(x, y)
        return math.hypot(world_x, world_y)

    def get_distance_forward_to_camera_point(self, x: float, y: float, camera_idx: int) -> float:
        """Return the forward distance in meters from the origin to a point in a camera image.

        .. warning::
            The point is assumed to lie on the ground. A point above the ground, such as the top of an object,
            ends up further away than it really is. For a point with a known height, use :meth:`get_camera_pose`.

        :param x: The x-coordinate in the source camera image.
        :param y: The y-coordinate in the source camera image.
        :param camera_idx: The index of the source camera in the calibration.
        :return: The forward distance in meters.
        """
        _, world_y = self.get_world_point_from_camera(x, y, camera_idx)
        return world_y

    def get_distance_to_camera_point(self, x: float, y: float, camera_idx: int) -> float:
        """Return the Euclidean distance in meters from the origin to a point in a camera image.

        .. warning::
            The point is assumed to lie on the ground. A point above the ground, such as the top of an object,
            ends up further away than it really is. For a point with a known height, use :meth:`get_camera_pose`.

        :param x: The x-coordinate in the source camera image.
        :param y: The y-coordinate in the source camera image.
        :param camera_idx: The index of the source camera in the calibration.
        :return: The Euclidean distance in meters.
        """
        world_x, world_y = self.get_world_point_from_camera(x, y, camera_idx)
        return math.hypot(world_x, world_y)

    def get_image_point(self, x: float, y: float) -> tuple[float, float]:
        """Map a world point to a pixel in the output image.

        :param x: The distance in meters to the right of the origin.
        :param y: The distance in meters in front of the origin.
        :return: The ``(x, y)`` pixel coordinates in the output image.
        """
        origin_x, origin_y = self._origin
        image_x = origin_x + self.get_pixels(x)
        image_y = origin_y - self.get_pixels(y)

        return image_x, image_y

    def get_world_point(self, x: float, y: float) -> tuple[float, float]:
        """Map a pixel in the output image to a world point.

        :param x: The x-coordinate of the output pixel.
        :param y: The y-coordinate of the output pixel.
        :return: The ``(x, y)`` world coordinates in meters from the origin.
        """
        origin_x, origin_y = self._origin
        world_x = self.get_distance(x - origin_x)
        world_y = self.get_distance(origin_y - y)

        return world_x, world_y

    def get_world_point_from_camera(self, x: float, y: float, camera_idx: int) -> tuple[float, float]:
        """Map a point in a camera image to a world point.

        .. warning::
            The point is assumed to lie on the ground. A point above the ground, such as the top of an object,
            ends up further away than it really is. For a point with a known height, use :meth:`get_camera_pose`.

        :param x: The x-coordinate in the source camera image.
        :param y: The y-coordinate in the source camera image.
        :param camera_idx: The index of the source camera in the calibration.
        :return: The ``(x, y)`` world coordinates in meters from the origin.
        """
        image_x, image_y = self._project_point(x, y, camera_idx)
        return self.get_world_point(image_x, image_y)

    def get_camera_point(self, x: float, y: float, camera_idx: int) -> tuple[float, float]:
        """Map a world point to a pixel in a camera image.

        .. note::
            The result can lie outside the camera image when the camera does not see the point.

        :param x: The distance in meters to the right of the origin.
        :param y: The distance in meters in front of the origin.
        :param camera_idx: The index of the camera in the calibration.
        :return: The ``(x, y)`` pixel coordinates in the camera image.
        """
        image_x, image_y = self.get_image_point(x, y)
        homography = self._output_to_camera[camera_idx]

        output_point = np.array([image_x, image_y, 1.0], dtype=np.float64)
        camera_point = homography @ output_point
        if camera_point[2] < _EPS:
            raise RuntimeError(f"World point ({x}, {y}) is behind camera {camera_idx}.")

        camera_x = float(camera_point[0] / camera_point[2])
        camera_y = float(camera_point[1] / camera_point[2])

        return camera_x, camera_y

    def get_camera_matrix(self, camera_idx: int) -> npt.NDArray[np.float64]:
        """Return a camera's camera matrix for its input shape.

        :param camera_idx: The index of the camera in the calibration.
        :return: The ``(3, 3)`` camera matrix.
        :raises ValueError: If the calibration has no camera matrices.
        """
        camera_matrices = self._calibration.camera_matrices
        if camera_matrices is None:
            raise ValueError(
                "The calibration has no camera matrices. Recalibrate with charucal 0.3.0 or later to add them."
            )

        calibration_w, calibration_h = self._calibration.source_shapes[camera_idx]
        input_w, input_h = self._input_shapes[camera_idx]

        calibration_to_input = np.diag([input_w / calibration_w, input_h / calibration_h, 1.0])

        return calibration_to_input @ camera_matrices[camera_idx]

    def get_camera_pose(self, camera_idx: int) -> CameraPose:
        """Return a camera's pose in the world frame.

        The world frame has ``x`` to the right, ``y`` forward and ``z`` up, in meters from the origin. The camera
        frame is OpenCV's, with ``x`` to the right, ``y`` down and ``z`` along the optical axis.

        :param camera_idx: The index of the camera in the calibration.
        :return: The camera's pose.
        :raises ValueError: If the calibration has no camera matrices.
        """
        origin_x, origin_y = self._origin
        world_to_output = np.array([
            [self._pixels_per_meter, 0.0, origin_x],
            [0.0, -self._pixels_per_meter, origin_y],
            [0.0, 0.0, 1.0],
        ])

        world_to_camera = self._output_to_camera[camera_idx] @ world_to_output
        return _compute_camera_pose(world_to_camera, self.get_camera_matrix(camera_idx))

    def transform(self, images: list[npt.NDArray[np.uint8]]) -> npt.NDArray[np.uint8]:
        """Transform a list of camera images into a single top-down view.

        :param images: The camera images ordered to match the calibration.
        :return: The composited top-down image.
        """
        num_cameras = self._calibration.num_cameras
        if len(images) != num_cameras:
            raise ValueError(f"Expected {num_cameras} images, got {len(images)}.")

        self._canvas.fill(0)

        def _warp_camera(camera_idx: int) -> tuple[int, bool]:
            layer = self._warp_layers[camera_idx]
            if layer is None:
                return camera_idx, False

            _apply_remap(images[camera_idx], layer, self._interpolation)
            return camera_idx, True

        warp_results = (
            self._executor.map(_warp_camera, range(num_cameras))
            if self._executor is not None
            else map(_warp_camera, range(num_cameras))
        )

        for camera_idx, warped in warp_results:
            if not warped:
                continue

            layer = self._warp_layers[camera_idx]
            cv2.copyTo(layer.dst, layer.mask, self._canvas[layer.row_slice, layer.col_slice])

        return self._canvas

    def transform_point(self, x: float, y: float, camera_idx: int) -> tuple[int, int]:
        """Transform a point from a camera image into the top-down output image.

        :param x: The x-coordinate in the source camera image.
        :param y: The y-coordinate in the source camera image.
        :param camera_idx: The index of the source camera in the calibration.
        :return: The ``(x, y)`` pixel coordinates in the top-down output image.
        """
        out_x, out_y = self._project_point(x, y, camera_idx)
        return int(round(out_x)), int(round(out_y))

    def _project_point(self, x: float, y: float, camera_idx: int) -> tuple[float, float]:
        """Project a point from a camera image onto the output image.

        :param x: The x-coordinate in the source camera image.
        :param y: The y-coordinate in the source camera image.
        :param camera_idx: The index of the source camera in the calibration.
        :return: The ``(x, y)`` position in the output image, in pixels.
        """
        homography = self._camera_to_output[camera_idx]

        source_point = np.array([x, y, 1.0], dtype=np.float64)
        output_point = homography @ source_point
        if abs(output_point[2]) < _EPS:
            raise RuntimeError(f"Camera {camera_idx} point ({x}, {y}) projects onto the output horizon.")

        out_x = float(output_point[0] / output_point[2])
        out_y = float(output_point[1] / output_point[2])

        return out_x, out_y

    def _build_warp_layers(
        self,
        calibration: CalibrationResult,
        ref_to_output: npt.NDArray[np.float64],
        canvas_shape: tuple[int, int],
    ) -> tuple[
        list[CameraLayer | None],
        list[npt.NDArray[np.float64]],
        tuple[int, int],
        npt.NDArray[np.uint8],
    ]:
        """Build all per-camera warp layers and the compositing canvas.

        :param calibration: The calibration result describing all cameras.
        :param ref_to_output: The homography mapping the reference camera to the canvas.
        :param canvas_shape: The ``(width, height)`` of the full output canvas in pixels.
        :return: The per-camera warp layers, the trimmed per-camera homographies, the trimmed output shape,
            and the pre-allocated canvas buffer.
        """
        remap_coords, homographies = self._compute_all_remap_coords(
            calibration, ref_to_output, self._input_shapes, canvas_shape
        )

        render_order = [i for i in range(calibration.num_cameras) if i != calibration.ref_idx]
        render_order.append(calibration.ref_idx)

        warp_layers, first_valid_row = _build_camera_layers(remap_coords, render_order)

        canvas_w, canvas_h = canvas_shape
        output_shape = (canvas_w, canvas_h - first_valid_row)
        canvas = np.zeros((output_shape[1], output_shape[0], 3), dtype=np.uint8)

        trim_shift = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, -first_valid_row],
            [0.0, 0.0, 1.0],
        ])
        trimmed_homographies = [trim_shift @ h for h in homographies]

        return warp_layers, trimmed_homographies, output_shape, canvas

    @staticmethod
    def _build_ref_homography(
        calibration: CalibrationResult,
        render_distance: RenderDistance,
        output_shape: tuple[int, int],
    ) -> tuple[npt.NDArray[np.float64], float, tuple[int, int]]:
        """Compute the homography from the reference camera to the output canvas.

        Corrects any rotational skew in the top-down projection so the camera's horizontal axis
        aligns with the world x-axis, then scales and translates world coordinates into pixel space
        to fit the requested render distance inside the output canvas.

        :param calibration: The calibration result describing all cameras.
        :param render_distance: The physical scene extents to render.
        :param output_shape: The ``(width, height)`` maximum output canvas in pixels.
        :return: The reference-camera-to-output homography, the pixels-per-meter scale, and the
            usable canvas size ``(width, height)``.
        """
        ref_idx = calibration.ref_idx
        ref_w, ref_h = calibration.source_shapes[ref_idx]

        oriented_topdown, camera_world_origin = _compute_orientation_correction(
            calibration.topdown_matrix, ref_w, ref_h
        )
        world_to_pixel, pixels_per_meter, canvas_shape = _build_world_to_pixel_homography(
            render_distance, output_shape, camera_world_origin
        )

        ref_to_output = world_to_pixel @ oriented_topdown
        return ref_to_output, pixels_per_meter, canvas_shape

    @staticmethod
    def _compute_all_remap_coords(
        calibration: CalibrationResult,
        ref_to_output: npt.NDArray[np.float64],
        input_shapes: Sequence[tuple[int, int]],
        output_shape: tuple[int, int],
    ) -> tuple[
        list[tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]],
        list[npt.NDArray[np.float64]],
    ]:
        """Compute remap coordinate arrays and forward homographies for every camera.

        :param calibration: The calibration result describing all cameras.
        :param ref_to_output: The homography mapping the reference camera to the output canvas.
        :param input_shapes: The ``(width, height)`` of the input images for each camera.
        :param output_shape: The ``(width, height)`` of the output canvas in pixels.
        :return: The per-camera ``(map_x, map_y)`` coordinate arrays and forward homographies.
        """
        remap_coords: list[tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]] = []
        homographies: list[npt.NDArray[np.float64]] = []

        for stitch_matrix, calibration_shape, input_shape in zip(
            calibration.stitch_matrices, calibration.source_shapes, input_shapes
        ):
            input_to_calibration = np.diag([
                calibration_shape[0] / input_shape[0],
                calibration_shape[1] / input_shape[1],
                1.0,
            ])

            camera_to_output = ref_to_output @ stitch_matrix @ input_to_calibration
            remap_coords.append(_compute_remap_coordinates(camera_to_output, output_shape, input_shape))
            homographies.append(camera_to_output)

        return remap_coords, homographies
