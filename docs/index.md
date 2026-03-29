# charucal

`charucal` is a Python library designed to calibrate multi-camera systems and transform their outputs into a single
top-down view. The library utilizes ChArUco boards for precise corner detection and OpenCV for homography estimation.
To ensure the transformation remains efficient enough for real-time applications, `charucal` generates precomputed remap
tables that minimize processing overhead during runtime.

The project was originally developed for the Hanze team's participation in the
[Self Driving Challenge 2024](https://github.com/HeadTriXz/SDC-2024) to assist with autonomous driving. It is now
maintained as a standalone library for anyone who needs a real-time top-down view from multiple cameras.

---

## Install

```bash
pip install charucal
```

Requires Python 3.12+.

---

## Quick example

```python
import cv2
from charucal import CalibrationPattern, Calibrator, CalibrationResult, CameraTransformer, RenderDistance

# 1. Describe your printed board (measurements in metres)
pattern = CalibrationPattern(
    width=10,
    height=8,
    square_length=0.115,
    marker_length=0.086,
    aruco_dict=cv2.aruco.DICT_4X4_100,
)

# 2. Capture and calibrate
calibrator = Calibrator(pattern)

captures = []
for frame_set in your_capture_source:   # yields list[np.ndarray], one per camera
    capture = calibrator.detect(frame_set)
    if capture.is_complete:
        captures.append(capture)

result = calibrator.calibrate(*captures)
result.save("calibration.json")

# 3. Transform at runtime
calibration = CalibrationResult.load("calibration.json")
transformer = CameraTransformer(
    calibration,
    render_distance=RenderDistance(front=10.0, lateral=5.0),
    output_shape=(1000, 1000),
    interpolation=cv2.INTER_LINEAR,
)

topdown = transformer.transform(frames)   # list[np.ndarray] → np.ndarray
```

---

## Where to go next

| | |
|---|---|
| [Installation](getting-started/installation.md) | Requirements, pip install, board generation |
| [Quick Start](getting-started/quick-start.md) | Full walkthrough with all options explained |
| [How It Works](how-it-works.md) | Homographies, coordinate spaces, remap tables |
| [Capture Tips](getting-started/capture-tips.md) | Common mistakes and how to avoid them |
| [CLI Reference](cli/index.md) | `board`, `calibrate`, `preview` |
| [API Reference](api/calibration.md) | Full Python API |
