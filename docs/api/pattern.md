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

## Reference

::: charucal.pattern.CalibrationPattern
