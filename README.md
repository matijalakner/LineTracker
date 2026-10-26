# Line Finder

A Python library and command-line tool that finds thin vertical lines in images and video, measures their spacing, and can drive Thorlabs lab hardware: a DC2200 LED driver (current ramps), a PM40 power meter (power logging), and both together for LIV measurements.

**Line detection.** Horizontal strips are sampled at regular rows. In each strip, narrow deviations from a moving-median background are detected, then linked from strip to strip into vertical *tracks*. Isolated specks and dust never form a track, so they are discarded.

**Video.** A video is sliced into frames, every frame is analysed like a single image, and the results are collected into per-frame and whole-video reports. Detection parameters can be measured automatically for each frame.

**Hardware.** Small modules ramp the LED current of a Thorlabs DC2200, log power from a PM40, or do both at once and save the data to CSV.

---

## Installation

Requires Python 3.8 or newer.

```bash
git clone https://github.com/your-username/strip-line-finder.git
cd strip-line-finder
pip install -e .              # core: numpy, pillow, opencv-python, pandas
pip install -e ".[plots]"     # adds matplotlib for the spacing-vs-time plots
pip install -e ".[hardware]"  # adds pyusb for the Thorlabs instruments
```

The hardware commands (`ramp`, `pm`, `liv`) additionally need the `measurement_control` package, which is not installed automatically. Image and video analysis work without `pyusb` and without `measurement_control`; the package imports fine either way, and a clear error is raised only when you start a measurement.

### Import name

`src/` is installed as the package **`line_finder`**, with the subpackages `strip_line_finder` (detection) and `Thorlabs` (instruments). All public functions are available directly:

```python
from line_finder import analyse_image, process_video, main_ramp, main_liv_measurement
```

---

## Quick start

### One image

```python
from line_finder import AnalysisConfig, analyse_image, annotate_image, export_pixel_histogram

config = AnalysisConfig(min_contrast=7.0)          # other values keep their defaults
width, height, lines, tracks = analyse_image("sample.jpg", config)

annotate_image("sample.jpg", lines, tracks, config.margin,
               "sample_marked.png", config.step, config.x_tolerance)
export_pixel_histogram("sample.jpg", lines, bin_size=10, out_path="sample_histogram.png")
# -> sample_histogram.png and sample_histogram.csv
```

For frames you already hold in memory (for example from OpenCV), use `analyse_image_array(img_np, **params)`.

### Automatic parameters

```python
import numpy as np
from PIL import Image
from line_finder import AnalysisConfig, analyse_image, auto_parameters

image = np.asarray(Image.open("sample.jpg").convert("RGB"))
params, measurements = auto_parameters(image)            # or overrides={"step": 80}
width, height, lines, tracks = analyse_image("sample.jpg", AnalysisConfig(**params))
```

### A video

```python
from line_finder import process_video

results = process_video("footage.mp4", output_dir="results", num_frames=12)
for frame in results:
    print(frame["frame_index"], frame["timestamp_sec"], len(frame["tracks"]))
```

### Statistics and plots

```python
from line_finder import analyze_cleaned_data_from_csv, show_analysis

report = analyze_cleaned_data_from_csv("sample_histogram.csv", cluster_gap=50)
print(report["total_lines"], report["pixel_indexes"], report["stats"])

show_analysis("results/frames_summary.csv", "MySample")   # needs matplotlib
```

`pixel_indexes` are the **centres** of each line's strongest histogram bin, so positions do not depend on the bin size. `show_analysis` saves a PNG and works without a display.

---

## Hardware

Before running anything, edit the instrument serial numbers in `src/Thorlabs/common.py`. USB product IDs and the resource strings are defined there once, so they cannot disagree:

```python
DC2200_RESOURCE = make_resource(DC2200_PRODUCT_ID, "M00937194")   # your serial here
PM_RESOURCE     = make_resource(PM_PRODUCT_ID, "P0012345")        # your serial here
```

All three modules detach the Linux kernel driver for the instrument while they run (via `ThorlabsUSBDriver`) and re-attach it afterwards. This needs `pyusb` and usually elevated USB permissions (a udev rule or `sudo`).

