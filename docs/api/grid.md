# CalibrationGrid

`CalibrationGrid` is the internal data structure that holds detected ChArUco corners for
a single camera image. It is returned by [`CalibrationPattern.detect()`](pattern.md) and consumed by
[`Calibrator`](calibrate.md).

---

## Structure

A grid is a NumPy array of shape `(H-1, W-1, 2)`, where `H` and `W` are the number of
squares on the board. Each cell stores the `(x, y)` pixel coordinate of the corresponding
inner corner, or `NaN` if that corner was not detected.

---

## Reference

::: charucal.grid.CalibrationGrid
