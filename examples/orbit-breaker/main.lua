-- Orbit Breaker: original compatible-source sample, not an imported PDX.
-- Copyright (c) 2026 Crankfruit contributors. SPDX-License-Identifier: MIT
local pd,g=playdate,playdate.graphics
pd.display.setRefreshRate(30)
local tone=pd.sound.synth.new(pd.sound.kWaveSquare)
local cue=pd.sound.synth.new(pd.sound.kWaveTriangle)
tone:setVolume(.18);tone:setADSR(.002,.018,.25,.025)
cue:setVolume(.20);cue:setADSR(.004,.03,.3,.07)
local mode,paused,best="title",false,0
local autoplay=false
local score,lives,remaining,hits=0,3,16,0
local paddle,bx,by,vx,vy=200,200,194,52,-104
local serve,clock,overClock,lastMs=0,0,0,nil
local bricks={true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true}
local dirty,lastDraw,oldX,oldY,oldPaddle=true,-1,200,194,200
local hudScore,hudLives,hudBest=-1,-1,-1
local function clamp(n,lo,hi) return math.max(lo,math.min(hi,n)) end
local function resetBall()
 bx=paddle;by=194;vx=52;vy=-104;serve=.75
end
local function begin(nextMode)
 mode,paused,score,lives,remaining,hits=nextMode,false,0,3,16,0
 autoplay=nextMode=="demo"
 paddle,clock,overClock=200,0,0
 for i=1,16 do bricks[i]=true end
 resetBall();dirty=true
 tone:stop();cue:stop();cue:playNote(523.25,.7,.15)
end
local function brickPosition(i)
 return 64+((i-1)%4)*70,53+math.floor((i-1)/4)*14
end
local function advance(dt,left,right,delta,auto)
 clock=clock+dt
 local movement=(right and 200*dt or 0)-(left and 200*dt or 0)+delta*(344/360)
 if auto then movement=clamp(bx-paddle,-240*dt,240*dt) end
 paddle=clamp(paddle+movement,34,366)
 if serve>0 then
  serve=math.max(0,serve-dt);bx=paddle;by=194;return
 end
 local ox,oy=bx,by
 bx=bx+vx*dt;by=by+vy*dt
 if bx<13 then bx=13;vx=math.abs(vx)
 elseif bx>387 then bx=387;vx=-math.abs(vx) end
 if by<37 then by=37;vy=math.abs(vy) end
 for i=1,16 do
  if bricks[i] then
   local x,y=brickPosition(i)
   if bx+3>=x and bx-3<=x+61 and by+3>=y and by-3<=y+9 then
    bricks[i]=false;remaining=remaining-1;score=score+25;best=math.max(best,score)
    if oy+3<y or oy-3>y+9 then vy=-vy else vx=-vx end
    bx=ox;by=oy;dirty=true
    tone:playNote(440+(i%4)*110,.65,.065)
    if remaining==0 then
     mode="won";overClock=0;cue:playNote(783.99,.75,.3)
    end
    break
   end
  end
 end
 if vy>0 and oy<199 and by>=199 and math.abs(bx-paddle)<=27 then
  by=199;hits=hits+1
  vx=clamp((bx-paddle)*5,-120,120)
  if math.abs(vx)<20 then vx=vx<0 and -20 or 20 end
  vy=-math.min(142,104+hits*2)
  tone:playNote(330,.5,.04)
 elseif by>222 then
  lives=lives-1;cue:playNote(110,.8,.2)
  if lives<=0 then mode="over";overClock=0;dirty=true
  else resetBall() end
 end
end
local function hud()
 if score==hudScore and lives==hudLives and best==hudBest then return end
 g.setColor(g.kColorBlack);g.fillRect(0,0,400,28)
 g.setColor(g.kColorWhite)
 g.drawText("ORBIT BREAKER",12,5);g.drawText("SECTOR 01 / CLEAR THE ARRAY",12,17)
 g.drawText("SCORE "..score,184,5);g.drawText("BEST "..best,184,17)
 g.drawText("SHIPS "..lives,321,11)
 g.setColor(g.kColorBlack)
 hudScore,hudLives,hudBest=score,lives,best
