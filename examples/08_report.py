"""Line the photo results up with a DC2200 ramp and plot them.

Run:  python 08_report.py mysample [ramp_xxx.csv]
Needs output/folder/<name>/results.csv (analysis folder) and a ramp in output/ramp/.
Writes output/report/<name>/data.csv and plots.png
"""
import sys

from line_finder import main_report

name = sys.argv[1] if len(sys.argv) > 1 else "mysample"
ramp = sys.argv[2] if len(sys.argv) > 2 else None      # default: newest ramp
res = main_report(name, ramp=ramp, objective="20x", theta="0.8wt")
print(f"{res['photos']} photos during the ramp; plot: {res['plot_path']}")
