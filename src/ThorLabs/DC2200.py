import time

from .common import DC2200_PRODUCT_ID, DC2200_RESOURCE, close_quietly
from .usb_driver import ThorlabsUSBDriver

# Currents are in AMPERES (the DC2200 accepts up to 2 A; check your LED head's rating).
MAX_CURRENT_A = 2.0


def ramp_current(dc2200, start, stop, duration, update_rate, include_start=True):
    """Linearly ramp current (A) from start to stop over `duration` seconds.

    include_start=False skips the first point (use it for the second half of a
    cycle so the turning point is not set twice).
    """
    n_steps = max(2, int(duration * update_rate))
    start_time = time.monotonic()

    for i in range(0 if include_start else 1, n_steps + 1):
        fraction = i / n_steps
        dc2200.configure_constant_current(start + fraction * (stop - start))

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


def _import_dc2200():
    """Imported lazily so the rest of the package works without the instrument library."""
    try:
        from measurement_control.communicators import USBCommunicator
        from measurement_control.instruments.thorlabs_dc2200 import DC2200
    except ImportError as e:
        raise RuntimeError(
            "The 'measurement_control' package is required to control the DC2200."
        ) from e
    return USBCommunicator, DC2200


def main_ramp(cfg):
    """Ramp function control for the ThorLabs DC2200.

    cfg needs: i_min, i_max (A), ramp_duration (s), update_rate (Hz), cycles.
    """
    p = _read_cfg(cfg)
    USBCommunicator, DC2200 = _import_dc2200()

    with ThorlabsUSBDriver(product_id=DC2200_PRODUCT_ID):
        print("Kernel USB driver detached. Connecting to DC2200 via PyVISA...")
        communicator = USBCommunicator(DC2200_RESOURCE)
        try:
            dc2200 = DC2200(communicator)
            try:
                dc2200.set_user_current_limit(p["i_max"])
                dc2200.configure_constant_current(p["i_min"])
                dc2200.switch_on()

                for _ in range(p["cycles"]):
                    ramp_current(dc2200, p["i_min"], p["i_max"],
                                 p["ramp_duration"], p["update_rate"])
                    ramp_current(dc2200, p["i_max"], p["i_min"],
                                 p["ramp_duration"], p["update_rate"],
                                 include_start=False)
            finally:
                dc2200.switch_off()
        finally:
            close_quietly(communicator)


def _read_set_cfg(cfg):
    """Accepts a dict or an object with the key `current` (A)."""
    get = cfg.get if isinstance(cfg, dict) else (lambda k: getattr(cfg, k))
    current = float(get("current"))
    if not 0 <= current <= MAX_CURRENT_A:
        raise ValueError(f"current must be between 0 and {MAX_CURRENT_A} A")
    return current


def main_set_current(cfg):
    """Set the DC2200 LED output to a constant current and leave it running.

    cfg needs: current (A). The user current limit is set to the same value, so
    the device cannot exceed it. Unlike main_ramp, the output is NOT switched
    off afterwards; a current of 0 switches the output off instead.
    """
    current = _read_set_cfg(cfg)
    USBCommunicator, DC2200 = _import_dc2200()

    with ThorlabsUSBDriver(product_id=DC2200_PRODUCT_ID):
        print("Kernel USB driver detached. Connecting to DC2200 via PyVISA...")
        communicator = USBCommunicator(DC2200_RESOURCE)
        try:
            dc2200 = DC2200(communicator)
            if current == 0:
                dc2200.configure_constant_current(0.0)
                dc2200.switch_off()
                print("LED output switched off.")
            else:
                dc2200.set_user_current_limit(current)
                dc2200.configure_constant_current(current)
                dc2200.switch_on()
                print(f"LED output ON at {current * 1e3:.2f} mA "
                      f"(user limit {current * 1e3:.2f} mA).")
        finally:
            close_quietly(communicator)
