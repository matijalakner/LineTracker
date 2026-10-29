"""Detect vertical lines in ONE image.

Run:  python 01_single_image.py sample_photo.jpg
Writes output/image/<name>/<name>_marked.png, <name>_lines.csv, <name>_signal.png
"""
import sys
from pathlib import Path

from line_finder import DetectionConfig, analyse_image

image_path = sys.argv[1] if len(sys.argv) > 1 else "sample_photo.jpg"
out_dir = Path("output/image") / Path(image_path).stem

config = DetectionConfig()   # defaults; e.g. DetectionConfig(k=4, min_fraction=0.5)
result = analyse_image(image_path, out_dir, config, plot=True)

print(f"{len(result['lines'])} lines at x = {[int(x) for x in result['lines']]}")
print(f"Marked image: {result['marked_path']}")
