"""The detected corners of a ChArUco board as a grid."""

from __future__ import annotations

__all__ = ["CalibrationGrid"]

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


class CalibrationGrid:
    """Represents the detected corners of a ChArUco board as a grid."""

    #: The detected ChArUco corners. Each cell contains the (x, y) image coordinates of the corner,
    #: or NaN if not detected.
    grid: npt.NDArray[np.float32]

    def __init__(self, grid: npt.NDArray[np.float32]) -> None:
        """Initializes the grid.

        :param grid: The detected ChArUco corners as a (h, w, 2) array.
        """
        self.grid = grid

    @property
    def visible_mask(self) -> npt.NDArray[np.bool_]:
        """A boolean mask of the visible corners."""
        return ~np.isnan(self.grid).any(axis=-1)

    @property
    def visible_corners(self) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.intp]]:
        """The visible corners and their ids."""
        mask = self.visible_mask
        corners = self.grid[mask]
        ids = np.flatnonzero(mask)[:, np.newaxis]

        return corners, ids

    def find_homography(self, other: CalibrationGrid) -> npt.NDArray[np.float64]:
        """Finds the homography mapping this grid to another grid.

        :param other: The grid to find the homography to.
        :return: The homography mapping this grid to the other grid.
        """
        mask = self.visible_mask & other.visible_mask
        if mask.sum() < 4:
            raise ValueError("Not enough visible corners to find a homography")

        points_self = self.grid[mask]
        points_other = other.grid[mask]

        homography, inlier_mask = cv2.findHomography(points_self, points_other, method=cv2.RANSAC)
        if homography is None:
            raise ValueError("RANSAC failed to find a homography")
        if inlier_mask.sum() < 4:
            raise ValueError("Not enough inliers to find a homography")

        return homography.astype(np.float64)

    def flatten(self) -> npt.NDArray[np.float32]:
        """Flattens the grid into a (n, 2) array of corner positions.

        :return: The flattened grid.
        """
        return self.grid.reshape(-1, 2)

    def is_empty(self) -> bool:
        """Checks if the grid is empty (no corners detected).

        :return: Whether the grid is empty.
        """
        return np.isnan(self.grid).all()

    def merge(self, other: CalibrationGrid) -> CalibrationGrid:
        """Merges another grid into this one, filling in any missing corners.

        :param other: The grid to merge into this one.
        :return: This grid with the other grid merged in.
        """
        self.grid = np.where(np.isnan(self.grid), other.grid, self.grid)
        return self

    @classmethod
    def empty(cls, shape: tuple[int, int]) -> CalibrationGrid:
        """Creates an empty grid of the given shape.

        :param shape: The shape of the ChArUco board (w, h).
        :return: An empty grid.
        """
        w, h = shape[0] - 1, shape[1] - 1
        grid = np.full((h, w, 2), np.nan, dtype=np.float32)
        return cls(grid)

    @classmethod
    def from_corners(
        cls,
        shape: tuple[int, int],
        corners: npt.NDArray[np.float32],
        ids: npt.NDArray[np.intp],
    ) -> CalibrationGrid:
        """Creates a grid from detected ChArUco corners.

        :param shape: The shape of the ChArUco board (w, h).
        :param corners: The image coordinates of the detected corners.
        :param ids: The ids of the detected corners.
        :return: A grid of detected corner positions.
        """
        w, h = shape[0] - 1, shape[1] - 1
        grid = np.full((h, w, 2), np.nan, dtype=np.float32)

        rows = ids[:, 0] // w
        cols = ids[:, 0] % w

        grid[rows, cols] = corners[:, 0]
        return cls(grid)

    @classmethod
    def from_shape(cls, shape: tuple[int, int], length: float) -> CalibrationGrid:
        """Creates a grid of ideal corner positions for a ChArUco board.

        :param shape: The shape of the ChArUco board (w, h).
        :param length: The square side length.
        :return: A grid of ideal corner positions.
        """
        w, h = shape[0] - 1, shape[1] - 1

        y, x = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
        grid = np.stack((x, y), axis=-1).astype(np.float32) * length

        return cls(grid)

    def __repr__(self) -> str:
        """Returns a string representation of the grid."""
        return f"CalibrationGrid({self.grid.shape[1]}, {self.grid.shape[0]})"

    def __str__(self) -> str:
        """Returns a string representation of the grid."""
        chars = np.where(self.visible_mask, "██", "░░")

        return "\n".join("".join(row) for row in chars)
