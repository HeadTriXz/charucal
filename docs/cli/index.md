# CLI Reference

`charucal` ships with three command-line tools that cover the full workflow without writing any Python.

| Command | Description |
|---|---|
| [`charucal board`](board.md) | Generate a printable ChArUco board |
| [`charucal calibrate`](calibrate.md) | Produce a calibration file from images or live cameras |
| [`charucal preview`](preview.md) | Preview the top-down view in real time |

---

## Typical workflow

```bash
# 1. Generate and print a board
charucal board \
  --width 10 --height 7 \
  --square-length 0.030 \
  --marker-length 0.022 \
  --dict DICT_4X4_50 \
  --paper-width 0.297 --paper-height 0.210 \
  --output board.png

# 2. Calibrate from a folder of captured images
charucal calibrate \
  --width 10 --height 7 \
  --square-length 0.030 \
  --marker-length 0.022 \
  --dict DICT_4X4_50 \
  --images ./frames \
  --output calibration.json

# 3. Preview the result
charucal preview --cameras 0 1 2 --calibration calibration.json
```
