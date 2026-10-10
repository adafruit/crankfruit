"""Locally stored startup clip, pre-rendered by the actual CrankJam engine.

Not a Lua interpreter or live game substitute. This finite boot-only adapter
reuses GamePlayer's tested PCM queue and native framebuffer presentation.
All asset I/O completes before playback; games still use crankjam.Runtime.
"""
FRAME_BYTES = 52 * 240


def _read(path, limit):
    with open(path, "rb") as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError("oversized boot asset: " + path)
    return data


class BootClip:
    def __init__(self, path="/bootclip"):
        frames = _read(path + "/boot.frames", 75 * FRAME_BYTES)
        self.index = _read(path + "/boot.index", 75)
        pcm = _read(path + "/boot.pcm", 160000)
        if len(self.index) != 75 or len(pcm) != 160000:
            raise ValueError("boot clip must contain 75 frames and 80000 samples")
        if not frames or len(frames) % FRAME_BYTES:
            raise ValueError("bad boot frame storage")
        if max(self.index) >= len(frames) // FRAME_BYTES:
            raise ValueError("boot frame index out of range")
        self.frames = memoryview(frames)
        self.pcm = memoryview(pcm)
        self.silence = memoryview(bytes(2134))
        self.frame = 0
        self.offset = 0

    def refresh_rate(self):
        return 30

    def heap_stats(self):
        return ("PRERENDERED_BOOT_ASSET_BYTES", len(self.frames) + len(self.pcm) + len(self.index))

    def step(self, buttons, angle, delta, elapsed):
        self.frame = self.index[min(74, max(0, (elapsed * 30 + 29) // 1000))]

    def copy_framebuffer_into(self, target, stride=52):
        if stride != 52 or len(target) != FRAME_BYTES:
            raise ValueError("boot presentation requires 52-byte row stride")
        start = self.frame * FRAME_BYTES
        target[:] = self.frames[start:start + FRAME_BYTES]
        return 12000

    def audio_into(self, target, rate=32000):
        if rate != 32000 or len(target) not in (2132, 2134):
            raise ValueError("boot audio requires 30Hz PCM16 chunks at 32kHz")
        count = min(len(target), len(self.pcm) - self.offset)
        target[:count] = self.pcm[self.offset:self.offset + count]
        target[count:] = self.silence[:len(target) - count]
        self.offset += count
        return len(target)

    def close(self):
        self.frames = self.pcm = self.index = self.silence = None
