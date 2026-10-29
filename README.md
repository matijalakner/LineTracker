# Line Finder

A Python library and command-line tool that finds thin vertical lines in images and video, tracks their spacing over time, and drives Thorlabs lab hardware: a DC2200 LED driver (current ramps, constant current), a PM40 power meter (power logging), and both together for LIV measurements.

The command line has two parts:

- **`control`** - the instruments: `ramp`, `pm`, `set`, `liv`
- **`analysis`** - the images: `image`, `video`, `analyse`

---

## Installation

Requires Python 3.8 or newer.

```bash
git clone https://github.com/your-username/strip-line-finder.git
cd strip-line-finder
pip install -e .              # core: numpy, pillow, opencv-python, matplotlib
pip install -e ".[hardware]"  # adds pyusb for the Thorlabs instruments
```

The `control` commands additionally need the `measurement_control` package, which is not installed automatically. Image and video analysis work without `pyusb` and without `measurement_control`; the package imports fine either way, and a clear error is raised only when you start a measurement.

`src/` is installed as the package **`line_finder`**, with the subpackages `strip_line_finder` (detection) and `ThorLabs` (instruments):

```python
from line_finder import analyse_image, process_video, analyse_spacing, main_set_current
```

---

## How the line detection works

1. The image is cut into 8 horizontal bands. Each band is reduced to one colour profile along x by taking the **median** over its rows, which ignores dust and local defects.
2. Per colour channel, a moving-median background is subtracted at 1-px resolution, and the largest deviation over R, G and B is the line strength of that column. Wide colour stripes stay in the background; only narrow features remain.
3. The band-averaged signal is smoothed and searched for local maxima above `max(k * sigma, rel * strong-response level)`, at least `min_dist` px apart.
4. A candidate is accepted only if it is visible in at least `min_fraction` of the bands. A bubble that covers only part of the image height is rejected, while faint lines survive.

Size-dependent parameters scale with the image width (tuned for a 6000 px wide frame), so downscaled frames work with the defaults.

---

## Command line

```bash
# analysis
strip-line-finder analysis image sample.jpg
strip-line-finder analysis video footage.mp4 -n 5
strip-line-finder analysis analyse footage

# control
strip-line-finder control set 0.25
strip-line-finder control ramp --i-min 0.0 --i-max 0.5 --ramp-duration 60 --update-rate 20 --cycles 1
strip-line-finder control pm --wavelength 633 --sample-duration 5 --sample-rate 10
strip-line-finder control liv --i-max 0.05 --ramp-duration 10 --output-csv liv_run1.csv
```

### `analysis`

All analysis commands take `--output-dir` (default `output`).

| Command | What it does |
|---|---|
| `image IMAGE` | Detects the lines and writes `output/image/<name>/<name>_marked.png` (same size, lines painted red) and `<name>_lines.csv` (`line, x_px, spacing_px`). `--plot` also saves the line-strength plot. |
| `video VIDEO -n N` | Takes a frame every `N` seconds (default 1), saves them to `output/video/frames/<name>/`, analyses each one like an image, and writes the marked frames and `lines.csv` to `output/video/<name>/`. |
| `analyse NAME` | Reads `output/video/<name>/lines.csv` and plots the mean distance between neighbouring lines against time, with the std of the spacings as the error. Writes `spacing.png` and `spacing.csv` into the same folder. Frames with fewer than 2 lines are skipped. |

`lines.csv` has one row per analysed frame:

| Column | Meaning |
|---|---|
| `time` | Time of the frame in the video, in seconds |
| `frame` | Frame index in the video |
| `lines` | Array of the x positions of the lines, e.g. `[121.0, 259.0, 395.0]` |

`image` and `video` accept the detection options below as `--k 4`, `--min-fraction 0.5`, and so on.

### `control`

Currents are in **amperes**. Check your LED head's rating first.

| Command | What it does |
|---|---|
| `set CURRENT` | Sets the DC2200 to a constant current (0 - 2 A) and **leaves the light on**. The user current limit is set to the same value. `set 0` switches the output off. |
| `ramp` | Ramps the DC2200 current up and down (`--i-min --i-max --ramp-duration --update-rate --cycles`). The output is switched off at the end or on any error, including Ctrl+C. |
| `pm` | Logs optical power with the PM40 (`--wavelength --averaging-count --sample-duration --sample-rate`). |
| `liv` | Ramps the current and logs power together, saved to CSV (`--output-csv`, `--settle-time`, plus the ramp and `pm` options). |

---

## Detection parameters

