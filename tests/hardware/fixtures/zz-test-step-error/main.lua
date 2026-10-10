local voice=playdate.sound.synth.new(playdate.sound.kWaveTriangle)
voice:playNote(440,0.2,2)
local frames=0
function playdate.update()
    frames=frames+1
    if frames==12 then error("deliberate-fixture step error during active audio") end
end
