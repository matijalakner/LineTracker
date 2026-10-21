# Line Finder

A Python library and CLI tool designed to detect thin vertical lines in images and video streams using a multi-strip profile sampling algorithm.

`strip-line-finder` samples horizontal row strips across an image or video frame, extracts signal deviation profiles to detect subtle line contrast, and links line detections across vertical strips while discarding random noise and dust.

---

## Features

- **Multi-Strip Sampling Engine:** Efficiently processes images by sampling horizontal strips rather than the entire pixel grid.
- **Robust Line Detection:** Uses moving median background estimation to identify thin vertical lines despite varying light conditions or gradients.
- **Vertical Tracking:** Links detections across adjacent strips to filter out noise, specks, and dust.
- **Video Processing:** Uniformly samples frames from video files (`.mp4`, `.avi`, etc.) and processes them individually with annotated visual exports.
- **Histogram & CSV Exports:** Generates pixel interval distribution histograms and saves detailed CSV/JSON reports.
- **Statistical Post-Processing:** Built-in statistical tools to compute spacing, averages, and standard deviations across detected lines.

---

## Installation

### Prerequisites

- Python `>= 3.8`
- `numpy`, `pillow`, `opencv-python`, and `pandas`

### Install Locally

Clone the repository and install the package using `pip`:

```bash
git clone https://github.com/matijalakner/LineFinder.git
cd strip-line-finder
pip install -e .
```

---

## Quick Start (Python API)

### 1. Process a Single Image

```python
from strip_line_finder import analyse_image, annotate_image

# Run analysis on an image file
width, height, lines, tracks = analyse_image("sample.jpg", args=your_args)

# Annotate detected tracks onto an output image
annotate_image(
    path="sample.jpg",
    lines=lines,
    tracks=tracks,
    margin=3,
    out_path="sample_marked.png",
    step=100,
    x_tolerance=20
)
```

### 2. Process and Slice Video Files

```python
from strip_line_finder import process_video

# Uniformly sample 15 frames from a video and extract vertical lines
results = process_video(
    video_path="input_video.mp4",
    num_frames=15,
    output_dir="./output_frames",
    step=100,
    min_contrast=7.0
)

# Inspect results per frame
for frame in results:
    print(f"Frame {frame['frame_index']} ({frame['timestamp_sec']}s): "
          f"Found {len(frame['tracks'])} line tracks.")
```

### 3. Analyze Output Statistics

```python
from strip_line_finder import analyze_cleaned_data_from_csv

# Process CSV histogram data to obtain mean spacing and standard deviation
report = analyze_cleaned_data_from_csv("histogram_output.csv")

print(f"Total Detected Lines: {report['total_lines']}")
print(f"Mean Spacing: {report['stats'].get('mean_diff', 0):.2f} px")
print(f"Std Deviation: {report['stats'].get('std_diff', 0):.2f} px")
```

---

## Command-Line Interface (CLI)

`strip-line-finder` includes a command-line utility for quick analysis.

### Single Image Mode

```bash
strip-line-finder image sample.jpg --step 100 --min-contrast 7.0 --output marked.png
```

### Video Slicing Mode

```bash
strip-line-finder video sample.mp4 --num-frames 20 --output-dir ./annotated_frames
```

---

## Project Structure

```text
strip-line-finder/
├── pyproject.toml
├── README.md
└── src/
    └── strip_line_finder/
        ├── __init__.py      # Package public exports
        ├── _core.py         # Profile filters, line detection algorithms
        ├── image.py         # Image loaders, annotation & histogram drawers
        ├── video.py         # OpenCV video frame extraction and pipeline
        ├── analysis.py      # Statistical post-processing routines
        └── cli.py           # Command-Line Interface router
```

---

## License

Distributed under the MIT License. See `LICENSE` for more information.