# Capture Tips

- **Use a large board:** The ChArUco board needs to be large enough for all cameras to see it clearly. If it's too
  small, corner detection and homography estimation will fail or become unstable.
- **Maximize overlap:** The board has to be fully visible in every camera at the same time. Place it right in the middle
  where the camera views overlap. You can check `capture.is_complete` to confirm it was detected in all cameras before
  accepting a capture.
- **Ensure good lighting:** Reflections and bright spots on the board's surface will cause missed or inaccurate corner
  detections. Try to use matte materials or adjust your lighting to avoid glare.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `capture.is_complete` is always `False` | Board not fully visible in all cameras, or wrong `--dict` |
| Top-down view looks geometrically wrong | Board `square_length` or `marker_length` don't match the printed board |
| One camera's view is clearly misaligned | Too few shared corners between that camera and the reference |
| RANSAC error at calibration time | Fewer than 4 corners shared between two cameras |
