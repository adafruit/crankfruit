-- Almost Tennis: Crankfruit source adaptation, not the original PDX.
-- Derived from SquidGodDev/almost-tennis, 69172662a659849c8b452e257c1f41f8cd240ad8.
-- Copyright (c) 2025 SquidGod. MIT; see accompanying LICENSE.
-- Adaptation/pixel primitives/synth audio: Copyright (c) 2026 PT and ints. MIT.
-- Crankfruit 2026-10: crank swing restored from upstream player.lua ("med" sense).
local pd,g=playdate,playdate.graphics
local CRANK_SENSE=10 -- upstream default "med"; degrees per frame to swing
pd.display.setRefreshRate(30)
local hit=pd.sound.synth.new(pd.sound.kWaveSquare)
local low=pd.sound.synth.new(pd.sound.kWaveTriangle)
-- Triangle avoids double-precision sin() per sample on the Cortex-M33.
local tune=pd.sound.synth.new(pd.sound.kWaveTriangle)
hit:setVolume(.18); low:setVolume(.22); tune:setVolume(.17)
hit:setADSR(.002,.035,.25,.03); low:setADSR(.004,.04,.3,.07)
tune:setADSR(.004,.04,.6,.07)
-- Upstream enemyList.lua gameplay values, with image paths removed.
local roster={{4,2,4,0},{3,2.5,5,0},{4,3,5,1},{5,3,6,0},
 {6,3,6,1},{7,3.5,7,0},{8,3.5,7,1},{9,3.5,6.5,1},{8,3,7,2},{8,4,7.5,1}}
local names={"BUBBLE BOY","ROOMMATE","MILK","TRASH HEAD","TALL HAT TIM",
 "CAR SALESMAN","MR WORLDWIDE","PROFESSOR","MARK Z.","KING BOB"}
local level,hp,ehp,charge=1,10,4,0
local px,pv,ex,ev=200,0,200,0
local bx,by,vx,vy=200,170,0,0
local swing,enemySwing,hitWindow,dash=0,0,0,false
local mode,paused,serve,clock="title",false,30,0
local direction,seed,lastMs=1,17,nil
local lastDrawSlot=-1
local points,hits,flash=0,0,0
local function clamp(x,a,b) return math.max(a,math.min(x,b)) end
local function random(a,b)
 seed=(seed*48271)%2147483647
 return a+seed%(b-a+1)
end
-- The same acceleration/friction and direction-reversal policy as Player/Enemy.
local function moveVelocity(v,d,max)
 if d<0 then if v>=0 then return -1 end; return math.max(-max,v-.3)
 elseif d>0 then if v<=0 then return 1 end; return math.min(max,v+.3)
 elseif math.abs(v)<=.3 then return 0
 elseif v<0 then return v+.3 else return v-.3 end
end
local function resetBall(enemySide)
 bx=random(82,317); by=enemySide and 60 or 180; vx=0; vy=0; serve=30
 swing=0; enemySwing=0; hitWindow=0
 tune:playNote(enemySide and 392 or 523.25,.7,.10)
end
local function begin()
 level,hp,ehp,charge=1,10,roster[1][1],0
 px,pv,ex,ev=200,0,200,0; points,hits=0,0
 mode,paused,dash="play",false,false
 resetBall(false)
end
-- Ball:hit normalized-vector rule, preserving enemy/player shot direction.
local function strike(x,y,enemy,speed)
 local dx,dy=bx-x,by-y
 local length=math.sqrt(dx*dx+dy*dy)
 if length<.001 then dx=0; length=1 end
 local cosine=clamp(dx/length,-1,1)
 vx=cosine*speed
 vy=math.sqrt(math.max(0,1-cosine*cosine))*speed*(enemy and 1 or -1)
 if math.abs(vy)<.5 then vy=enemy and .5 or -.5 end
 hit:playNote(enemy and 330 or 660,.85,.055)
 flash=4; hits=hits+1
 if not enemy then charge=math.min(50,charge+10) end
