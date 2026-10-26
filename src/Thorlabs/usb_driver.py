
import usb.core
import usb.util


VENDOR_ID = 0x1313
PRODUCT_ID = 0x80C8


class DC2200USBDriver:
    """Temporarily detach Linux USBTMC from the DC2200 for PyVISA-py access."""

    def __init__(self):
        self.device = None
        self.detached = False

    def __enter__(self):
        self.device = usb.core.find(
            idVendor=VENDOR_ID,
            idProduct=PRODUCT_ID,
        )
        if self.device is None:
            raise RuntimeError("Thorlabs DC2200 USB device not found")

        try:
            if self.device.is_kernel_driver_active(0):
                self.device.detach_kernel_driver(0)
                self.detached = True
        except Exception:
            # Do not proceed if USB ownership is uncertain.
            if self.detached:
                self.device.attach_kernel_driver(0)
                self.detached = False
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.device is not None and self.detached:
            try:
                self.device.attach_kernel_driver(0)
            finally:
                self.detached = False
        return False
