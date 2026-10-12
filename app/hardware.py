"""Opt-in Fruit Jam hardware adapter. Importing this module touches NO devices.

Physical qualification and remaining limits are recorded in the kit RESULTS.md.
"""
import sys
from stream import RATE, MAX_BANK_BYTES, Clock
from player import Debounce


class HardwareError(RuntimeError):
    pass


def _check_board(board):
    if getattr(board, "board_id", None) != "adafruit_fruit_jam":
        raise HardwareError("wrong board: requires board.board_id == adafruit_fruit_jam")
    for name in ("CKP", "CKN", "D0P", "D0N", "D1P", "D1N", "D2P", "D2N",
                 "BUTTON1", "BUTTON2", "BUTTON3"):
        if not hasattr(board, name):
            raise HardwareError("wrong board/pin definition: missing " + name)


def _environment():
    if sys.implementation.name != "circuitpython":
        raise HardwareError("hardware entry requires CircuitPython on Fruit Jam; host execution refused")
    try:
        import board
    except ImportError:
        raise HardwareError("wrong board: this CircuitPython build has no board module")
    _check_board(board)
    try:
        import crankjam
        import picodvi
        import displayio
        import framebufferio
        import digitalio
        import supervisor
        import time
    except ImportError as exc:
        raise HardwareError("missing firmware module: built-in crankjam and patched HDMI picodvi required: " + str(exc))
    runtime = getattr(crankjam, "Runtime", None)
    if runtime is None or any(not hasattr(runtime, name) for name in
                              ("step", "copy_framebuffer_into", "audio_into", "close", "refresh_rate", "heap_stats")):
        raise HardwareError("missing/wrong firmware: crankjam.Runtime API unavailable")
    for name in ("audio_write", "audio_stop", "audio_pending"):
        if not hasattr(picodvi.Framebuffer, name):
            raise HardwareError("missing/wrong firmware: patched picodvi.Framebuffer." + name)
    return board, picodvi, displayio, framebufferio, digitalio, supervisor, time, runtime


class Hardware:
    def __init__(self):
        self.fb = None
        self.display = None
        self.buttons = []  # fixed three entries, constructed before playback
        self.gamepad = None  # optional GamepadInput, owned and closed by the app
        self.displayio = None
        self.supervisor = None
        self.autoreload = None
        self.closed = False
        self.cleanup_error = None

    def initialize(self):
        board, picodvi, displayio, framebufferio, digitalio, supervisor, time, runtime = _environment()
        self.displayio = displayio
        self.supervisor = supervisor
        self.sleep = time.sleep
        self.clock = Clock(supervisor.ticks_ms)
        self.runtime_class = runtime
        self.autoreload = supervisor.runtime.autoreload
        supervisor.runtime.autoreload = False
        displayio.release_displays()
        self.fb = picodvi.Framebuffer(
            640, 480, clk_dp=board.CKP, clk_dn=board.CKN,
            red_dp=board.D0P, red_dn=board.D0N,
            green_dp=board.D1P, green_dn=board.D1N,
            blue_dp=board.D2P, blue_dn=board.D2N, color_depth=1)
        # No dedicated reserve API: a nonempty 32 kHz write allocates BOTH banks.
        # Do this BEFORE Bitmap, UI, Runtime arena, source, or game PCM buffers.
        accepted = self.fb.audio_write(bytes(MAX_BANK_BYTES), sample_rate=RATE)
        if type(accepted) is not int or not (0 < accepted <= MAX_BANK_BYTES) or accepted % 2:
            raise HardwareError("HDMI early bank reservation did not accept valid PCM bytes")
        self.fb.audio_stop()
        deadline = self.clock.now() + 250
        while self.fb.audio_pending:
            if self.clock.now() > deadline:
                raise HardwareError("HDMI reservation stop still pending after 250ms; hardware retained")
            time.sleep(0.001)
        self.display = framebufferio.FramebufferDisplay(self.fb, auto_refresh=False)
        self.bitmap = displayio.Bitmap(400, 240, 2)
        self.frame_view = memoryview(self.bitmap)
        if len(self.frame_view) != 52 * 240:
            raise HardwareError("unsupported Bitmap layout: expected writable 52-byte row stride")
        self.palette = displayio.Palette(2)
        self.palette[0], self.palette[1] = 0x000000, 0xffffff
        self.tile = displayio.TileGrid(self.bitmap, pixel_shader=self.palette, x=120, y=120)
        self.group = displayio.Group()
        self.group.append(self.tile)
        self.display.root_group = self.group
        for pin in (board.BUTTON1, board.BUTTON2, board.BUTTON3):
            button = digitalio.DigitalInOut(pin)
            self.buttons.append(button)  # retain for cleanup even if setup fails
            button.switch_to_input(pull=digitalio.Pull.UP)
        self.debounce = Debounce(self.clock)
        return self

    def read_buttons(self):
        raw = 0
        for i in range(3):
            if not self.buttons[i].value:
                raw |= 1 << i
        bits = self.debounce.update(raw)
        if self.gamepad is not None:
            now = self.clock.now()
            bits |= self.gamepad.poll(now)
            self.gamepad.record_poll(self.clock.now() - now)
        return bits

    def present(self, runtime):
        # Never gate this on audio_pending: that would freeze continuous games.
        # Initial root composition may cover 640x480; subsequent dirty area is
        # the full 400x240 canvas. This conservative path is NOT FPS proof.
        if runtime.copy_framebuffer_into(self.frame_view, stride=52) != 12000:
            raise HardwareError("Runtime framebuffer byte count mismatch")
        self.bitmap.dirty(0, 0, 400, 240)
        return self.display.refresh(target_frames_per_second=None,
                                    minimum_frames_per_second=0)

    def close(self, timeout_ms=250):
        """Bounded cleanup. False means resources retained: stop still pending."""
        if self.closed:
            return True
        for button in self.buttons:
            button.deinit()
        self.buttons = []
        if self.fb is not None:
            try:
                self.fb.audio_stop()
                deadline = self.clock.now() + timeout_ms
                while self.fb.audio_pending:
                    if self.clock.now() > deadline:
                        self.cleanup_error = "STOP_PENDING: physical silence not confirmed; display retained"
                        return False
                    self.sleep(0.001)
            except Exception as exc:
                self.cleanup_error = "STOP_PENDING: " + str(exc)
                return False
        if self.displayio is not None:
            self.displayio.release_displays()
        if self.supervisor is not None:
            self.supervisor.runtime.autoreload = self.autoreload
        self.closed = True
        return True
