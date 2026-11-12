# Quick Start

This guide walks you through the full workflow, from capturing calibration images to
producing a live top-down view.

## What you need

- Two or more cameras (USB webcams, CSI cameras, or pre-recorded video files all work)
- A printed **ChArUco board** that all cameras can see at the same time
- ChArUcal [installed](installation.md)

!!! note "Don't have a ChArUco board?"
    You can generate one using any ArUco online tool or the
    [OpenCV tutorial](https://docs.opencv.org/4.x/da/d13/tutorial_aruco_calibration.html).
    Make sure the dictionary, width, height, and square length you use to generate the board
    match what you pass to `CalibrationPattern` in your code.

---

## Step 1. Describe your board

Create a [`CalibrationPattern`](../api/pattern.md) that matches the physical board you printed:

```python
import cv2
from charucal import CalibrationPattern

pattern = CalibrationPattern(
    width=10,             # number of squares horizontally
    height=8,             # number of squares vertically
    square_length=0.115,  # side of one square in meters
    marker_length=0.086,  # side of the ArUco marker inside the square
    aruco_dict=cv2.aruco.DICT_4X4_100,
)
```

!!! warning "Measure your board carefully"
    `square_length` and `marker_length` must match the **printed** dimensions exactly.
    Printers often scale slightly, so measure with a ruler after printing. Getting this
    wrong shifts the real-world scale of the output image.

---

## Step 2. Collect calibration captures

A *capture* is a single moment in time where the board is visible in **all** cameras at once.
You need at least one, but a handful from slightly different angles improves robustness.

### Option A. Use the CLI (recommended for first-timers)

The `calibrate` command opens live camera feeds and lets you press ++space++ to save a capture:

```bash
charucal calibrate \
  --width 10 --height 8 \
  --square-length 0.115 --marker-length 0.086 \
  --camera 0 --camera 1 --camera 2 \
  --output calibration.json
```

The terminal shows a live grid diagram for each camera so you can see exactly which corners
are detected. Press ++enter++ when you have enough captures.

See the full [CLI reference](../cli/calibrate.md) for all options.

### Option B. Use the Python API

```python
from charucal import Calibrator

calibrator = Calibrator(pattern)
captures = []

for frame_set in your_capture_source:
    # frame_set is a list of numpy arrays, one per camera, in the same order every time
    capture = calibrator.detect(frame_set)
    if capture.is_complete:   # True when every camera detected at least one corner
        captures.append(capture)
```

`your_capture_source` can be anything that yields lists of frames: a loop reading from
`cv2.VideoCapture` objects, a generator over image files, etc.

---

## Step 3. Calibrate and save

```python
result = calibrator.calibrate(*captures)
result.save("calibration.json")
```

`calibrate()` computes the homography matrices describing how each camera's image relates to
the others and to real-world coordinates. The result is saved as a JSON file so you only need
to do this once per camera setup.

---

## Step 4. Transform frames at runtime

Load the saved calibration and create a [`CameraTransformer`](../api/transform.md):

```python
from charucal import CalibrationResult, CameraTransformer, RenderDistance

calibration = CalibrationResult.load("calibration.json")

transformer = CameraTransformer(
    calibration,
    render_distance=RenderDistance(front=10.0, side=5.0),  # meters to show
    output_shape=(1000, 1000),
)
```

`RenderDistance` controls how much of the scene to include, measured from the
[origin](../how-it-works.md#step-4-transform-the-images), the point on the ground at the bottom
center of the reference camera's view.

- `front` — how many meters in front of the origin to show
- `side` — how many meters to each side of the origin to show
- `rear` — how many meters behind the origin to show (default `0`)

Now call `transform()` for each new set of frames:

```python
import cv2

cam0 = cv2.VideoCapture(0)
cam1 = cv2.VideoCapture(1)
cam2 = cv2.VideoCapture(2)

while True:
    frames = [cam.read()[1] for cam in [cam0, cam1, cam2]]
    topdown = transformer.transform(frames)

    cv2.imshow("Top-down view", topdown)
    if cv2.waitKey(1) == ord("q"):
        break
```

`topdown` is a standard NumPy array (H x W x 3, BGR) compatible with any OpenCV function.

---

## Preview with the CLI

To see the output without writing any code, use the `preview` command:

```bash
charucal preview calibration.json \
  --camera 0 --camera 1 --camera 2 \
  --front 10 --side 5
```

See the full [CLI reference](../cli/preview.md) for all options.

---

## Next steps

- Read [Capture Tips](capture-tips.md) to get the best calibration results
- Understand what ChArUcal does under the hood in [How It Works](../how-it-works.md)
- Explore the full [API Reference](../api/index.md)