end
local function scored(playerScored)
 points=points+1; flash=12
 low:playNote(playerScored and 196 or 73.42,.85,.24)
 if playerScored then
  ehp=ehp-1
  if ehp<=0 then
   level=level+1; hp=math.min(10,hp+2)
   if level>10 then mode="won"; return end
   ehp=roster[level][1]; mode="next"; return
  end
 else hp=hp-1; if hp<=0 then mode="over"; return end end
 resetBall(playerScored)
end
local function tick(d,pressA,pressB,auto)
 if swing>0 then swing=swing-1 end
 if enemySwing>0 then enemySwing=enemySwing-1 end
 if hitWindow>0 then hitWindow=hitWindow-1 end
 if flash>0 then flash=flash-1 end
 if d~=0 then direction=d end
 if pressB and charge>=50 then
  charge=0; pv=direction*10; dash=true; low:playNote(150,.7,.08)
 end
 if dash then
  pv=pv+(pv<0 and .7 or -.7)
  if math.abs(pv)<.7 then pv=0; dash=false end
 else pv=moveVelocity(pv,d,3) end
 px=clamp(px+pv,72,327)
 local ed=bx<ex-2 and -1 or (bx>ex+2 and 1 or 0)
 ev=moveVelocity(ev,ed,roster[level][2]); ex=clamp(ex+ev,72,327)
 if serve>0 then serve=serve-1; return end
 -- 24-frame racket recovery, 100ms collision window. Original animated
 -- sprite hitboxes are replaced with explicit bounds at the same court scale.
 if pressA and swing==0 then swing=24; hitWindow=3; hit:playNote(220,.3,.04) end
 if hitWindow>0 and math.abs(bx-px)<=64 and by>=153 and by<=216 and vy>=0 then
  strike(px,220,false,7); hitWindow=0
 end
 if enemySwing==0 and math.abs(bx-ex)<=65 and math.abs(by-20)<=60 and vy<=0 then
  enemySwing=24; local e=roster[level]
  strike(ex,20,true,e[3]+random(-e[4],e[4]))
 end
 bx=bx+vx; by=by+vy
 if bx<66 then bx=132-bx; vx=math.abs(vx); hit:playNote(440,.35,.025) end
 if bx>334 then bx=668-bx; vx=-math.abs(vx); hit:playNote(440,.35,.025) end
 if by<=0 then scored(true) elseif by>=240 then scored(false) end
end
local function person(x,y,enemy,s)
 x=math.floor(x)
 g.fillCircleAtPoint(x,y-7,5)
 g.fillRect(x-6,y-1,13,10)
 g.drawLine(x-4,y+9,x-7,y+14); g.drawLine(x+4,y+9,x+7,y+14)
 local side=enemy and -1 or 1
 local rx=x+(s>18 and -24 or 18); local ry=y+(enemy and 17 or -13)
 g.drawLine(x+side*5,y+2,rx,ry); g.drawCircleAtPoint(rx,ry,8)
 g.drawLine(rx-5,ry,rx+5,ry); g.drawLine(rx,ry-5,rx,ry+5)
 if enemy then
  if level==5 then g.fillRect(x-5,y-27,10,14); g.drawLine(x-9,y-13,x+9,y-13)
  elseif level==10 then g.drawRect(x-8,y-17,17,6); g.drawLine(x-8,y-17,x-8,y-21); g.drawLine(x,y-17,x,y-23); g.drawLine(x+8,y-17,x+8,y-21)
  elseif level==3 then g.drawRect(x-8,y-14,17,20)
  else g.drawLine(x-7,y-11,x+7,y-11) end
 end