end
local function background()
 g.clear(g.kColorWhite);g.setColor(g.kColorBlack)
 g.drawRect(8,33,384,191)
 -- Twin rails and isolated corner ticks leave the ball path uncluttered.
 g.fillRect(12,218,60,2);g.fillRect(328,218,60,2)
 for i=1,16 do
  if bricks[i] then
   local x,y=brickPosition(i)
   g.fillRect(x,y,62,10);g.setColor(g.kColorWhite)
   g.fillRect(x+3,y+2,56,1);g.setColor(g.kColorBlack)
  end
 end
 g.drawText("B1/B2 MOVE  B3 START  B1+B2 PAUSE  HOLD B3 EXIT",65,230)
 if autoplay then g.drawText("AUTO PILOT / B3: TAKE CONTROL",122,39) end
 hudScore=-1;hud()
 dirty=false
end
local function title()
 if not dirty then return end
 g.clear(g.kColorWhite);g.setColor(g.kColorBlack)
 g.drawRect(12,12,376,211);g.drawRect(18,18,364,199)
 g.fillRect(42,48,316,44);g.setColor(g.kColorWhite)
 g.drawText("O R B I T   B R E A K E R",130,65)
 g.setColor(g.kColorBlack)
 g.drawText("16 SATELLITES. ONE SHIP. NO SIGNAL LOST.",92,107)
 for i=0,7 do g.fillRect(104+i*25,132,17,7) end
 g.fillRect(198,157,5,5);g.fillRect(172,178,56,5)
 g.drawText("B3: LAUNCH / B1+B2: PAUSE",122,198)
 g.drawText("HOLD B3: EXIT",163,229)
 dirty=false
end
local function draw()
 if mode=="title" then title();return end
 if dirty then background()
 else
  -- The moving footprints never touch intact bricks; restore only those pixels.
  g.setColor(g.kColorWhite);g.fillRect(oldX-3,oldY-3,7,7)
  g.fillRect(oldPaddle-26,201,53,8);g.setColor(g.kColorBlack)
 end
 g.fillRect(12,218,60,2);g.fillRect(328,218,60,2)
 if autoplay then g.drawText("AUTO PILOT / B3: TAKE CONTROL",122,39) end
 hud()
 local x,y,p=math.floor(bx),math.floor(by),math.floor(paddle)
 g.fillRect(p-25,203,51,5);g.fillRect(p-21,201,43,2)
 g.fillRect(x-2,y-2,5,5)
 oldX,oldY,oldPaddle=x,y,p
 if mode=="won" or mode=="over" then
  g.setColor(g.kColorWhite);g.fillRect(83,116,234,66)
  g.setColor(g.kColorBlack);g.drawRect(83,116,234,66)
  g.drawText(mode=="won" and "ARRAY CLEARED" or "SIGNAL LOST",164,129)
  g.drawText("SCORE "..score.." / BEST "..best,140,147)
  g.drawText("B3: LAUNCH AGAIN",155,167)
 end
 if paused then
  g.setColor(g.kColorWhite);g.fillRect(130,121,140,32)
  g.setColor(g.kColorBlack);g.drawRect(130,121,140,32)
  g.drawText("ORBIT ON HOLD",164,134)
 end
end
function pd.update()
 local now=pd.getCurrentTimeMilliseconds()
 local dt=lastMs and clamp((now-lastMs)/1000,0,.05) or 1/30
 lastMs=now
 if pd.buttonJustPressed(pd.kButtonA) then begin("play") end
 if pd.buttonJustPressed(pd.kButtonB) and (mode=="play" or mode=="demo") then
  paused=not paused;dirty=true
  if paused then tone:stop();cue:stop() end
 end
 if not paused then
  if mode=="title" then clock=clock+dt;if clock>=3 then begin("demo") end
  elseif mode=="play" or mode=="demo" then
   advance(dt,pd.buttonIsPressed(pd.kButtonLeft),pd.buttonIsPressed(pd.kButtonRight),pd.getCrankChange(),mode=="demo")
   if mode=="demo" and clock>=24 then mode="title";clock=0;dirty=true end
  else
   overClock=overClock+dt
   if autoplay and overClock>2.4 then mode="title";clock=0;dirty=true end
  end
 end
 local slot=math.floor(now/50)
 if slot~=lastDraw then lastDraw=slot;draw() end
end
