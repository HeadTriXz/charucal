# Installation

## Requirements

ChArUcal requires Python 3.12 or later. The following packages are installed automatically:

- [NumPy](https://numpy.org/)
- [OpenCV](https://opencv.org/) (`opencv-python`)

## Install from PyPI

```bash
pip install charucal
```

Or with `uv`:

```bash
uv add charucal
```

!!! tip "Virtual environments"
    Always install into a virtual environment to avoid conflicts with other packages.

    ```bash
    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install charucal
    ```

## Install from source

To get the latest unreleased changes, install directly from GitHub:

```bash
pip install git+https://github.com/HeadTriXz/charucal.git
```

## Verify the installation

```bash
charucal --help
```

You should see the top-level help text listing the `calibrate` and `preview` sub-commands.

## What's next?

Head to the [Quick Start](quick-start.md) guide to run your first calibration.