end
local function panel(a,b,c)
 g.setColor(g.kColorWhite); g.fillRect(72,73,256,92)
 g.setColor(g.kColorBlack); g.drawRect(72,73,256,92); g.drawRect(75,76,250,86)
 g.drawText(a,200-#a*3,89); g.drawText(b,200-#b*3,111)
 g.drawText(c,200-#c*3,143)
end
local function draw()
 g.clear(g.kColorWhite); g.setColor(g.kColorBlack)
 g.fillRect(56,0,6,240); g.fillRect(338,0,6,240)
 g.drawRect(70,8,260,224)
 for x=72,330,12 do g.drawLine(x,120,x+6,120) end
 for y=9,232,8 do g.drawLine(58,y,60,y+4); g.drawLine(340,y,342,y+4) end
 g.drawText("YOU",5,178); g.drawText(tostring(hp),17,190)
 g.drawText("RIVAL",351,20); g.drawText(tostring(ehp),369,32)
 g.drawText("ROUND",351,86); g.drawText(tostring(math.min(level,10)),369,98)
 g.drawText("DASH",4,130); g.drawRect(13,143,25,8); g.fillRect(15,145,math.floor(charge*21/50),4)
 person(px,218,false,swing); person(ex,23,true,enemySwing)
 if serve==0 or serve%10<5 then
  if flash>0 then g.drawCircleAtPoint(math.floor(bx),math.floor(by),7+flash) end
  g.fillCircleAtPoint(math.floor(bx),math.floor(by),4)
 end
 if mode=="title" then
  panel("ALMOST TENNIS","SQUIDGOD / SOURCE ADAPTATION","B3: PLAY THE GAUNTLET")
  g.drawText("B1/B2 MOVE  B3 SWING",128,181)
  g.drawText("B1+B2 DASH WHEN CHARGED",116,192)
  g.drawText("HOLD B3: GAME LIBRARY",140,204)
 elseif mode=="next" then panel("ROUND WON",names[level],"B3: NEXT OPPONENT")
 elseif mode=="over" then panel("MATCH OVER","THE BALL HAD OTHER PLANS","B3: TRY AGAIN")
 elseif mode=="won" then panel("ALMOST TENNIS CHAMPION","TEN RIVALS. ONE FRUIT.","B3: PLAY AGAIN")
 elseif paused then panel("PAUSED","ALMOST TENNIS","B3: RESUME") end
end
function pd.update()
 local now=pd.getCurrentTimeMilliseconds(); clock=clock+1
 local a=pd.buttonJustPressed(pd.kButtonA)
 local b=pd.buttonJustPressed(pd.kButtonB)
 -- Upstream player.lua: a crank flick of CRANK_SENSE degrees also swings.
 -- Read every frame so movement outside play cannot swing later.
 local _,crankChange=pd.getCrankChange()
 local crankSwing=math.abs(crankChange)>=CRANK_SENSE
 local swung=false
 if mode=="title" then
  bx=200+math.sin(now/600)*80; by=120+math.cos(now/410)*40
  ex=bx; px=200+math.sin(now/750)*80
  if clock==1 then tune:playNote(523.25,.8,.15) end
  if clock==7 then tune:playNote(659.25,.8,.15) end
  if clock==13 then tune:playNote(783.99,.8,.25) end
  if a then begin() end
 elseif mode=="over" or mode=="won" then if a then begin() end
 elseif mode=="next" then if a then mode="play"; resetBall(true) end
 else
  local d=0
  if pd.buttonIsPressed(pd.kButtonLeft) then d=d-1 end
  if pd.buttonIsPressed(pd.kButtonRight) then d=d+1 end
  local before=swing
  tick(d,a or crankSwing,b,false)
  swung=swing>before -- a swing actually started
 end
 -- Physics and sound remain30Hz. Redraw at20Hz to leave physical HDMI/audio
 -- service headroom, with immediate A/B edge feedback on swings/navigation.
 local drawSlot=math.floor(now/50)
 if drawSlot~=lastDrawSlot or a or b or swung then draw(); lastDrawSlot=drawSlot end
 lastMs=now
end
