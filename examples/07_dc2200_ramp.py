"""Ramp the LED current of a Thorlabs DC2200 up and down.

Needs the `measurement_control` package and a connected DC2200.
Currents are in AMPERES - check your LED head's rating before running.

Run:  python 07_dc2200_ramp.py
"""
from types import SimpleNamespace

from line_finder import main_ramp

cfg = SimpleNamespace(
    i_min=0.0,            # A, start current
    i_max=0.5,            # A, also set as the device's user current limit
    ramp_duration=60.0,   # s, for EACH up or down ramp
    update_rate=20.0,     # current updates per second
    cycles=1,             # number of up + down cycles
)

try:
    main_ramp(cfg)        # switches the LED off again, even on errors
except KeyboardInterrupt:
    print("Interrupted - LED output switched off.")
