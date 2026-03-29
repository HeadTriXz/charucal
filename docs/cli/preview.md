# charucal preview

Preview the top-down view in real time, from either a folder of images or live cameras.

---

## From images

Steps through each frame set. Press any key to advance, `Q` to quit.

```bash
charucal preview \
  --images ./frames \
  --calibration calibration.json
```

---

## From live cameras

Streams the top-down view continuously. Press `Q` to quit.

```bash
charucal preview \
  --cameras 0 1 2 \
  --calibration calibration.json
```

---

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--images` | str | | Root directory containing one subfolder of images per camera |
| `--cameras` | int... | | Camera device indices for live preview (e.g. `0 1 2`) |
| `--calibration` | str | required | Path to the calibration JSON file |
| `--front` | float (m) | `5.0` | How many metres ahead of the camera to include in the output |
| `--lateral` | float (m) | `3.0` | How many metres to each side to include in the output |
| `--size` | int int | `800 600` | Output canvas size in pixels (width height) |
| `--interpolation` | str | `nearest` | Interpolation method: `nearest` (faster) or `linear` (better quality) |

Exactly one of `--images` or `--cameras` must be provided.
