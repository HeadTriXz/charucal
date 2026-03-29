# Installation

## Requirements

- Python 3.12+
- `opencv-contrib-python` (included automatically via pip)

## Install

```bash
pip install charucal
```

---

## Generating a ChArUco board

If you don't have a physical board yet, you can generate and print one with the CLI. All measurements are in metres.

```bash
charucal board \
  --width 10 --height 7 \
  --square-length 0.030 \
  --marker-length 0.022 \
  --dict DICT_4X4_50 \
  --paper-width 0.297 \
  --paper-height 0.210 \
  --output board.png
```

!!! warning "Print at 100% scale"
    Disable "fit to page" in your print dialog. After printing, measure a square with calipers and confirm it
    matches `--square-length`. Any size mismatch propagates directly into all distance measurements.

See the [board reference](../cli/board.md) for all available options.
