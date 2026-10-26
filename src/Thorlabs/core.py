import time

# Currents are in AMPERES (the DC2200 accepts up to 2 A; check your LED head's rating).


def ramp_current(dc2200, start, stop, duration, update_rate):
    """Linearly ramp current (A) from start to stop over `duration` seconds."""
    n_steps = max(2, int(duration * update_rate))
    start_time = time.monotonic()

    for i in range(n_steps + 1):
        fraction = i / n_steps
        current = start + fraction * (stop - start)

        # Set regulated LED current in amperes
        dc2200.configure_constant_current(current)

        # Keep timing based on a clock, not accumulated sleep time
        remaining = start_time + fraction * duration - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


def _read_cfg(cfg):
    """Accepts a dict or an object (e.g. SimpleNamespace) with the ramp settings."""
    get = cfg.get if isinstance(cfg, dict) else (lambda k: getattr(cfg, k))
    p = {k: get(k) for k in ("i_min", "i_max", "ramp_duration", "update_rate", "cycles")}
    if p["i_min"] < 0 or p["i_max"] < 0:
        raise ValueError("currents must be >= 0 A")
    if p["i_max"] < p["i_min"]:
        raise ValueError("i_max must be >= i_min")
    if p["ramp_duration"] <= 0 or p["update_rate"] <= 0:
        raise ValueError("ramp_duration and update_rate must be > 0")
    if p["cycles"] < 1:
        raise ValueError("cycles must be >= 1")
    return p


def main_ramp(cfg):
    """Ramp function control for the ThorLabs DC2200.

    cfg needs: i_min, i_max (A), ramp_duration (s), update_rate (Hz), cycles.
    """
    p = _read_cfg(cfg)

    # Imported here so the rest of the package works without the instrument library.
    try:
        from measurement_control.communicators import USBCommunicator
        from measurement_control.instruments.thorlabs_dc2200 import DC2200
    except ImportError as e:
        raise RuntimeError(
            "The 'measurement_control' package is required to control the DC2200."
        ) from e

    with DC2200(communicator=USBCommunicator()) as dc2200:
        print("LED heads:", dc2200.led_head_info)

        # Use a current limit no higher than your LED's safe rating
        dc2200.set_user_current_limit(p["i_max"])
        dc2200.configure_constant_current(p["i_min"])
        dc2200.switch_on()

        try:
            for _ in range(p["cycles"]):
                ramp_current(dc2200, p["i_min"], p["i_max"],
                             p["ramp_duration"], p["update_rate"])
                ramp_current(dc2200, p["i_max"], p["i_min"],
                             p["ramp_duration"], p["update_rate"])
        finally:
            # Ensure LED output is disabled if the script exits or errors
            dc2200.switch_off()