"""Detect vertical lines in ONE image with fixed parameters.

Run:  python 01_single_image.py sample_photo.jpg
Writes sample_photo_marked.png, sample_photo_histogram.png and .csv
"""
import sys

from line_finder import (AnalysisConfig, analyse_image, annotate_image,
                         export_pixel_histogram)

image_path = sys.argv[1] if len(sys.argv) > 1 else "sample_photo.jpg"
stem = image_path.rsplit(".", 1)[0]

config = AnalysisConfig(min_contrast=7.0)  # every other value keeps its default

# 1. Analyse: returns image size, kept detections and the vertical tracks
width, height, lines, tracks = analyse_image(image_path, config)
print(f"{len(tracks)} vertical line tracks in a {width}x{height} image "
      f"({len(lines)} strip detections)")

for t in tracks:
    xs = [m.center_px for m in t]
    print(f"  track {t[0].track_id}: x = {sum(xs) / len(xs):.1f} px, "
          f"seen on {len(t)} strips")

# 2. Save a copy of the image with the lines marked in red
annotate_image(image_path, lines, tracks, config.margin,
               f"{stem}_marked.png", config.step, config.x_tolerance)

# 3. Histogram of line positions (PNG) plus the same data as CSV
export_pixel_histogram(image_path, lines, bin_size=10,
                       out_path=f"{stem}_histogram.png")
