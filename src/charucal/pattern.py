"""The ChArUco board for camera calibration."""

from __future__ import annotations

__all__ = ["CalibrationPattern"]

import math
from typing import TYPE_CHECKING, Sequence

import cv2
import numpy as np

from charucal.grid import CalibrationGrid

if TYPE_CHECKING:
    import numpy.typing as npt


class CalibrationPattern:
    """Represents a calibration pattern."""

    #: The calibration board.
    board: cv2.aruco.CharucoBoard

    #: Whether OpenCV's own marker check is used as well.
    check_markers: bool

    #: The calibration pattern detector.
    detector: cv2.aruco.CharucoDetector

    #: The height of the calibration pattern.
    height: int

    #: How far off a marker may be, as a fraction of the image diagonal.
    max_marker_error: float

    #: The share of the detected markers that has to match the board.
    min_inlier_ratio: float

    #: The width of the calibration pattern.
    width: int

    #: The (x, y) corners of each marker on the board, by marker id.
    _marker_points: dict[int, npt.NDArray[np.float32]]

    def __init__(
        self,
        width: int,
        height: int,
        square_length: float,
        marker_length: float,
        aruco_dict: int,
        *,
        max_marker_error: float = 0.005,
        min_inlier_ratio: float = 0.8,
        check_markers: bool = False,
    ) -> None:
        """Initialize the calibration pattern.

        :param width: The width of the calibration pattern.
        :param height: The height of the calibration pattern.
        :param square_length: The length of the squares on the calibration pattern.
        :param marker_length: The length of the markers on the calibration pattern.
        :param aruco_dict: The dictionary for the calibration pattern.
        :param max_marker_error: How far off a marker may be, as a fraction of the image diagonal.
        :param min_inlier_ratio: The share of the detected markers that has to match the board.
        :param check_markers: Whether to also use OpenCV's own marker check.

        .. warning::
            Enabling ``check_markers`` can cause valid markers to be rejected, especially when the board is seen
            at a steep angle. It is recommended to leave it disabled unless you have a specific reason to enable it.

        """
        if max_marker_error <= 0.0:
            raise ValueError(f"Expected max_marker_error to be positive, got {max_marker_error}.")

        if not 0.0 < min_inlier_ratio <= 1.0:
            raise ValueError(f"Expected min_inlier_ratio to be between 0.0 and 1.0, got {min_inlier_ratio}.")

        self.width = width
        self.height = height
        self.max_marker_error = max_marker_error
        self.min_inlier_ratio = min_inlier_ratio
        self.check_markers = check_markers

        dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict)
        self.board = cv2.aruco.CharucoBoard(self.get_shape(), square_length, marker_length, dictionary)

        charuco_params = cv2.aruco.CharucoParameters()
        charuco_params.checkMarkers = check_markers
        self.detector = cv2.aruco.CharucoDetector(self.board, charuco_params, cv2.aruco.DetectorParameters())

        marker_ids = self.board.getIds()
        marker_points = self.board.getObjPoints()
        self._marker_points = {int(i): points[:, :2] for i, points in zip(marker_ids, marker_points)}

    def detect(self, image: npt.NDArray[np.uint8]) -> CalibrationGrid:
        """Detect the ChArUco board in an image, ignoring markers that don't match the board layout.

        :param image: The image to detect the ChArUco board in.
        :return: The corners and ids of the detected ChArUco board.
        """
        _, _, marker_corners, marker_ids = self.detector.detectBoard(image)
        if marker_ids is None or len(marker_ids) == 0:
            raise ValueError("Failed to detect ChArUco board.")

        diagonal = math.hypot(image.shape[0], image.shape[1])
        inlier_corners, inlier_ids = self._filter_markers(marker_corners, marker_ids, diagonal)

        charuco_corners, charuco_ids, _, _ = self.detector.detectBoard(
            image, markerCorners=inlier_corners, markerIds=inlier_ids
        )

        if charuco_corners is None or charuco_ids is None or len(charuco_ids) == 0:
            raise ValueError("Failed to detect ChArUco board.")

        return CalibrationGrid.from_corners(self.get_shape(), charuco_corners, charuco_ids)

    def get_shape(self) -> tuple[int, int]:
        """Get the shape of the ChArUco board.

        :return: The shape of the ChArUco board.
        """
        return self.width, self.height

    def to_grid(self) -> CalibrationGrid:
        """Get the grid of the ChArUco board.

        :return: The grid of the ChArUco board.
        """
        shape = self.get_shape()
        length = self.board.getSquareLength()

        return CalibrationGrid.from_shape(shape, length)

    def _filter_markers(
        self,
        marker_corners: Sequence[npt.NDArray[np.float32]],
        marker_ids: npt.NDArray[np.int32],
        diagonal: float,
    ) -> tuple[tuple[npt.NDArray[np.float32], ...], npt.NDArray[np.int32]]:
        """Keep the detected markers that match the board layout.

        :param marker_corners: The detected marker corners.
        :param marker_ids: The detected marker ids.
        :param diagonal: The image diagonal in pixels.
        :return: The inlier marker corners and ids, in OpenCV's shapes.
        """
        ids = np.asarray(marker_ids).reshape(-1)
        corners = [np.asarray(c, dtype=np.float32).reshape(4, 2) for c in marker_corners]

        on_board = [i for i, marker_id in enumerate(ids) if int(marker_id) in self._marker_points]
        if len(on_board) < 4:
            raise ValueError(f"Expected at least 4 board markers, got {len(on_board)}.")

        object_xy = np.concatenate([self._marker_points[int(ids[i])] for i in on_board])
        image_xy = np.concatenate([corners[i] for i in on_board])

        homography, _ = cv2.findHomography(object_xy, image_xy, cv2.LMEDS)
        if homography is None:
            raise ValueError("No homography could be found for the detected markers.")

        projected = cv2.perspectiveTransform(object_xy.reshape(-1, 1, 2), homography).reshape(-1, 4, 2)
        errors = np.sqrt(np.mean(np.sum((projected - image_xy.reshape(-1, 4, 2)) ** 2, axis=-1), axis=-1))
        max_error = self.max_marker_error * diagonal

        best: dict[int, tuple[float, int]] = {}
        for i, error in zip(on_board, errors.tolist()):
            if error > max_error:
                continue

            marker_id = int(ids[i])
            if marker_id not in best or error < best[marker_id][0]:
                best[marker_id] = (error, i)

        num_inliers = len(best)
        if num_inliers < self.min_inlier_ratio * len(ids):
            raise ValueError(f"Only {num_inliers} of {len(ids)} markers match the board layout.")

        kept = sorted(i for _, i in best.values())
        inlier_corners = tuple(corners[i].reshape(1, 4, 2) for i in kept)
        inlier_ids = ids[kept].reshape(-1, 1)

        return inlier_corners, inlier_ids
