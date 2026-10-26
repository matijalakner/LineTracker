import time
import json

def _read_cfg(cfg):
    """Parses and validates configuration for both DC2200 and PM40."""
    get = cfg.get if isinstance(cfg, dict) else (lambda k: getattr(cfg, k))
    
    defaults = {
        "i_min": 0.0,
        "i_max": 0.1,
        "ramp_duration": 10.0,
        "update_rate": 10.0,
        "cycles": 1,
        "wavelength": 633.0,
        "averaging_count": 10
    }
    
    p = {}
    for k, default_val in defaults.items():
        try:
            val = get(k)
            p[k] = default_val if val is None else val
        except (KeyError, AttributeError):
            p[k] = default_val

    if p["i_min"] < 0 or p["i_max"] < 0:
        raise ValueError("currents must be >= 0 A")
    if p["i_max"] < p["i_min"]:
        raise ValueError("i_max must be >= i_min")
    if p["wavelength"] <= 0:
        raise ValueError("wavelength must be > 0 nm")
        
    return p


def main_liv_measurement(cfg):
    """Simultaneously ramps the DC2200 current and logs power from the PM40 power meter."""
    p = _read_cfg(cfg)

    try:
        from measurement_control.instruments.thorlabs_dc2200 import DC2200
        from measurement_control.instruments.thorlabs_pm import ThorlabsPM
    except ImportError as e:
        raise RuntimeError(
            "The 'measurement_control' package is required to control Thorlabs instruments."
        ) from e

    # Update these resource strings with your actual connected device identifiers
    DC2200_RESOURCE = "USB0::4883::32968::M00937194::0::INSTR"
    PM_RESOURCE = "USB0::4883::33016::P0012345::0::INSTR"

    print("Connecting to DC2200 and PM40 via PyVISA...")
    dc2200 = DC2200(DC2200_RESOURCE)
    powermeter = ThorlabsPM(PM_RESOURCE)

    try:
        # Configure Power Meter
        powermeter.set_wavelength(p["wavelength"])
        powermeter.set_averaging(p["averaging_count"])

        # Configure DC2200 Driver
        dc2200.set_user_current_limit(p["i_max"])
        dc2200.configure_constant_current(p["i_min"])
        dc2200.switch_on()
        print("LED Driver switched ON. Starting synchronized ramp & power log...")

        total_steps = int(p["ramp_duration"] * p["update_rate"])
        dt = 1.0 / p["update_rate"]

        for cycle in range(p["cycles"]):
            print(f"--- Cycle {cycle + 1}/{p['cycles']} (Ramping Up) ---")
            
            # Ramp Up: i_min -> i_max
            for step in range(total_steps + 1):
                fraction = step / total_steps if total_steps > 0 else 1.0
                current = p["i_min"] + fraction * (p["i_max"] - p["i_min"])
                
                # Apply current and read power simultaneously
                dc2200.configure_constant_current(current)
                power_w = powermeter.read_power()
                
                print(f"Current: {current*1e3:.2f} mA | Power: {power_w*1e3:.4f} mW")
                time.sleep(dt)

            print(f"--- Cycle {cycle + 1}/{p['cycles']} (Ramping Down) ---")
            
            # Ramp Down: i_max -> i_min
            for step in range(total_steps + 1):
                fraction = step / total_steps if total_steps > 0 else 1.0
                current = p["i_max"] - fraction * (p["i_max"] - p["i_min"])
                
                dc2200.configure_constant_current(current)
                power_w = powermeter.read_power()
                
                print(f"Current: {current*1e3:.2f} mA | Power: {power_w*1e3:.4f} mW")
                time.sleep(dt)

    finally:
        print("Turning off DC2200 LED output...")
        dc2200.switch_off()
        print("Measurement completed safely.")