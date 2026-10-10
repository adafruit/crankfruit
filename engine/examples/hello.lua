-- SPDX-License-Identifier: MIT
-- Original bounded developer sample for the included source-Lua subset.
local p=playdate
local g=p.graphics
p.display.setRefreshRate(30)
local tone=p.sound.synth.new(p.sound.kWaveSquare)
tone:setVolume(0.25)
tone:setADSR(0.005,0.02,0.4,0.04)
local started=false
function p.update()
    local t=p.getCurrentTimeMilliseconds()
    g.clear(g.kColorWhite)
    g.setColor(g.kColorBlack)
    g.drawText("IMPOSSIBLE PLAYDATE: HELLO",20,20)
    g.drawRect(10,10,380,220)
    g.fillRect(20+math.floor(t/10)%330,110,24,24)
    if not started then tone:playNote(440,0.7,0.2);started=true end
end
