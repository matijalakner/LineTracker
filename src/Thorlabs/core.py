import time
import numpy as np

from measurement_control.communicators import USBCommunicator
from measurement_control.instruments.thorlabs_dc2200 import DC2200


def ramp_current(dc2200, start, stop, duration, update_rate):
    """Linearly ramp current from start to stop over duration seconds."""
    n_steps = max(2, int(duration * update_rate))

    start_time = time.monotonic()

    for i in range(n_steps + 1):
        fraction = i / n_steps
        current = start + fraction * (stop - start)

        # Set regulated LED current in amperes
        dc2200.configure_constant_current(current)

        # Keep timing based on a clock, not accumulated sleep time
        target_time = start_time + fraction * duration
        remaining = target_time - time.monotonic()

        if remaining > 0:
            time.sleep(remaining)


def main_ramp(cfg):
    """Ramp function control for the ThorLabs DC2200."""
    i_min, i_max, ramp_duration, update_rate, cycles = cfg.values()
    with DC2200(communicator=USBCommunicator()) as dc2200:
        print("LED heads:", dc2200.led_head_info)

        # Use a current limit no higher than your LED's safe rating
        dc2200.set_user_current_limit(i_max)

        # Start at the lower current
        dc2200.configure_constant_current(i_min)

        dc2200.switch_on()

        try:
            for _ in range(cycles):
                # Ramp up
                ramp_current(
                    dc2200,
                    i_min,
                    i_max,
                    ramp_duration,
                    update_rate,
                )

                # Ramp down
                ramp_current(
                    dc2200,
                    i_max,
                    i_min,
                    ramp_duration,
                    update_rate,
                )

        finally:
            # Ensure LED output is disabled if the script exits or errors
            dc2200.switch_off()