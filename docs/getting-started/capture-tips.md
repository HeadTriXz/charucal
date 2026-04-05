# Capture Tips

Good calibration starts with good captures. This page covers the three most important
factors and how to avoid the most common mistakes.

---

## Use a large board

The ChArUco board must be clearly legible in every camera at the same time. If the board
is too small, corners appear only a few pixels wide and detection becomes unreliable.

**Guidelines:**

- Print the board as large as your space and printer allow.
- If a camera shows fewer than 10 detected corners in ChArUcal's grid view, the board is
  probably too small for that camera.
- For high-resolution cameras that are far from the board, go bigger.

!!! tip
    Laminating the board or mounting it on rigid foam board prevents warping, which would
    introduce subtle distortions into the calibration.

---

## Maximize overlap

All cameras must see the board simultaneously and completely. Partial visibility is fine
for individual corners, but the more corners that appear in multiple cameras at once, the
more accurate the inter-camera stitching will be.

**How to do it:**

- Place the board at the point where all camera views overlap, usually the center-front of
  the rig.
- Hold the board flat and level, so its real-world plane matches ChArUcal's planar homography assumption.
- Before saving a capture, check the grid view in the CLI. Every camera should show the
  majority of corners detected (shown in green). Red or yellow means poor overlap.
- Take 3-5 captures from slightly different positions and angles. This gives ChArUcal more
  point correspondences to work with and reduces sensitivity to any single noisy detection.

---

## Ensure good lighting

Shadows and reflections are the leading causes of missed or inaccurate corner detections.

**Checklist:**

- **Avoid direct sunlight** on the board's surface. Bright spots wash out the ArUco marker
  patterns and ruin corner detection.
- **Use matte paper or matte lamination** instead of glossy. Glossy boards create specular
  highlights that the detector mistakes for saturated markers.
- **Light the board evenly.** Side lighting that casts shadows across the squares will hide
  corners near the shadow edge.
- **Avoid backlight.** If a window or lamp is behind the board, the camera will expose for
  the background and leave the board dark.
- **Check exposure.** Open the camera preview before capturing. The board should be neither
  blown out (all white) nor muddy (all gray).

---

## What happens if calibration is poor?

| Symptom                      | Likely cause                                           |
|------------------------------|--------------------------------------------------------|
| Cameras don't align at edges | Too few shared corners between cameras                 |
| Real-world scale is wrong    | `square_length` or `marker_length` entered incorrectly |
| Output is rotated or skewed  | Board was tilted at a steep angle during capture       |
| Flickering seams at runtime  | RANSAC accepted an unstable homography — recapture     |

See [Troubleshooting](../troubleshooting.md) for more detailed diagnostics.
