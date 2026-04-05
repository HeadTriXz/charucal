# Calibration

The `charucal.calibrate` module contains the classes that turn raw corner detections into
homography matrices ready for runtime use.

---

## Overview

```python
from charucal import Calibrator

calibrator = Calibrator(pattern)           # (1) create the calibrator
capture = calibrator.detect(frames)        # (2) detect corners in one frame set
result = calibrator.calibrate(*captures)   # (3) compute homographies
result.save("calibration.json")            # (4) persist to disk
```

Loading the result later:

```python
from charucal import CalibrationResult

calibration = CalibrationResult.load("calibration.json")
```

---

## Reference

::: charucal.calibrate.Calibrator

::: charucal.calibrate.CalibrationCapture

::: charucal.calibrate.CalibrationResult
