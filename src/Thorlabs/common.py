"""Shared constants and helpers for the Thorlabs modules.

One place for the USB identifiers, so the resource string and the product ID
used for the kernel-driver detach can never disagree again.
"""
import time

from .usb_driver import THORLABS_VENDOR_ID


def make_resource(product_id, serial):
    return f"USB0::{THORLABS_VENDOR_ID}::{product_id}::{serial}::0::INSTR"


DC2200_PRODUCT_ID = 0x80C8   # 32968
PM_PRODUCT_ID = 0x8075       # 33016  (was 0x8078 in PM40.py - did not match the resource string)

# Replace the serial numbers with those of your instruments.
DC2200_RESOURCE = make_resource(DC2200_PRODUCT_ID, "M00937194")
PM_RESOURCE = make_resource(PM_PRODUCT_ID, "P5003335")


def sleep_until(deadline):
    """Sleep until a time.monotonic() deadline (no accumulated drift)."""
    remaining = deadline - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def close_quietly(obj):
    close = getattr(obj, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
