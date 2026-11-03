# Line Finder

Find thin vertical lines in images and video, measure how their spacing changes over time, and control the lab hardware used in the same experiment (Thorlabs DC2200 LED driver, PM400 power meter, a Canon EOS R10 camera and a Teledyne FLIR Blackfly S microscope camera).

```text
measurement analysis  image | video | folder | report | analyse   find lines, measure spacing
measurement control   set | ramp | pm | liv        drive the instruments
measurement control   camera info | photo | timelapse | video     take photos and videos (Canon)
measurement control   flir list | info | photo | timelapse | video    the same with the FLIR Blackfly S
```

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Analysis](#analysis)
- [Control](#control)
- [Camera](#camera)
- [FLIR camera](#flir-camera)
- [Where the data goes](#where-the-data-goes)
- [How the detection works](#how-the-detection-works)
- [Detection parameters](#detection-parameters)
- [Python API](#python-api)
- [Project structure](#project-structure)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Installation

Requires Python 3.10 or newer.

Installation method only for use:
```bash
git clone https://github.com/matijalakner/strip-line-finder.git
cd strip-line-finder
sudo dnf install pipx
pipx install -e .              # numpy, pillow, opencv-python, matplotlib, pandas
pipx inject strip-line-finder pyusb  # adds pyusb, only needed for `control`
sudo dnf install libgphoto2 gphoto2  # camera library + `gphoto2 --auto-detect`
pipx inject strip-line-finder gphoto2  # only needed for `control camera` and `ramp --camera`
measurement --help
```

Installation method for further work:
```bash
#!/usr/bin/env bash
# Usage:  source setup.sh      (creates the environment, installs, and activates it)
#         PYTHON=python3.12 source setup.sh   (use a specific Python)
cd "$(dirname "${BASH_SOURCE[0]}")" || return 1
${PYTHON:-python3} -m venv measure \
  && source measure/bin/activate \
  && pip install --upgrade pip \
  && pip install -e ".[hardware,camera]" \
  && echo "Ready: the 'measurement' command is available in this terminal."
```
The `control` commands also need the separate `measurement_control` package (DC2200 driver). It is not installed automatically. Everything under `analysis` works without it, and the package imports fine either way; a clear error appears only when you start a measurement. The same holds for the camera: `python-gphoto2` (extra `camera`) is loaded only when the camera is opened.

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

# the same ramp with a photo in the middle of every step (Canon EOS R10)
measurement control ramp --min 0 --max 0.5 --step 0.05 --step-time 2 --camera mysample --shutter 1/5 --iso 100
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

### `analysis folder PATH`

Analyses every photo of a folder, for example photos taken during a ramp. The photos are ordered by their camera capture time (EXIF); photos without EXIF use the file time.

1. The first photo is used to tune the detection settings. The tuner first tries a 200 px strip around the image middle and shows the marked photo.
2. You answer `y` to keep the settings, or `n` to see the next suggestion (other strip heights are tried only then). Instead of Enter you can type settings, for example `strip_height=400 k=4`.
3. Every photo is analysed with the confirmed settings.

`--yes` skips the question, `--no-show` does not open the image viewer, `--window N` sets how many neighbouring photos are compared for the warnings.

```text
output/folder/<folder name>/
├── results.csv         time_stamp, photo, file, mean_spacing_px, n_lines, std_spacing_px, warning
├── parameters.json     the confirmed detection settings
├── tuning/             every tuning attempt: try<N>_<photo>_marked.png
└── <photo>_marked.png  every photo with its lines marked
```

`warning` is filled when a photo differs from its neighbours: fewer than 2 lines, a different number of lines, or an unusual std of the spacings.

### `analysis report NAME`

Lines the photo results of `analysis folder` up with a DC2200 ramp by time and plots average distance and pitch against current, intensity and time.

```bash
measurement control ramp --min 0.05 --max 1 --step 0.05 --step-time 100
measurement analysis folder photos/mysample
measurement analysis report mysample            # newest ramp in output/ramp/
measurement analysis report mysample --ramp ramp_20261030T171836Z.csv --objective 20x --sample 0.8wt
```

Each photo gets the ramp current that was set when it was taken; only photos taken during the ramp are kept. Photos with a warning are saved in the table but left out of the plots.

| Option | Meaning |
|---|---|
| `--ramp` | Ramp CSV (default: the newest `output/ramp/ramp_*.csv`) |
| `--results` | A results CSV instead of the one found from `NAME` |
| `--objective` | `5x`, `10x`, `20x`, `40x`: intensity per ampere (default 20x) |
| `--sample` | `0.2wt` ... `1.5wt`: angle for the pitch (default 0.8wt) |
| `--px-um` | Micrometers per pixel (default 0.1813) |
| `--camera-offset` | Seconds added to the photo times if the camera clock is off |

```text
output/report/<name>/
├── data.csv     time[s], current[A], mean_spacing_px, std_spacing_px, warning, n_lines
├── plots.png    average distance [µm] and pitch [µm] vs current, intensity [W/µm²] and time
└── timeline.png power (intensity) of the ramp and pitch of the photos on one time axis
```

`timeline.png` shifts both series to the same beginning: the ramp starts at t = 0 with its first row and the photos at t = 0 with the first photo. The shorter of the two series is also stretched in time to the length of the longer one, so both span the whole axis (the axis is then not real seconds for the stretched series; the x label says so). It uses all photos, also those outside the ramp (only photos with a warning are left out). The power is the LED intensity from the ramp current, `current * COEFF[objective]`. In Python, `plot_timeline(..., stretch=False)` only shifts, and `same_start=False` keeps the real clock instead.

The camera clock and the computer clock must agree: the EXIF time has no time zone and is taken as the computer's local time. If the plots look shifted against the ramp, use `--camera-offset`. The calibration constants are in `src/strip_line_finder/calibration.py`.

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
| `control ramp` | Steps the current from `--min` to `--max` and back, in steps of `--step` A, holding every step for `--step-time` s. All four are required. Optional: `--cycles` (default 1). The output is switched off at the end or on any error, including Ctrl+C. With `--camera NAME` the Canon camera (or with `--camera-type flir` the FLIR camera) takes photos during the ramp (see [Ramp with photos](#ramp-with-photos)). |
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

### Ramp with photos

`control ramp ... --camera NAME` runs the ramp and the Canon EOS R10 together. By default one photo is taken in the middle of every step, so every photo belongs to exactly one current:

```bash
measurement control ramp --min 0.05 --max 1 --step 0.05 --step-time 100 \
    --camera mysample --shutter 1/250 --iso 100 --wb Daylight --sync-clock
measurement analysis folder input/folder/mysample
measurement analysis report mysample
```

| Option | Meaning |
|---|---|
| `--camera NAME` | Photos go to `input/folder/NAME/NAME_XXXX.jpg` (numbering continues) |
| `--photo-delay S` | One photo per step, `S` seconds after the step starts (default: half the step time) |
| `--photo-interval N` | Instead: a photo every `N` seconds from the ramp start, independent of the steps |
| `--shutter --iso --wb --color-temp --picture-style --image-format --sync-clock --keep-on-card --input-dir` | As in [Camera](#camera) |
| `--camera-type flir` | Use the FLIR Blackfly S instead; then `--shutter --wb --gain --wb-red --wb-blue --gamma --black-level --pixel-format --save-format --serial --backend` as in [FLIR camera](#flir-camera) |

```bash
measurement control ramp --min 0.05 --max 1 --step 0.05 --step-time 100 \
    --camera mysample --camera-type flir --shutter 1/250 --gain 0 --wb off
```

- The camera is connected first; if it is not found, the LED is never switched on.
- The camera runs in its own thread, so a slow capture or download never delays a current step. If a capture takes longer than the time between photos, the next photo is late and a warning is printed.
- If the camera fails during the ramp, the ramp stops and the LED is switched off. Ctrl+C also stops both; photos and data taken so far are kept.
- Next to the ramp CSV a photo log `ramp_<UTC>_photos.csv` is written with the same time stamp line and the same t = 0 as the ramp:

```csv
time_stamp,2026-11-02T07:31:11.102Z
time_s,index,file,utc,step,cycle,direction,current_A
0.301,0,mysample_0000.jpg,2026-11-02T07:31:11.403Z,1,1,up,0.05
0.901,1,mysample_0001.jpg,2026-11-02T07:31:12.003Z,2,1,up,0.1
```

`current_A` is the current that was set when the photo was taken, independent of the camera clock.

### Setup

1. Edit the instrument serial numbers in `src/ThorLabs/common.py`. USB product IDs and resource strings are defined there once, so they cannot disagree.
2. The modules detach the Linux kernel driver while they run and re-attach it afterwards. This needs `pyusb` and usually elevated USB permissions (a udev rule for vendor `1313`, or `sudo`).

## Camera

`control camera` drives a Canon EOS R10 over USB through libgphoto2. Photos and videos are saved as

```text
input/folder/<name>/
├── <name>_0000.jpg
├── <name>_0001.jpg
├── ...
└── <name>_0042.mp4      videos use the same numbering
```

Numbering continues after the files already in the folder, so nothing is overwritten and a measurement can be continued with the same name. The folder can be analysed directly: `measurement analysis folder input/folder/<name>`.

| Command | What it does |
|---|---|
| `camera info` | Shows the current settings and every value the camera accepts for them. |
| `camera photo NAME` | Takes one photo. With `-i` the camera stays connected: Enter takes a photo, `q` + Enter quits. |
| `camera timelapse NAME -n N` | Takes a photo every `N` seconds (first one at t = 0, clock-based, no drift). Stops after `--count` photos or `--duration` seconds, otherwise on Ctrl+C. |
| `camera video NAME` | Records on the camera card and downloads the file. `--duration S`, or stops on Enter. Ctrl+C stops early and still downloads. `--delete-from-card` removes it from the card afterwards. |

Settings (all optional; not given = keep what is set on the camera). Values are checked against the camera's own list, so `1/250`, `0.004` and `1/250s` all work:

| Option | Example | Note |
|---|---|---|
| `--shutter` | `1/250`, `0.5`, `2` | mode dial on **M** (or Tv) |
| `--iso` | `100`, `400`, `Auto` | mode dial on M, Av, Tv or P |
| `--wb` | `Daylight`, `Tungsten`, `Auto` | white balance; a unique part of the name is enough |
| `--color-temp` | `5200` | Kelvin; switches the white balance to colour temperature |
| `--picture-style` | `Neutral`, `Faithful` | |
| `--image-format` | `"Large Fine JPEG"` | must include a JPEG; with RAW+JPEG only the JPEG is kept |
| `--sync-clock` | | sets the camera clock to the computer clock (so EXIF times match the ramp in `analysis report`) |

Photos are captured into the camera RAM and only downloaded, so the card does not fill up (`--keep-on-card` keeps a copy). Every run writes `output/camera/camera_<UTC time>.csv` with `time_s, index, file, utc` (computer time when each capture started), after a `time_stamp` line like the other logs.

```bash
measurement control camera info
measurement control camera photo sample-1 --shutter 1/250 --iso 200 --wb Daylight
measurement control camera timelapse sample-1 -n 5 --duration 1200 --sync-clock
measurement control camera video sample-1 --duration 60

```

Photos during a current ramp: use `control ramp ... --camera NAME`, see [Ramp with photos](#ramp-with-photos).

### Camera setup

1. `pip install -e ".[camera]"` (or `sudo dnf install python3-gphoto2`). Check the connection with `gphoto2 --auto-detect`.
2. Camera on, USB data cable, **Wi-Fi and Bluetooth off** (the R10 disables USB control while they are connected), auto power off disabled.
3. For video put the photo/movie switch on movie and insert a memory card.
4. On GNOME the file manager claims the camera. If you get "could not claim the USB device": `gio mount -s gphoto2; pkill -f gvfs-gphoto2-volume-monitor`.

---

## FLIR camera

`control flir` drives the Teledyne FLIR Blackfly S **BFS-U3-27S5C-C** on the microscope (Sony IMX429, 1936 × 1464, colour, global shutter, USB3 Vision) and works like `control camera`: the same files, numbering and logs, so `analysis folder` and `analysis report` work on its photos unchanged.

```text
input/folder/<name>/<name>_0000.jpg      (.png / .tif with --save-format)
input/folder/<name>/<name>_0001.mp4      video, recorded on the computer
output/camera/flir_<UTC time>.csv        time_s, index, file, utc
output/camera/flir_<UTC time>_frames.csv video only: the time of every frame
```

| Command | What it does |
|---|---|
| `flir list` | Lists the connected cameras with their serial numbers. |
| `flir info` | Shows the current settings with their allowed values or ranges. |
| `flir photo NAME` | Takes one photo. With `-i`: Enter takes a photo, `q` + Enter quits. |
| `flir timelapse NAME -n N` | A photo every `N` seconds; `--count` / `--duration`, otherwise until Ctrl+C. |
| `flir video NAME` | Records the stream to `.mp4` (`--fps`, default 10; `--duration`, otherwise until Enter). |

Settings (all optional; not given = keep what is set on the camera):

| Option | Example | Note |
|---|---|---|
| `--shutter` / `--exposure` | `1/250`, `0.004`, `4ms`, `250us`, `auto` | a plain number is seconds, as for the Canon; 15 µs – 30 s |
| `--gain` | `0`, `6.5`, `auto` | dB, 0 – 48 (the camera has no ISO) |
| `--wb` | `off`, `once`, `auto` | automatic white balance |
| `--wb-red`, `--wb-blue` | `1.4`, `2.0` | fixed white balance ratios (green = 1); switch the automatic off |
| `--gamma` | `1.0`, `off` | |
| `--black-level` | `1.5` | % |
| `--pixel-format` | `BGR8`, `BayerRG8`, `BayerRG16`, `Mono8` | default BGR8 (colour from the camera); 16-bit needs `--save-format png`/`tiff` |
| `--save-format` | `jpg`, `png`, `tiff` | default `jpg`; png/tiff are lossless |
| `--defaults` | | load the factory defaults first |
| `--serial`, `--backend` | `23306230`, `aravis` | which camera, and which library (default: Spinnaker if installed, else Aravis) |

For measurements fix the exposure, gain and white balance (`--shutter 1/250 --gain 0 --wb off`); with `auto` the camera changes them between photos and the brightness is no longer comparable.

```bash
measurement control flir list
measurement control flir info
measurement control flir photo sample-1 --shutter 1/250 --gain 0 --wb off
measurement control flir timelapse sample-1 -n 5 --duration 1200 --save-format png
measurement control flir video sample-1 --duration 60 --fps 20
```

How it differs from the Canon:

- Every photo is a fresh exposure started by a software trigger at the moment of the capture, so there is no delay for a download and photos can be taken many times per second.
- The camera has no clock and no card. The computer time of the trigger is written into the photo's EXIF (`DateTimeOriginal` with milliseconds), so `--sync-clock` and `--keep-on-card` are not needed.
- Video is recorded on the computer. If the computer cannot keep up, frames are dropped and a warning is printed; the real time of every frame is in `_frames.csv`.

### FLIR camera setup

The camera needs one of two libraries (neither is on PyPI):

**Spinnaker + PySpin** (Teledyne's SDK; Windows and Ubuntu officially):
1. Download the Spinnaker SDK and the PySpin wheel matching your Python from teledynevisionsolutions.com (Spinnaker downloads). Install the SDK (it adds the udev rule and the `flirimaging` group).
2. `pip install spinnaker_python-<version>-cp3XX-...whl` into the same environment.
3. Check with SpinView or `measurement control flir list`.

**Aravis** (open source; easiest on Fedora):
1. `sudo dnf install aravis-0.8 aravis-0.8-viewer python3-gobject` (if your Fedora has no `aravis-0.8` package: `sudo dnf copr enable emmanuelp/Aravis` first). Ubuntu: `sudo apt install gir1.2-aravis-0.8 aravis-tools python3-gi`.
2. The environment must see the system `gi` module: create it with `python3 -m venv --system-site-packages measure`, or for pipx: `pipx install --system-site-packages -e .`.
3. USB permissions: install Aravis's udev rule (`aravis.rules`, from the Aravis source, into `/etc/udev/rules.d/`) or test once with `sudo`. Check with `arv-tool-0.8` or `measurement control flir list`.

Both: use a USB3 port (blue) and on Linux raise the USB buffer for full-speed video: `echo 1000 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb`.

---

## Where the data goes

`--output-dir` (default `output`) is the root for everything.

| Command | Folder | File |
|---|---|---|
| `control ramp` | `output/ramp/` | `ramp_<UTC time>.csv`; with `--camera` also `ramp_<UTC time>_photos.csv` and the photos in `input/folder/<name>/` |
| `control pm` | `output/pm/` | `pm_<UTC time>.csv` |
| `control liv` | `output/liv/` | `liv_<UTC time>.csv` |
| `control camera` | `input/folder/<name>/` | `<name>_XXXX.jpg`, `<name>_XXXX.mp4`; log in `output/camera/camera_<UTC time>.csv` |
| `control flir` | `input/folder/<name>/` | `<name>_XXXX.jpg` (`.png`, `.tif`), `<name>_XXXX.mp4`; log in `output/camera/flir_<UTC time>.csv` |
| `analysis image` | `output/image/<name>/` | marked image, `<name>_lines.csv` |
| `analysis video` | `output/video/` | `frames/<name>/`, and `<name>/` with the marked frames and `lines.csv` |
| `analysis folder` | `output/folder/<name>/` | `results.csv`, `parameters.json`, marked photos, `tuning/` |
| `analysis report` | `output/report/<name>/` | `data.csv`, `plots.png` |

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

Set them in Python with `DetectionConfig(...)` or on the command line (`analysis image`, `analysis video`) as `--k 4`, `--min-fraction 0.5`, and so on.

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
| `strip_height` | 200 | Only this many rows around the image middle are analysed (curved lines stay straight in a strip, and it is faster); 0 or `None` = all rows |
| `min_threshold` | 2.0 | Absolute floor of the threshold in 0-255 levels; lower it for dark images |

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

Lower-level pieces: `detect_lines(img, config)` returns `(positions, signal, threshold)` for a NumPy image; `mark_image`, `plot_line_signal`, `split_video`, `read_lines_csv`, `read_time_stamp`, `spacing_stats` and `ramp_levels` are also exported. Hardware: `main_set_current`, `main_ramp`, `main_power_measurement` and `main_liv_measurement` (all take an object or dict with the settings; `output_csv` is optional). Camera: `main_ramp_camera` (ramp with photos), `main_photo`, `main_timelapse`, `main_video`, `main_camera_info` (dicts as in `examples/09_camera.py`) and the lower-level `CanonCamera`. FLIR: `main_flir_list`, `main_flir_info`, `main_flir_photo`, `main_flir_timelapse`, `main_flir_video` (dicts as in `examples/11_flir_camera.py`), the lower-level `FlirCamera`, and `main_ramp_camera` with `"camera_type": "flir"`.

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
    ├── Canon/
    │   ├── camera.py                 CanonCamera: connect, settings, capture, download (gphoto2)
    │   ├── capture.py                photo, time-lapse and video commands, file numbering
    │   └── ramp_camera.py            DC2200 ramp with photos (`control ramp --camera`, Canon or FLIR)
    ├── FLIR/
    │   ├── backends.py               Spinnaker/PySpin and Aravis access to the GenICam features
    │   ├── camera.py                 FlirCamera: settings, software-triggered photos, EXIF time
    │   └── capture.py                `control flir` photo, time-lapse and video commands
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
        ├── tune.py                   tunes the detection settings on one photo
        ├── folder.py                 analysis of a folder of photos, with warnings
        ├── report.py                 aligns photo results with a ramp and plots them
        ├── calibration.py            objective, sample and pixel size constants
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
| `07_folder_analysis.py` | Analyse a folder of photos without questions |
| `08_report.py` | Line photo results up with a ramp and plot |
| `09_camera.py` | Camera settings, a photo, a time-lapse and a video (needs the camera) |
| `10_ramp_camera.py` | DC2200 ramp with a photo in every step (needs both) |
| `11_flir_camera.py` | FLIR Blackfly S: settings, a photo, a time-lapse and a video (needs the camera) |

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
| `python-gphoto2 is required` | `pip install -e ".[camera]"` (or `sudo dnf install python3-gphoto2`) |
| `measurement_control` error | Install that package and connect the instrument over USB |
| `Thorlabs USB device ... not found` | Check the cable and the serial number and product ID in `src/ThorLabs/common.py` (`lsusb`) |
| USB permission denied (Linux) | Add a udev rule for vendor `1313`, or run with `sudo` |
| Camera: `could not claim the USB device` | `gio mount -s gphoto2; pkill -f gvfs-gphoto2-volume-monitor` |
| Camera: `No camera found` | Camera on, data cable, Wi-Fi/Bluetooth off; check `gphoto2 --auto-detect` |
| Camera: `'shutter' cannot be changed` | Mode dial on M (or Tv) |
| Camera: `no JPEG` | Set the image quality to JPEG, or `--image-format "Large Fine JPEG"` |
| FLIR: `no library for the FLIR camera is installed` | Install Spinnaker + PySpin, or Aravis + PyGObject; see [FLIR camera setup](#flir-camera-setup) |
| FLIR: `no FLIR camera ... was found` | USB3 cable, udev rule / permissions; close SpinView; `measurement control flir list` |
| FLIR: `ExposureTime ... outside the allowed range` | 15 µs – 30 s; with `--fps` the exposure must also be shorter than 1/fps |
| FLIR: `cannot be saved as JPEG` | 16-bit pixel format: add `--save-format png` (or `tiff`) |
| FLIR: video warns `frames were dropped` | Lower `--fps`, raise `usbfs_memory_mb`, or use a faster disk |
| `camera failed, ramp stopped` | See the camera error after it; the LED is already off |
| Time-lapse warns `late` | The interval is shorter than one capture + download; use a larger `-n` |

## License

MIT. Add a `LICENSE` file to the repository root.
