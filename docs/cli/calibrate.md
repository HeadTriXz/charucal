# `charucal calibrate`

The `calibrate` command guides you through capturing board images and produces a
`calibration.json` file that can be loaded at runtime by [`CameraTransformer`](../api/transform.md).

---

## Usage

```
charucal calibrate [OPTIONS]
```

---

## ChArUco pattern options

These must match the **physical board you printed**.

| Option                        | Type    | Required       | Description                                                                                                |
|-------------------------------|---------|----------------|------------------------------------------------------------------------------------------------------------|
| `--width INT`                 | integer | :lucide-check: | Number of squares along the horizontal axis                                                                |
| `--height INT`                | integer | :lucide-check: | Number of squares along the vertical axis                                                                  |
| `--square-length METERS`      | float   | :lucide-check: | Side length of one chessboard square in meters                                                             |
| `--marker-length METERS`      | float   | :lucide-check: | Side length of the ArUco marker inside each square in meters                                               |
| `--dict NAME`                 | string  | :lucide-x:     | ArUco dictionary. Accepts `DICT_4X4_100`, `4X4_100`, or the raw integer constant (default: `DICT_4X4_100`) |
| `--max-marker-error FRACTION` | float   | :lucide-x:     | How far off a marker may be, as a fraction of the image diagonal (default: `0.005`)                        |
| `--min-inlier-ratio RATIO`    | float   | :lucide-x:     | Share of the detected markers that has to match the board (default: `0.8`)                                 |
| `--check-markers`             | flag    | :lucide-x:     | Also run OpenCV's own marker check, which often rejects boards seen at a steep angle                       |

The last three are explained in more detail under [Board validation](../api/pattern.md#board-validation).

---

## Input options

The `--camera` flag is repeated once per physical camera. Each invocation accepts either a
**live device** or a **set of image files**.

| Option                         | Description                                                                   |
|--------------------------------|-------------------------------------------------------------------------------|
| `--camera SOURCE [SOURCE ...]` | Camera index (integer), video path, or image glob(s). Repeat for each camera. |
| `--resolution WIDTHxHEIGHT`    | Override resolution for live cameras (e.g. `1920x1080`)                       |
| `--fps INT`                    | Override framerate for live cameras                                           |
| `--no-input`                   | Use every frame where the board is found, without asking. Image files only.   |

### Live cameras

Pass device indices (integers). On most Linux systems `/dev/video0` is `0`, `/dev/video1`
is `1`, and so on.

```bash
charucal calibrate \
  --width 10 --height 8 \
  --square-length 0.115 --marker-length 0.086 \
  --camera 0 \
  --camera 1 \
  --camera 2
```

### Image files

Pass glob patterns. Each `--camera` can match multiple files, which is useful when images
are named with a frame index.

```bash
charucal calibrate \
  --width 10 --height 8 \
  --square-length 0.115 --marker-length 0.086 \
  --camera "captures/cam0/*.jpg" \
  --camera "captures/cam1/*.jpg" \
  --camera "captures/cam2/*.jpg"
```

!!! warning "All cameras must have the same number of frames"
    When using image files, each `--camera` must match the same number of files. Each set of
    matched files is treated as one capture, so the first file from each camera forms the
    first capture, the second file from each camera forms the second capture, and so on.

---

## Output options

| Option               | Default            | Description                                    |
|----------------------|--------------------|------------------------------------------------|
| `--output PATH`      | `calibration.json` | Destination path for the calibration JSON file |
| `--ref-camera INDEX` | auto               | Override the reference camera index            |

---

## Interactive controls (live mode)

| Key                 | Action                                                                               |
|---------------------|--------------------------------------------------------------------------------------|
| ++space++           | Save the current frame set as a capture (only works when all cameras detect corners) |
| ++enter++           | Finish capturing and run calibration                                                 |
| ++q++ or ++escape++ | Abort without saving                                                                 |

The terminal displays a live grid diagram for every camera. Each cell represents one inner
corner of the ChArUco board:

- `██` — corner detected
- `░░` — corner not detected

The status below each grid changes from red to green when enough corners are visible.

---

## Image review mode

When you supply image files, ChArUcal automatically processes every frame set and then
presents an interactive review screen where you can browse the results and exclude bad frames
before calibration runs.

| Key                      | Action                                           |
|--------------------------|--------------------------------------------------|
| ++h++ or ++arrow-left++  | Previous capture                                 |
| ++l++ or ++arrow-right++ | Next capture                                     |
| ++space++                | Toggle include / exclude for the current capture |
| ++enter++                | Run calibration on included captures             |
| ++q++ or ++escape++      | Abort without saving                             |

### Running without a terminal

The review screen waits for you to press a key, so it can't be used in a script or on a CI
server. Pass `--no-input` to skip it. Every frame where the board is found in all cameras is
then used, and a warning is printed for each frame that was skipped. If no frame is left, the
command exits with an error and nothing is saved.

```bash
charucal calibrate \
  --width 10 --height 8 \
  --square-length 0.115 --marker-length 0.086 \
  --camera "frames/left_*.jpg" \
  --camera "frames/right_*.jpg" \
  --no-input
```

`--no-input` only works with image files.

---

## Examples

**Three webcams, large board, custom output path:**

```bash
charucal calibrate \
  --width 12 --height 9 \
  --square-length 0.08 --marker-length 0.06 \
  --camera 0 --camera 1 --camera 2 \
  --output results/my_rig.json
```

**Two cameras from pre-captured JPEG frames:**

```bash
charucal calibrate \
  --width 10 --height 8 \
  --square-length 0.115 --marker-length 0.086 \
  --camera "frames/left_*.jpg" \
  --camera "frames/right_*.jpg"
```

**Force 1080p and 30 FPS on live cameras:**

```bash
charucal calibrate \
  --width 10 --height 8 \
  --square-length 0.115 --marker-length 0.086 \
  --camera 0 --camera 1 \
  --resolution 1920x1080 --fps 30
```
