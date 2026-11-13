# API Reference

ChArUcal's public API is organized into four modules. Here is a quick map of everything you are likely to need:

---

## Calibration workflow

| Class / Function                                                           | Module               | Description                                           |
|----------------------------------------------------------------------------|----------------------|-------------------------------------------------------|
| [`CalibrationPattern`](pattern.md)                                         | `charucal.pattern`   | Describes the physical ChArUco board                  |
| [`Calibrator`](calibrate.md#charucal.calibrate.Calibrator)                 | `charucal.calibrate` | Detects corners and computes homographies             |
| [`CalibrationCapture`](calibrate.md#charucal.calibrate.CalibrationCapture) | `charucal.calibrate` | Holds detected corners for one moment in time         |
| [`CalibrationResult`](calibrate.md#charucal.calibrate.CalibrationResult)   | `charucal.calibrate` | Holds the final homographies; can be saved and loaded |

## Runtime transformation

| Class                                                                    | Module               | Description                                 |
|--------------------------------------------------------------------------|----------------------|---------------------------------------------|
| [`CameraTransformer`](transform.md#charucal.transform.CameraTransformer) | `charucal.transform` | Transforms live frames into a top-down view |
| [`RenderDistance`](transform.md#charucal.transform.RenderDistance)       | `charucal.transform` | Specifies how much of the scene to render   |
| [`CameraPose`](transform.md#charucal.transform.CameraPose)               | `charucal.transform` | A camera's position and rotation in 3D      |

## Low-level

| Class                        | Module          | Description                               |
|------------------------------|-----------------|-------------------------------------------|
| [`CalibrationGrid`](grid.md) | `charucal.grid` | Internal grid of detected ChArUco corners |