| Parameter | Default | Meaning |
|---|---|---|
| `n_blocks` | 8 | Horizontal bands that must agree |
| `k` | 3.0 | Noise floor in sigmas |
| `rel` | 0.25 | Threshold floor as a fraction of the strong responses |
| `min_fraction` | 0.6 | Fraction of bands a line must be visible in |
| `band_rel` | 0.5 | Per-band visibility, as a fraction of the threshold |
| `bg_window` | from width | Background filter width in px (about 100 at 6000 px) |
| `min_dist` | from width | Minimum distance between lines in px (about 100 at 6000 px) |
| `x_tol` | from width | Allowed x shift between bands for one line (about 10 at 6000 px) |
| `smooth` | 5 | Smoothing width in px that merges split peaks |
| `half_width` | 1 | Painted half-width of a line in px |

Python: `DetectionConfig(k=4.0, min_fraction=0.5)`. Command line: `--k 4 --min-fraction 0.5`.

---

## Hardware

Before running anything, edit the instrument serial numbers in `src/ThorLabs/common.py`. USB product IDs and the resource strings are defined there once, so they cannot disagree.

All hardware modules detach the Linux kernel driver for the instrument while they run (via `ThorlabsUSBDriver`) and re-attach it afterwards. This needs `pyusb` and usually elevated USB permissions (a udev rule or `sudo`).

```python
from types import SimpleNamespace
from line_finder import main_set_current, main_ramp, main_power_measurement, main_liv_measurement

main_set_current(SimpleNamespace(current=0.25))        # light stays on
main_ramp(SimpleNamespace(i_min=0.0, i_max=0.5, ramp_duration=60.0,
                          update_rate=20.0, cycles=1))
readings = main_power_measurement(SimpleNamespace(
    wavelength=633.0, averaging_count=10, sample_duration=5.0, sample_rate=10.0))
rows = main_liv_measurement(SimpleNamespace(
    i_min=0.0, i_max=0.05, ramp_duration=10.0, update_rate=10.0, cycles=1,
    wavelength=633.0, averaging_count=10, settle_time=None, output_csv="liv_run1.csv"))
```

The LIV rows and CSV have the columns `time_s, cycle, direction, current_A, power_W`. The CSV is written even if the run is interrupted. `settle_time` must be shorter than `1 / update_rate`.

---

## Project structure

```text
strip-line-finder/
├── pyproject.toml
├── README.md
├── examples/                         runnable scripts (see below)
└── src/                              installed as `line_finder`
    ├── __init__.py                   public exports
    ├── cli.py                        `control` and `analysis` commands
    ├── ThorLabs/
    │   ├── common.py                 USB IDs, resource strings, timing helpers
    │   ├── usb_driver.py             kernel-driver detach context manager (pyusb)
    │   ├── DC2200.py                 current ramp and constant current (set)
    │   ├── PM400.py                  power logging
    │   └── PM400_DC2200.py           combined LIV measurement with CSV output
    └── strip_line_finder/
        ├── detect.py                 DetectionConfig and the line detector
        ├── image.py                  analyse_image: detect, mark, save
        ├── video.py                  split_video, process_video
        └── analysis.py               spacing statistics and the spacing-vs-time plot
```

## Examples

| Script | Shows |
|---|---|
| `01_single_image.py` | Detect, mark and save one image |
| `02_split_video.py` | Take a frame every N seconds |
| `03_video_analysis.py` | Full video pipeline |
| `04_plot_spacing.py` | Mean spacing vs time with std error bars |
| `05_dc2200_ramp.py` | DC2200 current ramp (needs hardware) |
| `06_dc2200_set.py` | Set the DC2200 current (needs hardware) |

## Troubleshooting

- **Too many lines found:** raise `--k` or `--rel`.
- **Faint lines missed:** lower `--k` or `--rel`, or lower `--min-fraction` if a defect hides a line in some bands.
- **Two lines merged or one split:** adjust `--min-dist` (it should be well below the line spacing).
- **`No lines.csv in output/video/<name>`:** run `analysis video` first, and check that `--output-dir` matches.
- **`pyusb is required` error:** `pip install -e ".[hardware]"`.
- **`measurement_control` error on `control` commands:** install that package and connect the instrument over USB.
- **`Thorlabs USB device ... not found`:** check the cable and that the serial number and product ID in `src/ThorLabs/common.py` match your instrument (`lsusb`).
- **USB permission denied on Linux:** add a udev rule for vendor `1313`, or run with `sudo`.

## License

MIT. Add a `LICENSE` file to the repository root.
