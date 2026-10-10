# sound explorer

original standalone Crankfruit player mode. no Courier import or game dependency.
MIT code and original synthetic sample assets; no third-party audio.

## install contract

place `sound_explorer.py` beside the player modules and place these files in
`/player/assets/` (or the constructor's explicit asset directory):

- `sample_boot.pcm`: 28,800 bytes, 450ms
- `sample_coin.pcm`: 12,800 bytes, 200ms
- `sample_swoop.pcm`: 32,000 bytes, 500ms

all are 32000Hz mono signed16 little-endian PCM. constructor caches all 73,600
sample bytes plus a 2,134-byte zero buffer before playback. no filesystem access,
Python per-sample loops, runtime recreation, sample decoding, or slicing in
`audio_into`. one or two bounded native `copy_into` calls fill a sample block.
GamePlayer blocks must be even-sized and at most 2,134 bytes.

requires `_crankfruit_pcm.copy_into`, the existing `Canvas`, and a crankjam
Runtime constructor. no silent copy fallback exists on the device path.
instantiate `SoundExplorer(runtime_class, path='/player/assets')`.

the canvas needs the shared `explorer` background and ASCII glyphs. parent-owned
header occupies y0-49, footer y218-239. rows start at y66,90,114. optional sprites
`wave_square`, `wave_triangle`, `wave_sample` draw at (32,144); `envelope` at
(238,144). suggested limits are 128x40 and 96x40. those pictures illustrate
waveform/envelope shape, not a measured live oscilloscope. fields redraw only on
control changes. missing optional pictures do not prevent audio/control use.

## controls

- B1/B2: decrease/increase the selected value and audition it.
- short B3: next field, applied on release; holds >=900ms do not change fields.
- B1+B2: replay. expected mapped button bit is16, not raw mask3.
- hold B3: library navigation stays with the parent application.

wave choices are square, triangle and PDA sample. synth mode has eight pitches
and four decay lengths. PDA mode changes row2 to the three sample choices, skips
the non-editable format row, and replaces synth output with exact cached PCM.
the single persistent Lua Runtime contains two synths but stops both before
starting one. button bits encode wave/pitch/decay; crank-delta +1 auditions,
-1 stops, 0 leaves the envelope running. this is an internal protocol, not an
advertisement of a physical crank.

## genuine PDA input, offline normalization

`pda.py` implements the documented PCM8/PCM16 mono/stereo layouts from
[Cranksters' PDA notes](https://github.com/cranksters/playdate-reverse-engineering/blob/e7be3ff0141b7cd3b9f008737eda1f0539aca45c/formats/pda.md).
those are unofficial reverse-engineering notes, not a compatibility warranty.
the format documentation is CC0; this implementation is original MIT code.

`build_samples.py` synthesizes original sounds off-device, encodes real `.pda`
files, then decodes/normalizes them into the deployed `.pcm`. each `.pda` and
matching `.pcm` is included under `assets/`, along with hashes, peak amplitudes,
and 32 integer envelope bands in `samples.json`. no canned third-party recording
is included. rebuild with `python3 build_samples.py`.

the decoder bounds input to1MiB and decoded output to320,000 mono frames,
accepts rates8-96kHz, checks whole interleaved frames, and rejects empty/truncated
or unknown encodings before normalization. stereo uses integer averaging and
rate conversion uses integer linear interpolation. this is not a mastering-grade
anti-alias filter; provided sounds already use32kHz and need no resampling.

IMA ADPCM format4/5 is explicitly rejected. the consulted notes did not fully
resolve mono nibble/predictor convention for this implementation, and no separate
SDK-produced reference fixture was verified. do not call this an all-PDA decoder.

## verification

run `python3 -m unittest -v test_sound.py`: 14 host tests, including all four PCM
encodings, exact stereo/resampling vectors, malformed/rate/duration bounds,
ADPCM rejection, all original PDA-to-PCM roundtrips, control behavior, held-B3
behavior, cached sample/tail conservation, no playback-time file opens, and
no Python sample loop in the audio method. Canvas/native copying are explicit
fixtures in these tests.

`real_runtime.py` runs under the existing CircuitPython UNIX crankjam build.
all64 synth configurations produced nonzero PCM; stop produced exact zero;
sample output matched the original bytes, and returning to synth worked.
measured synth peak2225 (PCM16 units) in that build. raw heap stats:
`[20341,20763,32768,66392]`. Canvas and native copying remain fixtures in this
specific test, not claims of device compositor/copy validation.

no physical audio, display, buttons, latency, or long-run device qualification
was performed by this lane. no official SDK/pdc roundtrip or Playdate hardware
comparison was performed. parent owns integration and hardware verification.
