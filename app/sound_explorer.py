"""Original Sound Explorer for the bounded Crankfruit player.

SPDX-License-Identifier: MIT
One persistent synth Runtime; samples are decoded off-device and loaded once.
No Python per-sample synthesis, conversion, slicing or mixing during playback.
"""
from _crankfruit_pcm import copy_into

RATE = 32000
MAX_CHUNK = 2134
PITCHES = ('220 HZ', '262 HZ', '330 HZ', '392 HZ', '440 HZ', '523 HZ', '659 HZ', '880 HZ')
DECAYS = ('100 MS', '200 MS', '400 MS', '800 MS')
WAVES = ('SQUARE', 'TRIANGLE', 'PDA SAMPLE')
SAMPLES = ('BOOT CHIME', 'COIN RISE', 'SOFT SWOOP')
SAMPLE_FILES = ('sample_boot.pcm', 'sample_coin.pcm', 'sample_swoop.pcm')

SOUND_SOURCE = b'''local p=playdate
p.display.setRefreshRate(30)
local square=p.sound.synth.new(p.sound.kWaveSquare)
local triangle=p.sound.synth.new(p.sound.kWaveTriangle)
square:setVolume(0.28);triangle:setVolume(0.34)
local pitches={220,261.63,329.63,392,440,523.25,659.25,880}
local decays={0.1,0.2,0.4,0.8}
function p.update()
 local trigger=p.getCrankChange()
 if trigger==0 then return end
 square:stop();triangle:stop()
 if trigger<0 then return end
 local pitch=1
 if p.buttonIsPressed(2) then pitch=pitch+1 end
 if p.buttonIsPressed(4) then pitch=pitch+2 end
 if p.buttonIsPressed(8) then pitch=pitch+4 end
 local decay=1
 if p.buttonIsPressed(16) then decay=decay+1 end
 if p.buttonIsPressed(32) then decay=decay+2 end
 local voice=p.buttonIsPressed(1) and triangle or square
 voice:setADSR(0.005,decays[decay],0,0.025)
 voice:playNote(pitches[pitch],0.8,decays[decay]+0.01)
end
'''


def _load_pcm(path):
    with open(path, 'rb') as source:
        pcm = source.read(65537)
    if not pcm or len(pcm) > 65536 or len(pcm) % 2:
        raise ValueError('sample must be nonempty PCM16LE, at most 65536 bytes')
    return pcm


class SoundExplorer:
    """B1/B2 value, short B3 next field, B1+B2 replay; hold B3 is parent-owned."""
    def __init__(self, runtime_class, path='/player/assets'):
        from canvas import Canvas
        self.canvas = Canvas(path)
        self.sound = None
        try:
            self.samples = tuple(_load_pcm(path + '/' + name) for name in SAMPLE_FILES)
            self.zeros = bytes(MAX_CHUNK)
            self.sound = runtime_class(SOUND_SOURCE, heap_cap=32768)
        except Exception:
            self.canvas.close()
            raise
        self.wave = 0
        self.pitch = 4
        self.decay = 1
        self.sample = 0
        self.field = 0
        self.last_buttons = 0
        self.b3_started = None
        self.offset = len(self.samples[0])
        self.first = True
        self.dirty = True
        self.closed = False
        self.auditions = 0

    def refresh_rate(self):
        return 30

    def step(self, buttons, angle, delta, elapsed):
        if self.closed:
            raise RuntimeError('sound explorer closed')
        pressed = buttons & ~self.last_buttons
        released = self.last_buttons & ~buttons
        self.last_buttons = buttons
        if pressed & 32:
            self.b3_started = elapsed
        if released & 32 and self.b3_started is not None:
            if 0 <= elapsed - self.b3_started < 900:
                self.field = (self.field + 1) % (2 if self.wave == 2 else 3)
                self.dirty = True
            self.b3_started = None
        audition = self.first or bool(pressed & 16)
        direction = -1 if pressed & 1 else (1 if pressed & 2 else 0)
        if direction and not buttons & 16:
            if self.field == 0:
                self.wave = (self.wave + direction) % 3
            elif self.wave == 2:
                self.sample = (self.sample + direction) % len(self.samples)
            elif self.field == 1:
                self.pitch = (self.pitch + direction) % len(PITCHES)
            else:
                self.decay = (self.decay + direction) % len(DECAYS)
            audition = True
            self.dirty = True
        config = (self.wave & 1) | (self.pitch << 1) | (self.decay << 4)
        trigger = 0
        if audition:
            self.auditions += 1
            if self.wave == 2:
                self.offset = 0
                trigger = -1  # stop both synths; cached sample owns output
            else:
                self.offset = len(self.samples[self.sample])
                trigger = 1
        self.sound.step(config, 0, trigger, elapsed)
        self.first = False
        if self.dirty:
            self.draw()
            self.dirty = False

    def draw(self):
        c = self.canvas
        c.begin('explorer')
        c.text('WAVE', 36, 66)
        c.text(WAVES[self.wave], 144, 66)
        c.text('SAMPLE' if self.wave == 2 else 'PITCH', 36, 90)
        c.text(SAMPLES[self.sample] if self.wave == 2 else PITCHES[self.pitch], 144, 90)
        c.text('FORMAT' if self.wave == 2 else 'DECAY', 36, 114)
        c.text('32K MONO PCM16' if self.wave == 2 else DECAYS[self.decay], 144, 114)
        c.text('>', 22, 66 + self.field * 24)
        name = ('wave_square', 'wave_triangle', 'wave_sample')[self.wave]
        if name in c.ids:
            c.sprite(name, 32, 144)
        if 'envelope' in c.ids:
            c.sprite('envelope', 238, 144)
        c.text('WAVEFORM', 44, 189)
        c.text('LEVEL ENVELOPE', 230, 189)
        c.render()

    def audio_into(self, target, rate=RATE):
        if self.closed or rate != RATE or len(target) % 2 or len(target) > MAX_CHUNK:
            raise ValueError('sound explorer requires open 32k PCM16 blocks <=2134 bytes')
        if self.wave != 2:
            return self.sound.audio_into(target, rate=rate)
        n = len(target)
        sample = self.samples[self.sample]
        copied = min(n, len(sample) - self.offset)
        if copied:
            if copy_into(target, sample, 0, self.offset, copied) != copied:
                raise RuntimeError('sample native copy mismatch')
            self.offset += copied
        if copied < n:
            tail = n - copied
            if copy_into(target, self.zeros, copied, 0, tail) != tail:
                raise RuntimeError('silence native copy mismatch')
        return n

    def copy_framebuffer_into(self, target, stride=52):
        return self.canvas.copy_framebuffer_into(target, stride=stride)

    def heap_stats(self):
        return self.sound.heap_stats()

    def close(self):
        if not self.closed:
            self.closed = True
            self.sound.close()
            self.canvas.close()
            self.samples = self.zeros = None
