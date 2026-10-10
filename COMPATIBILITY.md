# compatibility, without the shorthand

| input or feature | this release |
| --- | --- |
| compatible flat `main.lua` + manifest | discovered and executed by real C/Lua runtime |
| another independent source game | works without launcher code changes; Orbit Breaker demonstrates it |
| original Almost Tennis repository | adapted source port, not unchanged SDK compatibility |
| Playdate `.pdx` / `.pdz` / modified `.luac` | rejected; no bytecode/container runtime implemented |
| Playdate native ARM executable | not supported |
| SDK imports, CoreLibs, classes, sprites, timers | not implemented in source profile v1 |
| primitive graphics, input/time and synth subset | implemented; exact methods in engine source |
| PDI images / PDT tables | offline codec and masked native atlas used by player artwork |
| PDI/PDT loading from game Lua | not exposed as a Playdate image API yet |
| PDA PCM8/16 mono/stereo | offline decoder; cached normalized samples demonstrated in Sound Explorer |
| PDA ADPCM or arbitrary Lua sample-player calls | not implemented |
| hardware crank | disabled-by-default seesaw/analog adapters; logic tested, physical hardware pending |
| Cranksters `pd-usb` | designed for an actual Playdate; not presented as a Fruit Jam driver |

the useful result is a small, inspectable, standalone source-game console and
development path. it is not a renamed desktop emulator or a video recording
pretending to be gameplay. only the finite startup is pre-rendered; both source
games execute locally. authoring tools work offline once dependencies are installed.

the next compatibility milestones would be a measured image/sprite API and a
carefully scoped SDK-source adaptation layer. PDZ parsing and modified bytecode
execution would be separate projects requiring format and VM validation, not a
filename-extension switch. commercial/catalog compatibility is not promised.
