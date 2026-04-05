# `charucal preview`

The `preview` command loads a saved calibration file and opens a window showing the
real-time top-down view. It is a quick way to verify a calibration result without writing
any code.

---

## Usage

```
charucal preview CALIBRATION [OPTIONS]
```

`CALIBRATION` is the path to a `.json` file produced by [`charucal calibrate`](calibrate.md).

---

## Input options

| Option                         | Description                                                                                                        |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------|
| `--camera SOURCE [SOURCE ...]` | Camera index, video path, or image glob(s). Repeat for each camera (must match the order used during calibration). |
| `--resolution WIDTHxHEIGHT`    | Override resolution for live cameras                                                                               |
| `--fps INT`                    | Override framerate for live cameras                                                                                |

---

## Render options

| Option                       | Default   | Description                                                                                 |
|------------------------------|-----------|---------------------------------------------------------------------------------------------|
| `--output-size WIDTHxHEIGHT` | `720x720` | Maximum output canvas size in pixels                                                        |
| `--front METERS`             | `10.0`    | Forward render distance in meters                                                           |
| `--lateral METERS`           | `5.0`     | Lateral render distance in meters (each side)                                               |
| `--nearest`                  | off       | Use nearest-neighbor interpolation instead of bilinear. Faster but produces blockier edges. |

---

## Interactive controls (live mode)

| Key                 | Action                   |
|---------------------|--------------------------|
| ++q++ or ++escape++ | Close the preview window |

---

## Interactive controls (image mode)

When you provide image files instead of live cameras, the preview shows one frame set at a time.

| Key                      | Action                   |
|--------------------------|--------------------------|
| ++h++ or ++arrow-left++  | Previous frame           |
| ++l++ or ++arrow-right++ | Next frame               |
| ++q++ or ++escape++      | Close the preview window |

---

## Examples

**Live preview with three webcams:**

```bash
charucal preview calibration.json \
  --camera 0 --camera 1 --camera 2
```

**Custom render distance and output size:**

```bash
charucal preview calibration.json \
  --camera 0 --camera 1 \
  --front 15 --lateral 7.5 \
  --output-size 1280x720
```

**Preview from recorded images using nearest-neighbor interpolation:**

```bash
charucal preview calibration.json \
  --camera "frames/cam0/*.jpg" \
  --camera "frames/cam1/*.jpg" \
  --nearest
```

---

## Notes

The camera order passed to `--camera` must match the order used during calibration.
If the output looks misaligned, check that you are not mixing up camera indices.
See [Troubleshooting](../troubleshooting.md) for guidance.
