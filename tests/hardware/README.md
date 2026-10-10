# optional physical qualification scripts

these execute real video/audio and game code on a selected Fruit Jam, not a
desktop. install the reviewed app/custom firmware first. preserve `code.py`
before temporarily replacing it with a test script. close other serial clients,
capture the serial console, reset/reload once, then restore `code.py` and restart.
do not overwrite an unrelated board or discard existing user files.

- `001_player.py`: native helpers, discovery, every mode and hold-to-return.
- `002_endurance.py`: three minutes per mode, about nine minutes overall.
- `003_recovery.py`: copy both `fixtures/zz-test-*` folders into `/games/` first.
  triggers load failure and update failure during sound; checks audio stop,
  library recovery and another real game. retire these exact test folders after.
- `004_showcase.py`: startup, library, games and sound lab with scripted controls.
  designed for repeatable capture of real HDMI output.

success requires PASS lines, zero failed checks, and one final `~~END~~` after
cleanup. missing completion, traceback or failure is not a pass. expected game
rejections in003 are deliberate, but its failed count must be zero. keep raw logs
private if they contain paths/device details. automated controls are injected
button states; separately test physical buttons, standalone power, the chosen
audio/video sink and optional crank hardware.
