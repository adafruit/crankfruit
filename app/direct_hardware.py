"""Fruit Jam scanout adapter: native bit-order copy, no displayio composition.

The original kit hardware.py remains the reference. This path writes the live
single scanout buffer, so it is not an atomic swap or a tear-free guarantee.
Optional /display.json {"scale": "1" | "1.6" | "1.6s", "white": "playdate" |
"bright"} selects a 2-bit greyscale
framebuffer whose modes (1x, 1.6x sharp, 1.6x smooth) B1 cycles while a gamepad
is connected. Without the file: the kit's 1-bit 1x output, B1 toggles 1x / 1.6x.
"""
from hardware import Hardware, HardwareError

SCALES = ('1', '1.6', '1.6s')
CYCLE_1BIT = ('1', '1.6')
CYCLE_2BIT = ('1', '1.6', '1.6s')
BLIT2_MODES = {'1': 0, '1.6': 1, '1.6s': 2}
WHITES = {'playdate': 2, 'bright': 3}  # 2-bit white level: ~50% grey (like 1-bit) or ~75%


def load_display_config(path):
    """Explicit optional JSON loader; a missing file is the caller's 1x default."""
    import json
    with open(path, 'r') as source:
        text = source.read(1025)
    if len(text) > 1024:
        raise ValueError('display configuration exceeds 1024 characters')
    config = json.loads(text)
    if not isinstance(config, dict):
        raise ValueError('display configuration must be an object')
    for key in config:
        if key not in ('scale', 'white'):
            raise ValueError('unknown display setting: ' + str(key))
    if config.get('scale', '1') not in SCALES:
        raise ValueError('display scale must be "1", "1.6" or "1.6s"')
    if config.get('white', 'playdate') not in WHITES:
        raise ValueError('display white must be "playdate" or "bright"')
    return config


def select_blit(module, scale, depth=1, white=2):
    """(copy function(src, dst), expected byte count) for scale and framebuffer depth."""
    if depth == 2:
        blit2 = getattr(module, 'blit2', None)
        if blit2 is None:
            raise HardwareError('2-bit display needs the updated _crankfruit_blit helper')
        if scale not in BLIT2_MODES:
            raise HardwareError('unsupported display scale: ' + str(scale))
        mode = BLIT2_MODES[scale]
        def copy(src, dst):
            return blit2(src, dst, mode, white)
        return copy, 76800
    if scale == '1.6':
        blit16 = getattr(module, 'blit16', None)
        if blit16 is None:
            raise HardwareError('display scale 1.6 needs the updated _crankfruit_blit helper')
        return blit16, 38400
    if scale != '1':
        raise HardwareError('unsupported display scale for a 1-bit framebuffer: ' + str(scale))
    return module.blit, 12000


class DirectHardware(Hardware):
    scale = '1'
    white = 2  # 2-bit only; Playdate-like default

    def configure(self, config):
        """Apply a loaded /display.json before initialize(): selects 2-bit greys."""
        self.scale = config.get('scale', '1')
        self.white = WHITES[config.get('white', 'playdate')]
        self.color_depth = 2

    def initialize(self):
        from stream import NATIVE_COPY
        if not NATIVE_COPY:
            raise HardwareError("player requires the native PCM copy helper")
        super().initialize()
        import _crankfruit_blit
        self._blit, self._blit_bytes = select_blit(_crankfruit_blit, self.scale, self.color_depth, self.white)
        self.scan_view = memoryview(self.fb)
        expected = 38400 * self.color_depth
        if len(self.scan_view) != expected:
            raise HardwareError("direct scanout requires exactly %d bytes for 640x480 at %d-bit" % (expected, self.color_depth))
        self._zeros = bytes(38400) if self.color_depth == 1 else None  # 1-bit 1x leaves edges
        print("DISPLAY_PATH", "native scanout", "640x480", "%d-bit" % self.color_depth, "scale", self.scale,
              "white", self.white if self.color_depth == 2 else 1)
        return self

    def settings_button(self, index):
        if index == 0:  # B1: next display mode, for this session
            cycle = CYCLE_2BIT if self.color_depth == 2 else CYCLE_1BIT
            position = cycle.index(self.scale) if self.scale in cycle else -1
            self.set_scale(cycle[(position + 1) % len(cycle)])

    def set_scale(self, scale):
        import _crankfruit_blit
        try:
            self._blit, self._blit_bytes = select_blit(_crankfruit_blit, scale, self.color_depth, self.white)
        except HardwareError as exc:
            print("DISPLAY_SCALE unchanged:", exc)  # a settings press must not end a scene
            return
        if scale == '1' and self.color_depth == 1 and self.scan_view is not None:
            self.scan_view[:] = self._zeros  # 1-bit 1x writes only the centre: drop old edges
        self.scale = scale
        print("DISPLAY_SCALE", scale)

    def present(self, runtime):
        if self.closed or self.scan_view is None:
            raise HardwareError("scanout already closed")
        if runtime.copy_framebuffer_into(self.frame_view, stride=52) != 12000:
            raise HardwareError("Runtime framebuffer byte count mismatch")
        if self._blit(self.frame_view, self.scan_view) != self._blit_bytes:
            raise HardwareError("native scanout byte count mismatch")
        return True

    def close(self, timeout_ms=250):
        # Never retain a native buffer view across driver teardown.
        self.scan_view = None
        return super().close(timeout_ms)
