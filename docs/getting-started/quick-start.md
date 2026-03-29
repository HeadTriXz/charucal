# Quick Start

## 1. Define your board and calibrate

Start by defining the physical dimensions of your ChArUco board. These must match the printed board exactly —
all measurements are in **metres**.

```python
import cv2
from charucal import CalibrationPattern, Calibrator

pattern = CalibrationPattern(
    width=10,
    height=8,
    square_length=0.115,
    marker_length=0.086,
    aruco_dict=cv2.aruco.DICT_4X4_100,
)

calibrator = Calibrator(pattern)

captures = []
for frame_set in your_capture_source:   # yields list[np.ndarray], one per camera
    capture = calibrator.detect(frame_set)
    if capture.is_complete:
        captures.append(capture)

result = calibrator.calibrate(*captures)
result.save("calibration.json")
```

`capture.is_complete` confirms the board was visible in every camera. The result is saved to JSON so you don't
need to recalibrate between sessions.

!!! tip
    You can also calibrate directly from the command line. See the [calibrate reference](../cli/calibrate.md).

---

## 2. Load and transform

Load the calibration and create a transformer. All remap tables are precomputed here at construction time —
`transform()` itself has no allocations and no matrix math per frame.

```python
import cv2
from charucal import CalibrationResult, CameraTransformer, RenderDistance

calibration = CalibrationResult.load("calibration.json")
transformer = CameraTransformer(
    calibration,
    render_distance=RenderDistance(front=10.0, lateral=5.0),
    output_shape=(1000, 1000),
    interpolation=cv2.INTER_LINEAR,
)

topdown = transformer.transform(frames)   # list[np.ndarray] → np.ndarray (BGR)
```

`RenderDistance` defines what part of the scene to show: `front` is how many metres ahead of the camera to
include, `lateral` is how many metres to each side.

---

## 3. Distance helpers

`CameraTransformer` exposes helpers for converting between output pixels and real-world distances:

```python
# Scale conversions
metres = transformer.get_distance(pixels=100)
pixels = transformer.get_pixels(metres=2.5)

# Depth to a horizontal scanline in the output image
depth = transformer.get_distance_forward(y=200)

# Euclidean distance from the camera to an output pixel
dist = transformer.get_distance_to_point(x=400, y=300)

# Same, but measured from a coordinate in the original source camera
depth = transformer.get_distance_forward_to_camera_point(x=640, y=360, camera_idx=0)
dist  = transformer.get_distance_to_camera_point(x=640, y=360, camera_idx=0)
```

---

## 4. Running at a lower runtime resolution

If your cameras run at a lower resolution during inference than during calibration, pass `input_shapes` so the
transformer can scale the homographies correctly:

```python
transformer = CameraTransformer(
    calibration,
    render_distance=RenderDistance(front=10.0, lateral=5.0),
    output_shape=(1000, 1000),
    input_shapes=[(640, 360), (640, 360), (640, 360)],  # (width, height) per camera
)
```

---

## 5. Parallel remapping

By default `transform()` runs single-threaded. Pass `n_jobs=-1` to use all available CPU cores:

```python
transformer = CameraTransformer(
    calibration,
    render_distance=RenderDistance(front=10.0, lateral=5.0),
    output_shape=(1000, 1000),
    n_jobs=-1,
)
```
