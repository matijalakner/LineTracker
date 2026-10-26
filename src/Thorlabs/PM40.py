from .usb_driver import ThorlabsUSBDriver

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

def main_power_measurement(cfg):
    """Power measurement control and logging loop for Thorlabs PM-series power meters.

    cfg needs: wavelength (nm), averaging_count, sample_duration (s), sample_rate (Hz).
    """
    p = _read_cfg(cfg)

    # Imported here so the rest of the package works without the instrument library.
    try:
        from measurement_control.communicators import USBCommunicator
        # Assumes a corresponding Thorlabs PM power meter instrument class exists
        from measurement_control.instruments.thorlabs_pm import ThorlabsPM
    except ImportError as e:
        raise RuntimeError(
            "The 'measurement_control' package is required to control the Thorlabs power meter."
        ) from e

    # Example PyVISA USB resource string for Thorlabs power meters 
    # (Vendor ID: 0x1313, Product ID typically ends around 0x807x)
    USB_RESOURCE = "USB0::4883::33016::P0012345::0::INSTR"

    # Product ID for Thorlabs PM power meters (e.g., 0x8078 for PM101/PM100 variants)
    # If unsure, you can pass product_id=None to catch any Thorlabs device connected.
    PM_PRODUCT_ID = 0x8078  

    # 1. Detach the Linux kernel USB driver lock so PyVISA-py can access the power meter
    with ThorlabsUSBDriver(product_id=PM_PRODUCT_ID):
        print("Kernel USB driver detached. Connecting to Thorlabs Power Meter via PyVISA...")
        
        # 2. Instantiate and control the power meter instrument
        powermeter = ThorlabsPM(USB_RESOURCE)
        
        try:
            # Configure basic power meter measurement parameters
            powermeter.set_wavelength(p["wavelength"])
            powermeter.set_averaging(p["averaging_count"])
            
            print(f"Starting power logging at {p['wavelength']} nm...")
            
            # Example measurement routine (e.g., polling optical power over time)
            total_samples = int(p["sample_duration"] * p["sample_rate"])
            delay = 1.0 / p["sample_rate"]
            
            import time
            for i in range(total_samples):
                optical_power = powermeter.read_power()  # Returns power in Watts
                print(f"Sample {i+1}/{total_samples} - Power: {optical_power * 1e3:.4f} mW")
                time.sleep(delay)
                
        finally:
            # Safely wrap up or zero out states if required by the instrument class
            print("Power measurement sequence completed.")