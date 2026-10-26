"""Let the library choose the parameters from the image itself.

Run:  python 02_auto_parameters.py sample_photo.jpg
"""
import sys

import numpy as np
from PIL import Image

from line_finder import AnalysisConfig, analyse_image, auto_parameters

image_path = sys.argv[1] if len(sys.argv) > 1 else "sample_photo.jpg"
image = np.asarray(Image.open(image_path).convert("RGB"))

# Optionally fix some values; the others adapt to them, e.g. {"step": 80}
params, measurements = auto_parameters(image, overrides=None)

print("Measured:")
for key, value in measurements.items():
    print(f"  {key:<18} {value}")
print("Chosen parameters:")
for key, value in params.items():
    print(f"  {key:<18} {value}")

width, height, lines, tracks = analyse_image(image_path, AnalysisConfig(**params))
print(f"\n{len(tracks)} line tracks found.")
