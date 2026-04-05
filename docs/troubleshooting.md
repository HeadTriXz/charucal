# Troubleshooting

This page covers the most common problems and how to fix them.

---

## Calibration fails or raises an error

### `"No complete captures found"`

The board was not visible in **all** cameras simultaneously in any of the processed frames.

**What to check:**

- Is the board large enough? All cameras must detect it clearly. See [Capture Tips](getting-started/capture-tips.md).
- Is the board fully inside every camera's field of view? Partially cropped boards still fail the `is_complete` check.
- Run the CLI with your cameras and watch the grid display. Any camera showing all `░░` has a detection problem.

---

### `"No shared corners found across any capture"`

Two cameras do not share any detected corner IDs, so ChArUcal cannot compute a stitching
homography between them.

**What to check:**

- The board must be visible in the overlapping region of both cameras. If two cameras have no
  overlap, they cannot be stitched.
- Check that you are using the same ArUco dictionary (`--dict`) as the one used to generate
  the board.
- Improve lighting and make sure there are no reflections on the board surface.

---

### `"RANSAC failed to compute the stitch homography"`

OpenCV's RANSAC could not find a consistent set of corner correspondences.

**What to check:**

- You need at least 4 shared corners. Collect more captures, or use a larger board.
- Very steep viewing angles can cause RANSAC to fail. Keep the board roughly face-on to all cameras.
- Poor lighting or a warped board leads to noisy detections that RANSAC cannot handle.

---

### `"Only N shared corners across all captures; at least 4 needed"`

Too few corners were matched between cameras across all captures.

**What to check:**

- Collect more captures from different board positions.
- Make sure the board's overlap region covers more of the shared camera field of view.

---

## The output image looks wrong

### Cameras are misaligned

Objects appear at different positions depending on which camera they came from.

**Likely cause:** The calibration is inaccurate due to poor captures.

Recalibrate with a larger board, better lighting, and more overlap. Use `charucal preview` to
quickly check alignment before integrating into your code.

---

### The output is rotated or skewed

**Likely cause:** The ChArUco board was placed at a steep angle during the calibration capture.

ChArUcal corrects rotation analytically, but extreme angles can cause the correction to
overshoot. Recapture with the board held flat and roughly face-on to all cameras.

---

### The real-world scale is wrong

**Likely cause:** `square_length` or `marker_length` was entered incorrectly.

Measure the printed board with a ruler. Printer scaling and paper choice can change the
physical size by 5-10%. Confirm the units are **meters**, not centimeters or millimeters.

---

### There are visible seams or flickering edges between cameras

**Likely cause:** The homographies are slightly inaccurate near the camera boundary.

Recalibrate with more captures that have good corner coverage near the seam area. The
reference camera is always drawn on top, so the seam is always on the boundary between the
reference camera and another camera.

---

## Runtime / API errors

### `"Expected N images, got M"`

You passed the wrong number of frames to `CameraTransformer.transform()`. The number of
images must equal `calibration.num_cameras`, in the same order as during calibration.

---

### `UserWarning: Calibration result version '...' does not match`

The `calibration.json` file was created by a different version of ChArUcal. The file format
may have changed between versions.

Recalibrate with the current version to resolve this. If recalibration is not immediately
possible, the warning is non-fatal and the file may still work if the format has not changed.

---

### Conflicts between OpenCV packages

If you have both `opencv-python` and `opencv-contrib-python` installed, import errors or
silent failures can occur.

```bash
pip uninstall opencv-python opencv-contrib-python opencv-python-headless
pip install opencv-python
```

---

## Camera issues (CLI)

### `"Failed to open camera '0'"`

OpenCV could not open the device at index `0`.

**What to check:**

- Is the camera plugged in and recognized by the OS?
- On Linux, check `ls /dev/video*`. The camera might be at a different index if other video
  devices are present.
- Another application (like a video call) may be holding the camera exclusively.

---

### Frames come out dark or blurry

Pass `--resolution` and `--fps` to set explicit capture parameters, as some cameras default
to low-quality settings. Check the camera's exposure settings outside ChArUcal first.

---

## Still stuck?

Open an issue on [GitHub](https://github.com/HeadTriXz/charucal/issues) with:

1. Your ChArUcal version (`pip show charucal`)
2. Your Python and OpenCV versions
3. The full error traceback
4. A description of your camera setup and board
