"""Set the LED current of a Thorlabs DC2200 and leave the light on.

Needs the `measurement_control` package and a connected DC2200.
The current is in AMPERES - check your LED head's rating before running.

Run:  python 06_dc2200_set.py 0.25     (0 switches the output off)
"""
import sys
from types import SimpleNamespace

from line_finder import main_set_current

current = float(sys.argv[1]) if len(sys.argv) > 1 else 0.1
main_set_current(SimpleNamespace(current=current))
