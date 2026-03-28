"""The ChArUco board for camera calibration."""

from __future__ import annotations

__all__ = ["CalibrationPattern"]

from typing import TYPE_CHECKING

import cv2

from charucal.grid import CalibrationGrid

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


class CalibrationPattern:
    """Represents a calibration pattern."""

    #: The calibration board.
    board: cv2.aruco.CharucoBoard

    #: The calibration pattern detector.
    detector: cv2.aruco.CharucoDetector

    #: The height of the calibration pattern.
    height: int

    #: The width of the calibration pattern.
    width: int

    def __init__(self, width: int, height: int, square_length: float, marker_length: float, aruco_dict: int) -> None:
        """Initialize the calibration pattern.

        :param width: The width of the calibration pattern.
        :param height: The height of the calibration pattern.
        :param square_length: The length of the squares on the calibration pattern.
        :param marker_length: The length of the markers on the calibration pattern.
        :param aruco_dict: The dictionary for the calibration pattern.
        """
        self.width = width
        self.height = height

        dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict)
        self.board = cv2.aruco.CharucoBoard(self.get_shape(), square_length, marker_length, dictionary)
        self.detector = cv2.aruco.CharucoDetector(
            self.board,
            cv2.aruco.CharucoParameters(),
            cv2.aruco.DetectorParameters(),
        )

    def detect(self, image: npt.NDArray[np.uint8]) -> CalibrationGrid:
        """Detect the ChArUco board in an image.

        :param image: The image to detect the ChArUco board in.
        :return: The corners and ids of the detected ChArUco board.
        """
        charuco_corners, charuco_ids, _, _ = self.detector.detectBoard(image)
        if charuco_corners is None or charuco_ids is None:
            raise ValueError("Failed to detect ChArUco board")

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
