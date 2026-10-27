import time

from .common import PM_PRODUCT_ID, PM_RESOURCE, close_quietly, sleep_until
from .usb_driver import ThorlabsUSBDriver


def _read_cfg(cfg):
    """Accepts a dict or an object (e.g. SimpleNamespace) with the power meter settings."""
    get = cfg.get if isinstance(cfg, dict) else (lambda k: getattr(cfg, k))

    defaults = {
        "wavelength": 633.0,
        "averaging_count": 10,
        "sample_duration": 5.0,
        "sample_rate": 10.0,
    }

    p = {}
    for k, default_val in defaults.items():
        try:
            val = get(k)
            p[k] = default_val if val is None else val
        except (KeyError, AttributeError):
            p[k] = default_val

    if p["wavelength"] <= 0:
        raise ValueError("wavelength must be > 0 nm")
    if p["averaging_count"] < 1:
        raise ValueError("averaging_count must be >= 1")
    if p["sample_duration"] <= 0 or p["sample_rate"] <= 0:
        raise ValueError("sample_duration and sample_rate must be > 0")

    return p


def main_power_measurement(cfg):
    """Power measurement loop for Thorlabs PM-series power meters.

    cfg needs: wavelength (nm), averaging_count, sample_duration (s), sample_rate (Hz).
    Returns a list of (time_s, power_W).
    """
    p = _read_cfg(cfg)

    try:
        from measurement_control.communicators import USBCommunicator
        from measurement_control.instruments.thorlabs_pm import ThorlabsPM
    except ImportError as e:
        raise RuntimeError(
            "The 'measurement_control' package is required to control the Thorlabs power meter."
        ) from e

    readings = []
    with ThorlabsUSBDriver(product_id=PM_PRODUCT_ID):
        print("Kernel USB driver detached. Connecting to Thorlabs Power Meter via PyVISA...")
        communicator = USBCommunicator(PM_RESOURCE)
        try:
            powermeter = ThorlabsPM(communicator)
            powermeter.set_wavelength(p["wavelength"])
            powermeter.set_averaging(p["averaging_count"])
            print(f"Starting power logging at {p['wavelength']} nm...")

            total = max(1, int(round(p["sample_duration"] * p["sample_rate"])))
            dt = 1.0 / p["sample_rate"]
            t0 = time.monotonic()
            for i in range(total):
                sleep_until(t0 + i * dt)
                power = powermeter.read_power()  # Watts
                readings.append((time.monotonic() - t0, power))
                print(f"Sample {i + 1}/{total} - Power: {power * 1e3:.4f} mW")
        finally:
            close_quietly(communicator)
    print("Power measurement sequence completed.")
    return readings
