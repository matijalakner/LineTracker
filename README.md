# Line Finder

Find thin vertical lines in images and video, measure how their spacing changes over time, and control the Thorlabs lab hardware used in the same experiment (DC2200 LED driver and PM400 power meter).

```text
measurement analysis  image | video | analyse     find lines, measure spacing
measurement control   set | ramp | pm | liv        drive the instruments
```

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Analysis](#analysis)
- [Control](#control)
- [Where the data goes](#where-the-data-goes)
- [How the detection works](#how-the-detection-works)
- [Detection parameters](#detection-parameters)
- [Python API](#python-api)
- [Project structure](#project-structure)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Installation

Requires Python 3.8 or newer.

```bash
git clone https://github.com/your-username/strip-line-finder.git
cd strip-line-finder
pip install -e .              # numpy, pillow, opencv-python, matplotlib
pip install -e ".[hardware]"  # adds pyusb, only needed for `control`
```

The `control` commands also need the separate `measurement_control` package (DC2200 driver). It is not installed automatically. Everything under `analysis` works without it, and the package imports fine either way; a clear error appears only when you start a measurement.

`src/` is installed as the package `line_finder`:

```python
from line_finder import analyse_image, process_video, analyse_spacing
```

---

## Quick start

```bash
# 1. one image
measurement analysis image sample.jpg

# 2. a video: one frame every 5 seconds, lines found in every frame
measurement analysis video footage.mp4 -n 5

# 3. mean line spacing (± std) against time
measurement analysis analyse footage

# light source: constant current of 0.25 A, left on
measurement control set 0.25

# light source: 0 -> 0.5 A in steps of 0.05 A, every step held for 2 s, and back
measurement control ramp --min 0 --max 0.5 --step 0.05 --step-time 2
```

---

## Analysis

Every analysis command takes `--output-dir` (default `output`).

### `analysis image IMAGE`

Detects the vertical lines in one image.

```text
output/image/<name>/
├── <name>_marked.png     the image, same size, lines painted red
├── <name>_lines.csv      line, x_px, spacing_px
└── <name>_signal.png     line-strength plot (only with --plot)
```

### `analysis video VIDEO -n N`

Takes a frame every `N` seconds (default 1, first frame at t = 0), then analyses each frame exactly like an image.

```text
output/video/
├── frames/<name>/        raw frames:  frame_00000.png, frame_00050.png, ...
└── <name>/
    ├── frame_00000_marked.png ...     every frame with its lines marked
    └── lines.csv                      time_stamp line, then time, frame, lines
```

`lines.csv` starts with a line `time_stamp,<UTC time when the analysis started>`, then the column header, then one row per analysed frame:

| Column | Meaning |
|---|---|
| `time` | Time of the frame in the video (s) |
| `frame` | Frame index in the video |
| `lines` | Array of the x positions of the detected lines (px) |

```csv
time_stamp,2026-10-30T12:34:56.789Z
time,frame,lines
0.0,0,"[62.0, 129.0, 198.0, 264.0, 333.0, 409.0, ...]"
5.0,50,"[63.0, 133.0, 203.0, 271.0, 341.0, 418.0, ...]"
```

Files without the time stamp line (older runs) are still read correctly.

### `analysis analyse NAME`

`NAME` is the video name (the folder under `output/video/`). It reads `lines.csv`, computes for every frame the mean distance between neighbouring lines and the standard deviation of those distances, and plots the mean against time with the std as the error bar.

```text
output/video/<name>/
├── spacing.png    mean spacing vs time, error bars = std
└── spacing.csv    time, frame, n_lines, mean_spacing_px, std_spacing_px
```

- Frames with fewer than 2 lines are skipped.
- The std is the sample standard deviation (n − 1) of the individual spacings; with only one spacing in a frame it is undefined and no error bar is drawn.
- The std describes how evenly the lines are spaced inside a frame, not the measurement noise. Unevenly spaced stripes give large error bars even if the detection is perfect.

---

## Control

Currents are in **amperes**. Check your LED head's rating before running anything.

| Command | What it does |
|---|---|
| `control set CURRENT` | Sets the DC2200 to a constant current (0 – 2 A) and **leaves the light on**. The user current limit is set to the same value. `set 0` switches the output off. |
| `control ramp` | Steps the current from `--min` to `--max` and back, in steps of `--step` A, holding every step for `--step-time` s. All four are required. Optional: `--cycles` (default 1). The output is switched off at the end or on any error, including Ctrl+C. |
| `control pm` | Logs optical power with the PM400. Options: `--wavelength` (default 450 nm), `--averaging-count`, `--sample-duration`, `--sample-rate`. |
| `control liv` | Ramps the current and logs power together. Options: `--i-min --i-max --ramp-duration --update-rate --cycles`, `--wavelength` (default 450 nm), `--averaging-count`, `--settle-time`. |

```bash
measurement control set 0.25
measurement control ramp --min 0.0 --max 0.5 --step 0.05 --step-time 2
measurement control pm --wavelength 450 --sample-duration 5 --sample-rate 10
measurement control liv --i-max 0.05 --ramp-duration 10 --output-csv liv_run1.csv
```

### How `ramp` steps

With `--min 0 --max 0.5 --step 0.1 --step-time 2` the current goes 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.1, 0 A and every value is held for 2 s (22 s in total). The maximum is not repeated, and the last value is held for the full step time before the output is switched off. If `max − min` is not a multiple of `step`, the last step up is shorter so that the ramp always ends exactly on `--max`. The steps are timed from a clock, so they do not drift. `--max` may not exceed 2 A, and the user current limit of the device is set to `--max` for the run.

### Setup

1. Edit the instrument serial numbers in `src/ThorLabs/common.py`. USB product IDs and resource strings are defined there once, so they cannot disagree.
2. The modules detach the Linux kernel driver while they run and re-attach it afterwards. This needs `pyusb` and usually elevated USB permissions (a udev rule for vendor `1313`, or `sudo`).

---

## Where the data goes

`--output-dir` (default `output`) is the root for everything.

| Command | Folder | File |
|---|---|---|
| `control ramp` | `output/ramp/` | `ramp_<UTC time>.csv` |
| `control pm` | `output/pm/` | `pm_<UTC time>.csv` |
| `control liv` | `output/liv/` | `liv_<UTC time>.csv` |
| `analysis image` | `output/image/<name>/` | marked image, `<name>_lines.csv` |
| `analysis video` | `output/video/` | `frames/<name>/`, and `<name>/` with the marked frames and `lines.csv` |

`--output-csv NAME` (ramp, pm, liv) changes the file name. A plain name is saved in the folder of its command (`--output-csv run1.csv` gives `output/ramp/run1.csv`); a name that contains a folder is used as given. The CSV is written even if a run is interrupted, so partial data is kept. Folders are created as needed.

**Time stamp line.** The first line of the ramp, pm and video CSVs is `time_stamp,<UTC time>`; the column header is on line 2. For `ramp` it is the UTC time just before the first step, for `pm` the start of the logging, for the video the start of the analysis.

```csv
time_stamp,2026-10-30T12:34:56.789Z
time_s,cycle,direction,current_A
0.0,1,up,0.0
2.0003,1,up,0.1
```

| File | Columns (after the time stamp line) |
|---|---|
| ramp | `time_s, cycle, direction, current_A` |
| pm | `time_s, power_W` |
| liv | `time_s, cycle, direction, current_A, power_W` (no time stamp line) |
| video `lines.csv` | `time, frame, lines` |

`time_s` is the time since the start of the run. `settle_time` of `liv` must be shorter than `1 / update_rate`.

---

## How the detection works

1. **Bands.** The image is cut into 8 horizontal bands. Each band is reduced to one colour profile along x by taking the median over its rows, which ignores dust and local defects.
2. **Line strength.** For each colour channel a moving-median background is subtracted at 1-px resolution, and the largest deviation over R, G and B is the line strength of that column. Wide colour stripes stay in the background; only narrow features remain.
3. **Candidates.** The band-averaged signal is smoothed and searched for local maxima above `max(k · sigma, rel · strong-response level)`, at least `min_dist` px apart (the strongest wins).
4. **Confirmation.** A candidate is accepted only if it is also visible in at least `min_fraction` of the bands. A defect that covers only part of the image height is rejected, while faint lines survive.

Size-dependent parameters scale with the image width (tuned on a 6000 px wide frame), so downscaled frames work with the defaults.

---

## Detection parameters

Set them in Python with `DetectionConfig(...)` or on the command line (`analysis image` and `analysis video`) as `--k 4`, `--min-fraction 0.5`, and so on.

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

---

## Python API

```python
from line_finder import DetectionConfig, analyse_image, process_video, analyse_spacing

config = DetectionConfig(k=4.0)

# one image -> dict with 'lines' (x positions), 'marked_path', 'csv_path', ...
res = analyse_image("sample.jpg", "output/image/sample", config, plot=True)

# video -> list of {'time', 'frame', 'lines'}; writes the folders described above
rows = process_video("footage.mp4", output_dir="output", interval=5.0, config=config)

# spacing vs time -> dict with the data and the paths of spacing.png / spacing.csv
out = analyse_spacing("footage", output_dir="output")
```

```python
from types import SimpleNamespace
from line_finder import main_ramp

rows = main_ramp(SimpleNamespace(i_min=0.0, i_max=0.5, step=0.05, step_time=2.0,
                                 output_csv="output/ramp/run1.csv"))
# rows: (time_s, cycle, direction, current_A); the CSV starts with the UTC time stamp line
```

Lower-level pieces: `detect_lines(img, config)` returns `(positions, signal, threshold)` for a NumPy image; `mark_image`, `plot_line_signal`, `split_video`, `read_lines_csv`, `read_time_stamp`, `spacing_stats` and `ramp_levels` are also exported. Hardware: `main_set_current`, `main_ramp`, `main_power_measurement` and `main_liv_measurement` (all take an object or dict with the settings; `output_csv` is optional).

---

## Project structure

```text
strip-line-finder/
├── pyproject.toml
├── README.md
├── examples/                         runnable scripts
└── src/                              installed as `line_finder`
    ├── __init__.py                   public exports
    ├── cli.py                        `control` and `analysis` commands
    ├── utils.py                      UTC time stamps, CSV writing, output paths
    ├── ThorLabs/
    │   ├── common.py                 USB IDs, resource strings, timing helpers
    │   ├── usb_driver.py             kernel-driver detach (pyusb)
    │   ├── DC2200.py                 stepped current ramp and constant current
    │   ├── PM400.py                  power logging
    │   └── PM400_DC2200.py           combined LIV measurement
    └── strip_line_finder/
        ├── detect.py                 DetectionConfig and the line detector
        ├── image.py                  analyse_image: detect, mark, save
        ├── video.py                  split_video, process_video
        └── analysis.py               spacing statistics and the spacing plot
```

## Examples

| Script | Shows |
|---|---|
| `01_single_image.py` | Detect, mark and save one image |
| `02_split_video.py` | Take a frame every N seconds |
| `03_video_analysis.py` | Full video pipeline |
| `04_plot_spacing.py` | Mean spacing vs time with std error bars |
| `05_dc2200_ramp.py` | DC2200 stepped current ramp (needs hardware) |
| `06_dc2200_set.py` | Set the DC2200 current (needs hardware) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Too many lines | Raise `--k` or `--rel` |
| Faint lines missed | Lower `--k` or `--rel`; lower `--min-fraction` if a defect hides a line in some bands |
| One line split in two, or two merged | Adjust `--min-dist`; it should be well below the line spacing |
| A spacing point jumps in the plot | A line was probably missed in that frame; check its `*_marked.png` |
| `No lines.csv in output/video/<name>` | Run `analysis video` first and check that `--output-dir` matches |
| `ramp` says `max must be <= 2.0 A` | The DC2200 limit is 2 A; lower `--max` |
| `ramp` / `control` error `the following arguments are required` | `--min --max --step --step-time` must all be given |
| `pyusb is required` | `pip install -e ".[hardware]"` |
| `measurement_control` error | Install that package and connect the instrument over USB |
| `Thorlabs USB device ... not found` | Check the cable and the serial number and product ID in `src/ThorLabs/common.py` (`lsusb`) |
| USB permission denied (Linux) | Add a udev rule for vendor `1313`, or run with `sudo` |

## License

MIT. Add a `LICENSE` file to the repository root.
