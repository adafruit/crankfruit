"""Portable native-host test. Invoke through verify.py with a crankjam interpreter."""
import sys
import json
import crankjam

with open(sys.argv[1], "rb") as handle:
    source = handle.read()

UNITS = b'''
begin("play")
assert(remaining==16 and lives==3 and score==0 and serve==.75)
for i=1,16 do assert(bricks[i]) end
advance(.05,true,false,0,false);assert(paddle==190)
advance(.05,false,true,0,false);assert(paddle==200)
advance(.05,false,false,1000,false);assert(paddle==366)
advance(.05,false,false,-1000,false);assert(paddle==34)
begin("play");serve=0;bx=12;by=150;vx=-52;vy=-104
advance(.01,false,false,0,false);assert(bx==13 and vx>0)
bx=388;by=150;vx=52;advance(.01,false,false,0,false);assert(bx==387 and vx<0)
bx=200;by=36;vy=-104;advance(.01,false,false,0,false);assert(by==37 and vy>0)
bx=200;by=198;vx=0;vy=104;paddle=200
advance(.02,false,false,0,false);assert(vy<0 and hits==1 and by==199)
bx=360;by=223;vx=0;vy=104;advance(.01,false,false,0,false)
assert(lives==2 and serve==.75 and mode=="play")
serve=0;bx=94;by=49;vx=0;vy=104
advance(.02,false,false,0,false)
assert(not bricks[1] and remaining==15 and score==25 and best==25)
begin("play");serve=0
for i=2,16 do bricks[i]=false end
remaining=1;bx=94;by=49;vx=0;vy=104
advance(.02,false,false,0,false);assert(mode=="won" and remaining==0)
begin("play");lives=1;serve=0;bx=360;by=223;vx=0;vy=104
advance(.01,false,false,0,false);assert(mode=="over" and lives==0)
begin("demo");assert(autoplay and mode=="demo" and best==25)
'''
r = crankjam.Runtime(source + UNITS, heap_cap=65536)
r.close()

INVARIANTS = b'''
local oldUpdate=pd.update
local oldDraw=draw
local drawCount=0
local updateCount=0
local firstTime=nil
draw=function() drawCount=drawCount+1;oldDraw() end
function pd.update()
 oldUpdate()
 updateCount=updateCount+1
 local now=pd.getCurrentTimeMilliseconds()
 if not firstTime then firstTime=now end
 assert(drawCount<=math.floor((now-firstTime)/50)+1,"20Hz drawing quota")
 assert(paddle>=34 and paddle<=366,"paddle bounds")
 assert(lives>=0 and lives<=3,"ship quota")
 assert(remaining>=0 and remaining<=16,"brick quota")
 local count=0
 for i=1,16 do if bricks[i] then count=count+1 end end
 assert(count==remaining,"fixed slots")
 assert(score>=0 and score<=400 and score%25==0,"score invariant")
 assert(best>=score,"record invariant")
end
'''
a = crankjam.Runtime(source + INVARIANTS, heap_cap=65536)
b = crankjam.Runtime(source, heap_cap=65536)
fa, fb, last = bytearray(12000), bytearray(12000), bytearray(12000)
pa, pb = bytearray(2134), bytearray(2134)
different_frames = 0
nonzero_pcm_frames = 0
for frame in range(1800):
    now = frame * 1000 // 30
    buttons = 0
    # Native A/32 launch, directions1/2, B/16 pause. Edges are separated.
    if frame in (600, 900, 1400):
        buttons = 32
    elif frame in (750, 780):
        buttons = 16
    elif 610 <= frame < 640 or 930 <= frame < 960:
        buttons = 1
    elif 650 <= frame < 700 or 1000 <= frame < 1050:
        buttons = 2
    delta = 3.0 if 1100 <= frame < 1120 else 0.0
    a.step(buttons, 0.0, delta, now)
    b.step(buttons, 0.0, delta, now)
    assert a.audio_into(pa, rate=32000) == len(pa)
    assert b.audio_into(pb, rate=32000) == len(pb)
    assert pa == pb, "PCM is not deterministic"
    a.copy_framebuffer_into(fa)
    b.copy_framebuffer_into(fb)
    assert fa == fb, "framebuffer is not deterministic"
    if len(sys.argv) > 2 and frame in (0, 160, 610, 751, 1350):
        with open(sys.argv[2] + "/frame-%d.pbm" % frame, "wb") as image:
            image.write(b"P4\n400 240\n")
            image.write(bytes(value ^ 255 for value in fa))
    if fa != last:
        different_frames += 1
        last[:] = fa
    if any(pa):
        nonzero_pcm_frames += 1
assert different_frames > 300, "expected animated output"
assert nonzero_pcm_frames > 30, "expected synthesized output"
result = {"updates": 1800, "deterministic_framebuffers": 1800,
          "deterministic_pcm_samples": 1920600,
          "changed_frames": different_frames, "nonzero_pcm_frames": nonzero_pcm_frames,
          "units": "passed", "invariants": "passed", "heap": list(a.heap_stats()),
          "physical_hardware_tested": False}
a.close()
b.close()
print(json.dumps(result))
