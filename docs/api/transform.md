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
    render_distance=RenderDistance(front=10.0, side=5.0),
    output_shape=(1000, 1000),
    interpolation=cv2.INTER_LINEAR,  # or cv2.INTER_NEAREST for maximum speed
)

topdown = transformer.transform(frames)  # list[np.ndarray] -> np.ndarray (H x W x 3 BGR)
```

---

## Controlling the render area

[`RenderDistance`](#charucal.transform.RenderDistance) defines the physical extent of the scene shown in the output image.

All three distances are measured from the origin, the point on the ground at the bottom center
of the reference camera's view.

- `front` — meters from the origin to the top edge of the output
- `side` — meters from the origin to the left and right edges of the output
- `rear` — meters from the origin to the bottom edge of the output (default `0`)

The pixels-per-meter scale is chosen automatically to fill `output_shape` while preserving
the aspect ratio implied by these distances. Parts of the output that no camera can see stay
black, which is often the case behind the origin.

---

## Measuring distances in the output

`CameraTransformer` provides helpers to convert between output pixel coordinates and meters.
All distances are measured from the origin.

```python
# Forward distance to a row of the output, negative behind the origin
dist_m = transformer.get_distance_forward(y=300)

# Straight-line distance to any output pixel
dist_m = transformer.get_distance_to_point(x=500, y=200)

# Map a point from a source camera into the output image
out_x, out_y = transformer.transform_point(x=640, y=360, camera_idx=0)

# Distance to a point in a source camera image
dist_m = transformer.get_distance_to_camera_point(x=640, y=360, camera_idx=0)
```

---

## World coordinates

World points are in meters from the origin, with `x` pointing to the right and `y` pointing
forward. A point behind the origin has a negative `y`. Converting a point back and forth gives
you exactly the point you started with.

```python
# Output pixel to world point
x_m, y_m = transformer.get_world_point(x=500, y=200)

# World point to output pixel
px, py = transformer.get_image_point(x=1.5, y=4.0)

# Point in a source camera image to world point
x_m, y_m = transformer.get_world_point_from_camera(x=640, y=360, camera_idx=0)

# World point to a point in a source camera image
cam_x, cam_y = transformer.get_camera_point(x=1.5, y=4.0, camera_idx=0)
```

`get_camera_point` raises a `RuntimeError` when the point is behind the camera. A point the
camera does not see can still end up outside the camera image, so check the bounds yourself.

!!! warning "Camera points must be on the ground"
    Points from a camera image are assumed to lie on the ground. A point above the ground, such as
    the top of an object, ends up further away than it really is. Use the point where the object
    touches the ground instead.

---

## Parallelism

By default (`n_jobs=-1`), all CPU threads are used to remap cameras in parallel. Set
`n_jobs=1` to disable threading. This can reduce latency when the number of cameras is small and the output resolution
is large, since the overhead of threading can outweigh the benefits in that case.

---

## Reference

::: charucal.transform.RenderDistance

::: charucal.transform.CameraTransformer
