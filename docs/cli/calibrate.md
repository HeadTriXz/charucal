# charucal calibrate

Produce a calibration file from pre-captured images or directly from live cameras. All measurements are in **metres**.

---

## From pre-captured images

Images should be organised in one subfolder per camera under a common root. Files are paired by sorted filename,
so `cam0/001.png`, `cam1/001.png`, `cam2/001.png` are treated as one simultaneous capture.

```
frames/
├── cam0/
│   ├── 001.png
│   └── 002.png
├── cam1/
│   ├── 001.png
│   └── 002.png
└── cam2/
    ├── 001.png
    └── 002.png
```

```bash
charucal calibrate \
  --width 10 --height 7 \
  --square-length 0.030 \
  --marker-length 0.022 \
  --dict DICT_4X4_50 \
  --images ./frames \
  --output calibration.json
```

---

## From live cameras

Press `SPACE` to accept a capture, `Q` to finish and write the calibration file. The live mode shows all camera
feeds side by side so you can confirm the board is visible everywhere before capturing.

```bash
charucal calibrate \
  --width 10 --height 7 \
  --square-length 0.030 \
  --marker-length 0.022 \
  --dict DICT_4X4_50 \
  --cameras 0 1 2 \
  --output calibration.json
```

---

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--width` | int | required | Number of squares along the board width |
| `--height` | int | required | Number of squares along the board height |
| `--square-length` | float (m) | required | Side length of one chessboard square, in metres |
| `--marker-length` | float (m) | required | Side length of the ArUco marker inside each square, in metres |
| `--dict` | str | required | ArUco dictionary name — must match the board exactly (e.g. `DICT_4X4_50`) |
| `--images` | str | | Root directory containing one subfolder of images per camera |
| `--cameras` | int... | | Camera device indices for live capture (e.g. `0 1 2`) |
| `--output` | str | `calibration.json` | Path to write the calibration result to |
| `--ref-camera` | int | auto | Index of the reference camera. By default, the camera with the most shared corners across all others is chosen automatically. |

Exactly one of `--images` or `--cameras` must be provided.
