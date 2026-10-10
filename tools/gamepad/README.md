# optional USB gamepad input

`GamepadInput(config=None)` is disabled by default. disabled construction and
polls do not import `usb`, open files or touch the USB host port. `poll(now_ms)`
returns player button bits; `close()` is idempotent. all source is MIT.

supported: a wired Sony DualShock 4 (USB `054c:05c4` or `054c:09cc`) on the Fruit
Jam USB-A host port. other controllers, Bluetooth and XInput pads are not supported.

## mapping

| DualShock 4 | player bit | Fruit Jam equivalent |
| --- | --- | --- |
| d-pad / left stick | left, right, up, down | B1 / B2 (left/right only) |
| cross | A | B3 |
| circle | B | B1+B2 |
| options | return to library immediately | hold B3 1.2s |

square, triangle, shoulders, share, PS and touchpad are unused. onboard buttons
keep working and are OR-ed with the pad. up/down reach Lua games; the library and
Sound Explorer ignore them. the return-to-library bit (64) is consumed by the
player and masked before any cartridge or built-in scene sees the buttons.

## install

copy `gamepad-config.json` to the board as `/gamepad.json` and restart. a missing
file selects disabled mode; malformed JSON or invalid settings stop startup
visibly. optional settings: `poll_ms` 8..100 (default 25), `read_timeout_ms` 2..5
(default 2), `stick` true/false (default true), `stick_deadzone` 16..120 (default 64).

## timing

the pad sends a 64-byte report every 5ms. a USB read waits for the next report,
so `poll()` touches USB at most once per `poll_ms` and holds the last state between
reads. measured on the Fruit Jam on 2026-10-09 with reads spaced at least 8ms apart:
2ms timeout, 60/60 reads delivered, 0.94ms average, 0.98ms worst. a 1ms timeout
missed most reports. device discovery costs about 0.27ms and is retried once per
second while no pad is attached. unplugging releases all pad buttons.

on-board module run (2026-10-09, REPL, player stopped): 60,849 polls over ~60s;
all mapped controls decoded correctly. unplugging raised `usb.core.USBError`, the
pad was dropped and reconnected automatically after replug. the connect step
(`set_configuration`) took 8.5-8.7ms, once at startup and once per replug; every
other poll stayed under 3ms. replugging during a game may therefore cost one long
frame.

## verification

`python3 -m unittest discover -s tools/gamepad -v` runs host tests with a fake
`usb.core`: report decoding (including bytes captured from the board), config
validation, rate limiting, timeouts, unplug/reconnect, and the player merge/mask.
on-board button capture covered every DS4 control. in-game timing impact must be
measured on the board with the player's own metrics.
