"""Fruit Jam scanout adapter: native bit-order copy, no displayio composition.

The original kit hardware.py remains the reference. This path writes the live
single scanout buffer, so it is not an atomic swap or a tear-free guarantee.
"""
from hardware import Hardware, HardwareError


class DirectHardware(Hardware):
    def initialize(self):
        from stream import NATIVE_COPY
        if not NATIVE_COPY:
            raise HardwareError("player requires the native PCM copy helper")
        super().initialize()
        import _crankfruit_blit
        self._blit = _crankfruit_blit.blit
        self.scan_view = memoryview(self.fb)
        if len(self.scan_view) != 38400:
            raise HardwareError("direct scanout requires exactly 640x480 one-bit bytes")
        print("DISPLAY_PATH", "native bit-reverse blit", "640x480, centered 400x240")
        return self

    def present(self, runtime):
        if self.closed or self.scan_view is None:
            raise HardwareError("scanout already closed")
        if runtime.copy_framebuffer_into(self.frame_view, stride=52) != 12000:
            raise HardwareError("Runtime framebuffer byte count mismatch")
        if self._blit(self.frame_view, self.scan_view) != 12000:
            raise HardwareError("native scanout byte count mismatch")
        return True

    def close(self, timeout_ms=250):
        # Never retain a native buffer view across driver teardown.
        self.scan_view = None
        return super().close(timeout_ms)
