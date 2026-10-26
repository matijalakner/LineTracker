# strip-line-finder

A Python library and CLI for detecting thin, roughly vertical lines in images and video frames using multi-strip profile sampling.

Instead of scanning every pixel, `strip-line-finder` samples narrow horizontal strips at regular intervals, estimates the local background of each strip with a moving median, and flags pixels that deviate from it. Detections that line up vertically across several strips are linked into **tracks**; isolated detections (dust, specks, noise) are discarded.

## Contents

- [How it works](#how-it-works)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Parameter reference](#parameter-reference)
- [Return values](#return-values)
- [Command-line interface](#command-line-interface)
- [Post-processing: spacing statistics](#post-processing-spacing-statistics)
- [Examples](#examples)
- [Project structure](#project-structure)
- [Tuning tips](#tuning-tips)
- [Known limitations](#known-limitations)
- [License](#license)

## How it works

1. **Sample strips.** Every `step` rows, take a strip of `2 * margin + 1` rows and average it vertically into a 1-D colour profile (one RGB value per x position).
2. **Estimate background.** Apply a moving median (`bg_window` pixels) to each colour channel and to overall luminance. This tolerates gradients and uneven lighting.
3. **Threshold deviations.** A pixel is a candidate if its largest per-channel deviation is at least `min_contrast` and the local background luminance is at least `min_brightness` (so dark regions don't produce false positives).
4. **Group into lines.** Candidate pixels separated by no more than `gap` pixels are merged. Groups whose width is between `min_width` and `max_width` become a `Line`, labelled `"bright"` or `"dark"` relative to the background.
5. **Link into tracks.** Lines from different strips whose centres are within `x_tolerance` pixels are grouped. Groups seen in fewer than `min_strips` strips are dropped; the survivors are numbered left to right as tracks.

## Installation

Requires Python 3.8+ with `numpy`, `pillow`, `opencv-python` and `pandas` (installed automatically).

```bash
git clone https://github.com/your-username/strip-line-finder.git
cd strip-line-finder
pip install -e .
```

This also installs the `strip-line-finder` command.

## Quick start

### Analyse a single image

`analyse_image` takes any object that exposes the detection parameters as attributes (see the [parameter reference](#parameter-reference)). `types.SimpleNamespace` works well:

```python
from types import SimpleNamespace
from strip_line_finder import analyse_image, annotate_image, export_pixel_histogram

config = SimpleNamespace(
    step=100, margin=3, min_contrast=7.0, min_width=1, max_width=14,
    bg_window=41, gap=2, min_brightness=25.0,
    x_tolerance=20, min_strips=3, keep_all=False,
)

width, height, lines, tracks = analyse_image("sample_photo.jpg", config)
print(f"Detected {len(tracks)} vertical tracks in a {width}x{height} image.")

# Save a copy with detections drawn in red
annotate_image("sample_photo.jpg", lines, tracks, config.margin,
               "sample_photo_marked.png", config.step, config.x_tolerance)

# Save a histogram (PNG) and matching CSV of detections per x-interval
export_pixel_histogram("sample_photo.jpg", lines, bin_size=10,
                       out_path="sample_photo_histogram.png")
```

If you already have a NumPy array (RGB, `float32`, shape `H x W x 3`), call `analyse_image_array` directly. It takes the same parameters as keyword arguments with defaults:

```python
from strip_line_finder import analyse_image_array

width, height, lines, tracks = analyse_image_array(img_array, step=50, min_contrast=6.0)
```

### Analyse a video

`process_video` samples `num_frames` evenly spaced frames, runs the detector on each, and optionally saves annotated PNGs. Any extra keyword arguments are forwarded to `analyse_image_array`.

```python
from strip_line_finder import process_video

results = process_video(
    video_path="input_footage.mp4",
    num_frames=12,
    output_dir="./analyzed_video_frames",   # optional; omit to skip saving images
    step=100,
    min_contrast=6.5,
    x_tolerance=20,
)

for frame in results:
    print(f"Frame {frame['frame_index']} ({frame['timestamp_sec']}s): "
          f"{len(frame['tracks'])} vertical tracks")
```

## Parameter reference

| Parameter | Default | Description |
|---|---|---|
| `step` | `100` | Sample one strip every `step` rows. Smaller values give more strips and slower, denser tracking. |
| `margin` | `3` | Strip half-height. Each strip covers rows `row - margin` to `row + margin`. |
| `min_contrast` | `7.0` | Minimum deviation from the local background (0 to 255 scale) for a pixel to count. Lower is more sensitive and noisier. |
| `min_width` | `1` | Minimum line width in pixels. |
| `max_width` | `14` | Maximum line width in pixels. Wider features are ignored. |
| `bg_window` | `41` | Moving-median window (pixels) for background estimation. Should be clearly wider than the widest line. |
| `gap` | `2` | Maximum run of non-candidate pixels bridged when merging a line. |
| `min_brightness` | `25.0` | Minimum background luminance. Suppresses detections in very dark regions. |
| `x_tolerance` | `20` | Maximum horizontal drift (pixels) when linking detections across strips. |
| `min_strips` | `3` | Minimum number of distinct strips a track must appear in. |
| `keep_all` | `False` | If `True`, return all raw detections instead of only those that belong to a track. |

## Return values

`analyse_image` and `analyse_image_array` return `(width, height, lines, tracks)`:

- `lines` is a list of `Line` dataclasses:

  | Field | Meaning |
  |---|---|
  | `row` | Centre row of the strip the line was found in |
  | `start_px`, `end_px` | First and last x pixel of the line |
  | `center_px` | Contrast-weighted centre x position |
  | `width_px` | Line thickness along the strip |
  | `polarity` | `"bright"` or `"dark"` relative to the surroundings |
  | `contrast` | Peak deviation strength (0 to 255 scale) |
  | `track_id` | Track number (1-based, left to right), or `-1` if unlinked |

- `tracks` is a list of tracks, each a list of `Line` objects sorted by row.

`process_video` returns one dict per successfully decoded frame with the keys `frame_index`, `timestamp_sec`, `width`, `height`, `lines`, and `tracks`.

## Command-line interface

```bash
# Single image
strip-line-finder image sample.jpg --step 100 --margin 3 --min-contrast 7.0 --output marked.png

# Video: sample frames and save annotated PNGs
strip-line-finder video sample.mp4 --num-frames 20 --output-dir ./annotated_frames
```

Options currently exposed:

| Command | Options |
|---|---|
| `image` | `--step`, `--margin`, `--min-contrast`, `--output` (defaults to `<name>_marked.png`) |
| `video` | `--num-frames` (default 10), `--output-dir` (default `video_frames_output`) |

All other parameters use the defaults from the table above. For full control, use the Python API.

## Post-processing: spacing statistics

`export_pixel_histogram` writes a CSV next to the histogram image with the columns `pixel_interval_start`, `pixel_interval_end`, `number_of_points`. `analyze_cleaned_data_from_csv` reads such a file and:

1. Drops empty intervals.
2. Clusters intervals whose starts are within 50 px of each other.
3. Keeps the interval with the highest count in each cluster as one "line" position.
4. Reports the spacing between consecutive line positions.

```python
from strip_line_finder import analyze_cleaned_data_from_csv

report = analyze_cleaned_data_from_csv("sample_photo_histogram.csv")

print(f"Total lines: {report['total_lines']}")
print(f"Pixel indexes: {report['pixel_indexes']}")

stats = report["stats"]
if stats:
    print(f"Mean spacing: {stats['mean_diff']:.2f} px")
    print(f"Std deviation: {stats['std_diff']:.2f} px")
    print(f"Min / max spacing: {stats['min_diff']} / {stats['max_diff']} px")
```

`stats` is empty when fewer than two line positions are found.

## Examples

Runnable scripts are in [`examples/`](examples/):

| File | Demonstrates |
|---|---|
| `single_image.py` | Detection, annotation and histogram export for one image |
| `video_analysis.py` | Frame sampling and per-frame track counts for a video |
| `statistical_analysis.py` | Spacing statistics from an exported CSV |

Update the input paths at the top of each script before running.

## Project structure

```text
strip-line-finder/
├── pyproject.toml
├── README.md
├── examples/
│   ├── single_image.py
│   ├── video_analysis.py
│   └── statistical_analysis.py
└── src/
    └── strip_line_finder/
        ├── __init__.py      # Public API exports
        ├── _core.py         # Line dataclass, background filter, detection, track linking
        ├── image.py         # Image analysis, annotation, histogram/CSV export
        ├── video.py         # Frame sampling and video pipeline (OpenCV)
        ├── analysis.py      # Spacing statistics from histogram CSVs
        └── cli.py           # Command-line entry point
```

## Tuning tips

- **Missing faint lines:** lower `min_contrast`, or reduce `step` so more strips vote.
- **Too many false positives:** raise `min_contrast`, raise `min_strips`, or narrow `max_width`.
- **Lines being split in two:** increase `gap`.
- **Slanted lines not linking:** increase `x_tolerance`, or decrease `step` so lines drift less between strips.
- **Detections in dark areas:** raise `min_brightness`.
- **Wide lines vanishing into the background:** increase `bg_window` so it stays well above `max_width`.

## Known limitations

- Designed for near-vertical lines; strongly slanted or curved lines will not link reliably.
- Video frames are sampled uniformly and analysed independently; there is no tracking between frames.
- `process_video` and the CLI write annotated images only. Line and track data are returned in Python and not exported to CSV or JSON.

## License

Distributed under the MIT License. Add a `LICENSE` file to the repository root before publishing.