> **Check your LED head's rating first.** Currents are in **amperes**. The DC2200 limit is set to `i_max`, and the LED output is switched off at the end or on any error, including Ctrl+C.

### DC2200 current ramp

```python
from types import SimpleNamespace
from line_finder import main_ramp

main_ramp(SimpleNamespace(i_min=0.0, i_max=0.5, ramp_duration=60.0,
                          update_rate=20.0, cycles=1))
```

Each up or down ramp lasts `ramp_duration` seconds. Timing uses a monotonic clock, so it does not drift, and the turning point is set only once per cycle.

### PM40 power logging

```python
from types import SimpleNamespace
from line_finder import main_power_measurement

readings = main_power_measurement(SimpleNamespace(
    wavelength=633.0, averaging_count=10, sample_duration=5.0, sample_rate=10.0))
# readings: list of (time_s, power_W)
```

### Combined LIV measurement

Ramps the current up and down while reading power at every step.

```python
from types import SimpleNamespace
from line_finder import main_liv_measurement

rows = main_liv_measurement(SimpleNamespace(
    i_min=0.0, i_max=0.05, ramp_duration=10.0, update_rate=10.0, cycles=1,
    wavelength=633.0, averaging_count=10,
    settle_time=None,            # seconds to wait after each current step; None = automatic
    output_csv="liv_run1.csv"))  # None = do not write a file
```

The returned rows, and the CSV, have these columns:

| Column | Meaning |
|---|---|
| `time_s` | Seconds since the start, when the power reading finished |
| `cycle` | Cycle number, starting at 1 |
| `direction` | `up` or `down` |
| `current_A` | Set LED current in amperes |
| `power_W` | Measured optical power in watts |

The CSV is written even if the run is interrupted, so partial data is kept. `settle_time` must be shorter than `1 / update_rate`.

---

## Command line

```bash
strip-line-finder image sample.jpg --output marked.png
strip-line-finder split footage.mp4 --num-frames 20 --format png
strip-line-finder video footage.mp4 --num-frames 12 --output-dir results
strip-line-finder ramp --i-min 0.0 --i-max 0.5 --ramp-duration 60 --update-rate 20 --cycles 1
strip-line-finder pm --wavelength 633 --sample-duration 5 --sample-rate 10
strip-line-finder liv --i-max 0.05 --ramp-duration 10 --output-csv liv_run1.csv
```

| Command | What it does | Main options |
|---|---|---|
| `image` | Analyse one image, write `<name>_marked.png` | `--step --margin --min-contrast --output` |
| `split` | Slice a video into frame images only | `--output-dir --num-frames --format {png,jpg}` |
| `video` | Slice and analyse every frame, write reports | `--output-dir --num-frames --format --bin-size --no-auto --no-report --quiet --keep-all` plus overrides |
| `ramp` | Ramp the DC2200 LED current | `--i-min --i-max --ramp-duration --update-rate --cycles` |
| `pm` | Log optical power with the PM40 | `--wavelength --averaging-count --sample-duration --sample-rate` |
| `liv` | Ramp current and log power together, save CSV | `--i-min --i-max --ramp-duration --update-rate --cycles --wavelength --averaging-count --settle-time --output-csv` |

`video` also accepts fixed values that override the automatic ones: `--step --margin --min-contrast --min-brightness --min-width --max-width --bg-window --gap --x-tolerance --min-strips`.

Without `--num-frames`, `split` and `video` process **every** frame and save each one as an image. For long or high-resolution videos this needs a lot of disk space. Without `--output-csv`, `liv` writes `liv_<timestamp>.csv` in the current folder.

---

## Detection parameters

| Parameter | Default | Meaning |
|---|---|---|
| `step` | 100 | Distance in pixels between sampled rows |
| `margin` | 3 | Rows above and below each sample row that are averaged (strip height = 2·margin + 1) |
| `min_contrast` | 7.0 | Minimum deviation from the background (0-255 levels) |
| `min_width` / `max_width` | 1 / 14 | Accepted line thickness in pixels |
| `bg_window` | 41 | Width of the moving-median background filter |
| `gap` | 2 | Pixels that may be missing inside one line |
| `min_brightness` | 25.0 | Minimum background brightness (ignores dark regions) |
| `x_tolerance` | 20 | Maximum horizontal shift between strips for one track |
| `min_strips` | 3 | Strips a track must appear on, which filters out specks |
| `keep_all` | False | Keep detections that did not form a track |

