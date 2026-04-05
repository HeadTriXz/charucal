# Transform

The `charucal.transform` module provides the classes responsible for transforming live camera frames into a top-down view.

---

## Overview

[`CameraTransformer`](#charucal.transform.CameraTransformer) is the main class you interact
with at runtime. It loads a saved calibration, precomputes remap tables once during
initialization, and then applies them on every call to `transform()`.

```python
import cv2
from charucal import CalibrationResult, CameraTransformer, RenderDistance

calibration = CalibrationResult.load("calibration.json")

transformer = CameraTransformer(
    calibration,
    render_distance=RenderDistance(front=10.0, lateral=5.0),
    output_shape=(1000, 1000),
    interpolation=cv2.INTER_LINEAR,  # or cv2.INTER_NEAREST for maximum speed
)

topdown = transformer.transform(frames)  # list[np.ndarray] -> np.ndarray (H x W x 3 BGR)
```

---

## Controlling the render area

[`RenderDistance`](#charucal.transform.RenderDistance) defines the physical extent of the scene shown in the output image.

- `front` — meters from the camera position to the top edge of the output
- `lateral` — meters from the center line to the left and right edges of the output

The pixels-per-meter scale is chosen automatically to fill `output_shape` while preserving
the aspect ratio implied by `front` and `lateral`.

---

## Measuring distances in the output

`CameraTransformer` provides helpers to convert between output pixel coordinates and meters:

```python
# Forward distance to any output pixel
dist_m = transformer.get_distance_forward(y=300)

# Euclidean distance to any output pixel
dist_m = transformer.get_distance_to_point(x=500, y=200)

# Map a point from a source camera into the output image
out_x, out_y = transformer.transform_point(x=640, y=360, camera_idx=0)

# Distance to a point in a source camera image
dist_m = transformer.get_distance_to_camera_point(x=640, y=360, camera_idx=0)
```

---

## Parallelism

By default (`n_jobs=-1`), all CPU threads are used to remap cameras in parallel. Set
`n_jobs=1` to disable threading. This can reduce latency when the number of cameras is small and the output resolution
is large, since the overhead of threading can outweigh the benefits in that case.

---

## Reference

::: charucal.transform.RenderDistance

::: charucal.transform.CameraTransformer
