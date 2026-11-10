# CalibrationPattern

`CalibrationPattern` describes the physical ChArUco board you printed and uses it to detect
corners in images. Create one instance per board design and share it across your calibration
and detection code.

---

## Example

```python
import cv2
from charucal import CalibrationPattern

pattern = CalibrationPattern(
    width=10,
    height=8,
    square_length=0.115,   # meters — measure your printed board
    marker_length=0.086,   # meters
    aruco_dict=cv2.aruco.DICT_4X4_100,
)

# Detect corners in a single image
grid = pattern.detect(image)   # returns a CalibrationGrid
```

---

## Choosing the right ArUco dictionary

The dictionary must match the one used when you generated the board.

| Dictionary | Markers | Recommended for |
|------------|---------|-----------------|
| `DICT_4X4_50` | 50 | Small boards, few cameras |
| `DICT_4X4_100` | 100 | General use (default) |
| `DICT_5X5_100` | 100 | Larger boards, more robust detection |
| `DICT_6X6_250` | 250 | Very large boards |

Pass the constant directly (`cv2.aruco.DICT_4X4_100`) or its integer value. The CLI also
accepts the short string form (`4X4_100`).

---

## Board validation

Sometimes something that isn't part of the board gets detected as a marker, like a road sign
or a pattern on the ground. To filter these out, `detect` works out where each marker should be
based on the layout of the board, and ignores any marker that is too far from that spot. If too
many markers have to be ignored, the board is rejected.

```python
pattern = CalibrationPattern(
    width=10,
    height=8,
    square_length=0.115,
    marker_length=0.086,
    aruco_dict=cv2.aruco.DICT_4X4_100,
    max_marker_error=0.005,
    min_inlier_ratio=0.8,
    check_markers=False,
)
```

`max_marker_error` sets how far off a marker may be, as a fraction of the image diagonal. The
default of `0.005` comes down to about 11 pixels in a 1080p image. If markers near the edges of a wide-angle lens
are being ignored, try raising it.

`min_inlier_ratio` is the share of markers that has to fit. With the default of `0.8`, the board
is rejected when more than one in five markers is off.

`check_markers` also turns on OpenCV's own check. It is a lot stricter and often rejects boards
that are seen at a steep angle, which is why it is off by default.

---

## Reference

::: charucal.pattern.CalibrationPattern