### Automatic parameters

`auto_parameters` measures the frame and returns a full parameter set plus the measurements behind it:

1. **Geometry from resolution:** step, margin, widths and window sizes scale from the 1920×1080 defaults.
2. **`min_contrast` by stability search:** thresholds are tried on a ladder, and the value is placed inside the longest plateau where the number of tracks stays stable. A noise-based fallback is used if there is no plateau.
3. **Tracking from the result:** `x_tolerance` follows the measured line drift but stays below half the line spacing, and `min_strips` follows the number of strips.

Values you pass as `overrides` (or as keyword arguments to `process_video`) are fixed, and the remaining parameters adapt to them. All tuning constants are collected at the top of `auto_params.py`.

---

## Video output

```text
results/
├── frames/                          sliced frames: frame_00000.png ...
├── analysis/
│   └── frame_00000/                 marked image, histogram .png/.csv, frame_00000_report.txt
├── video_report.txt                 human-readable report for the whole video
├── video_report.json                the same numbers, machine-readable
├── frames_summary.csv               one row per frame (input for show_analysis)
└── tracks.csv                       one row per detected track
```

The video report lists typical line count, spacing statistics, the image conditions and parameters used, where lines sit across frames, and which frames to review (no lines found, unusual line count, irregular spacing).

---

## Project structure

```text
strip-line-finder/
├── pyproject.toml
├── README.md
├── examples/                         runnable scripts (see below)
└── src/                              installed as `line_finder`
    ├── __init__.py                   public exports
    ├── cli.py                        command-line interface
    ├── Thorlabs/
    │   ├── common.py                 USB IDs, resource strings, timing helpers
    │   ├── usb_driver.py             kernel-driver detach context manager (pyusb)
    │   ├── DC2200.py                 current ramp
    │   ├── PM40.py                   power logging
    │   └── PM40_DC2200.py            combined LIV measurement with CSV output
    └── strip_line_finder/
        ├── _core.py                  AnalysisConfig, detection and track linking
        ├── image.py                  image analysis, annotation, histogram export
        ├── video.py                  split_video, per-frame pipeline, process_video
        ├── auto_params.py            automatic parameter selection
        ├── report.py                 whole-video reports
        └── analysis.py               histogram statistics, robust fit and plots
```

## Examples

| Script | Shows |
|---|---|
| `01_single_image.py` | Detect, annotate and export a histogram for one image |
| `02_auto_parameters.py` | Automatic parameter selection |
| `03_split_video.py` | Slice a video into frames |
| `04_video_analysis.py` | Full video pipeline and reports |
| `05_statistical_analysis.py` | Spacing statistics from a histogram CSV |
| `06_plot_spacing_over_time.py` | Spacing vs time with a robust polynomial fit |
| `07_dc2200_ramp.py` | DC2200 current ramp (needs hardware) |

Each script takes its input path as an optional command-line argument. The `pm` and `liv` workflows are shown in the Hardware section above.

## Troubleshooting

- **No lines found:** lower `min_contrast`, or try automatic parameters. Check that `step` is smaller than the image height / `min_strips`.
- **Lines merge into one track:** reduce `x_tolerance`. It should stay below half the line spacing.
- **`ModuleNotFoundError: matplotlib`:** `pip install -e ".[plots]"`.
- **`pyusb is required` error:** `pip install -e ".[hardware]"`.
- **`measurement_control` error on `ramp`, `pm` or `liv`:** install that package and connect the instrument over USB.
- **`Thorlabs USB device ... not found`:** check the cable and that the serial number and product ID in `src/Thorlabs/common.py` match your instrument (`lsusb` shows the vendor and product IDs).
- **USB permission denied on Linux:** add a udev rule for vendor `1313`, or run with `sudo`.
- **`settle_time must be ... shorter than 1/update_rate`:** lower `settle_time` or the `update_rate`.

## License

MIT. Add a `LICENSE` file to the repository root.