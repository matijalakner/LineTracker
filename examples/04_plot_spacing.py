"""Plot the mean distance between the lines (error = std) against time.

Run:  python 04_plot_spacing.py input_footage
(the name of the video without extension; needs example 03 / 'analysis video' first)
"""
import sys

from line_finder import analyse_spacing

name = sys.argv[1] if len(sys.argv) > 1 else "input_footage"

result = analyse_spacing(name, output_dir="output")
print(f"{result['frames']} frames used")
print(f"Plot: {result['plot_path']}")
print(f"Data: {result['csv_path']}")
