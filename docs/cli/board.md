# charucal board

Generate a printable ChArUco board image. All measurements are in **metres**.

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
    Disable "fit to page" or "scale to fit" in your print dialog. After printing, measure a single square with
    calipers. If it doesn't match `--square-length`, all distance measurements will be proportionally wrong.

---

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--width` | int | required | Number of squares along the board width |
| `--height` | int | required | Number of squares along the board height |
| `--square-length` | float (m) | required | Side length of one chessboard square, in metres |
| `--marker-length` | float (m) | required | Side length of the ArUco marker inside each square, in metres. Must be smaller than `--square-length`; typically around 70–80% of it. |
| `--dict` | str | required | ArUco dictionary name (e.g. `DICT_4X4_50`). Must match what you use during calibration. |
| `--paper-width` | float (m) | `0.297` | Width of the output image in metres. Defaults to A4 width. |
| `--paper-height` | float (m) | `0.210` | Height of the output image in metres. Defaults to A4 height. |
| `--dpi` | int | `300` | Resolution used to convert metres to pixels. 300 DPI is suitable for most printers. |
| `--output` | str | `board.png` | Path to write the output image to. |

---

## Choosing a dictionary

The dictionary controls how many distinct markers are available and how easy they are to tell apart.
A larger bit pattern is more distinctive but harder to detect at a distance or in poor lighting.

| Dictionary | Markers available | Min. bits that must differ |
|---|---|---|
| `DICT_4X4_50` | 50 | 4 |
| `DICT_4X4_100` | 100 | 4 |
| `DICT_5X5_50` | 50 | 5 |
| `DICT_5X5_100` | 100 | 5 |
| `DICT_6X6_50` | 50 | 6 |

For a 10×7 board you need at most 35 distinct markers, so `DICT_4X4_50` is sufficient.

---

## Example: A3 landscape

```bash
charucal board \
  --width 12 --height 9 \
  --square-length 0.040 \
  --marker-length 0.030 \
  --dict DICT_4X4_100 \
  --paper-width 0.420 \
  --paper-height 0.297 \
  --output board_a3.png
```
