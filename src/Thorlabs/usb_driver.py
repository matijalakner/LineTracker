import usb.core
import usb.util

THORLABS_VENDOR_ID = 0x1313

class ThorlabsUSBDriver:
    """Temporarily detach Linux kernel driver from any Thorlabs USB device for PyVISA-py or direct pyusb access."""

    def __init__(self, product_id=None):
        self.product_id = product_id
        self.device = None
        self.detached = False

    def __enter__(self):
        # If product_id is provided, match both; otherwise, find any device with Thorlabs Vendor ID (0x1313)
        if self.product_id is not None:
            self.device = usb.core.find(
                idVendor=THORLABS_VENDOR_ID, 
                idProduct=self.product_id
            )
        else:
            self.device = usb.core.find(
                idVendor=THORLABS_VENDOR_ID
            )

        if self.device is None:
            if self.product_id is not None:
                raise RuntimeError(
                    f"Thorlabs USB device (Vendor ID: {hex(THORLABS_VENDOR_ID)}, Product ID: {hex(self.product_id)}) not found"
                )
            else:
                raise RuntimeError(
                    f"No Thorlabs USB devices found (Vendor ID: {hex(THORLABS_VENDOR_ID)})"
                )

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