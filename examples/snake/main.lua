-- Simple Snake: Crankfruit source adaptation, not the original PDX.
-- Derived from gitlab.com/mocchimochi/playdate/playdate-snake-game,
-- c9cc2a924dcbe31156529ae37326940360865530 (v1.3.4): main.lua + snake.lua.
-- Copyright (c) 2022 Mocchi Mochi (TauchMe). MIT; see accompanying LICENSE.
-- Adaptation changes (MIT):
--  * snake.lua inlined; CoreLibs/saveddata/music imports removed.
--  * Playdate-only "+=" / "-=" operators rewritten as standard Lua 5.4.
--  * eat.wav sampleplayer replaced by a synth blip; background music
--    (third-party, not included) and system-menu Music/Inverted items removed.
--  * datastore highscore kept in memory only (resets when leaving the game).
--  * round rects drawn as plain rects; getTextSize uses the 6px built-in font;
--    *bold* markup removed; FillWhite image draw mode emulated with white text.
--  * added (not upstream): relative crank steering, see crankPressed().
local pd <const> = playdate
local gfx <const> = playdate.graphics
pd.display.setRefreshRate(30)

local eatSound <const> = pd.sound.synth.new(pd.sound.kWaveSquare)
eatSound:setVolume(0.2)
eatSound:setADSR(0.002, 0.04, 0, 0.03)

local function textWidth(text)
	return #text * 6 - 1
end

-- snake.lua
Snake = {}

function Snake:new()

	local pos = {
		x = 0,
		y = 0
	}
	local tail = {} -- The snake body coords

	function self:reset()
		pos['x'] = 0
		pos['y'] = 0
		tail = {}
	end

	function self:getX()
		return pos['x']
	end

	function self:getY()
		return pos['y']
	end

	function self:getTailLength()
		return #tail
	end

	function self:move(lastDirection)
		if (lastDirection == 'right') then
			pos['x'] = pos['x'] + 10
		elseif (lastDirection == 'left') then
			pos['x'] = pos['x'] - 10
		elseif (lastDirection == 'up') then
			pos['y'] = pos['y'] - 10
		elseif (lastDirection == 'down') then
			pos['y'] = pos['y'] + 10
		end
	end

	function self:OutOfScreen()
		if pos['x'] < 0 or pos['x'] >= 400 or pos['y'] < 0 or pos['y'] >= 240 then
			return true
		end

		return false
	end

	function self:eatenItself()
		for i = 1, #tail do
			if pos['x'] == tail[i][1] and pos['y'] == tail[i][2] then
				return true
			end
		end

		return false
	end

	function self:displayTail(gfx)
		for i = 1, #tail do
			if i == #tail then
				tail[#tail + 1 - i][1] = pos['x']
				tail[#tail + 1 - i][2] = pos['y']
			else
				tail[#tail + 1 - i][1] = tail[#tail - i][1]
				tail[#tail + 1 - i][2] = tail[#tail - i][2]
			end
		end
		for i = 1, #tail do
			gfx.fillRect(tail[i][1], tail[i][2], 10, 10)
		end
	end

	function self:pointEaten(point, initState)
		if pos['x'] == point[1] and pos['y'] == point[2] or point[1] == nil then
			point[1] = math.random(39) * 10
			point[2] = math.random(23) * 10

			table.insert(tail, { pos['x'], pos['y'] })

			if initState == false then
				return true
			else
				return false
			end
		end
	end

	return self
end

-- main.lua
local snake <const> = Snake:new()

local lastDirection = 'right'
local point = {}
local score = 0
local highscore = 0
local gameRunning = true
local initState = true
local frameCountVelocity = 0
local movementBlocked = false -- This prevents snake eating itself when fast turning
local difficulty = 4 -- from 4(low) to 1(high)

-- Crankfruit addition: relative crank steering. One 3.6-degree click (one
-- detent of a 100-pulse handwheel; larger clicks, e.g. a 20-count encoder's 18,
-- also give exactly one turn) turns right (clockwise) or left; at most one turn
-- per snake step, with one early click buffered.
local CRANK_STEP <const> = 3.6
local crankTurn = 0
local turnRight <const> = { right = 'down', down = 'left', left = 'up', up = 'right' }
local turnLeft <const> = { right = 'up', up = 'left', left = 'down', down = 'right' }

function crankPressed()
	local change = pd.getCrankChange() -- read every frame so it never goes stale
	if gameRunning == false then
		crankTurn = 0
		return
	end
	crankTurn = math.max(-CRANK_STEP, math.min(CRANK_STEP, crankTurn + change))
	if movementBlocked == false and math.abs(crankTurn) >= CRANK_STEP - 0.001 then
		lastDirection = (crankTurn > 0 and turnRight or turnLeft)[lastDirection]
		movementBlocked = true
		crankTurn = 0
	end
end

function buttonPressed()
	if (pd.buttonIsPressed(pd.kButtonRight) and lastDirection ~= 'left' and movementBlocked == false) then
		lastDirection = 'right'
		movementBlocked = true
	end

	if (pd.buttonIsPressed(pd.kButtonLeft) and lastDirection ~= 'right' and movementBlocked == false) then
		lastDirection = 'left'
		movementBlocked = true
	end

	if (pd.buttonIsPressed(pd.kButtonUp) and lastDirection ~= 'down' and movementBlocked == false) then
		lastDirection = 'up'
		movementBlocked = true
	end

	if (pd.buttonIsPressed(pd.kButtonDown) and lastDirection ~= 'up' and movementBlocked == false) then
		lastDirection = 'down'
		movementBlocked = true
	end
end

function restart()
	snake:reset()
	lastDirection = 'right'
	point = {}
	score = 0
	difficulty = 4
	initState = true
	gameRunning = true
end

function gameOver()
	gameRunning = false

	if score > highscore then
		highscore = score
	end

	gfx.setColor(gfx.kColorWhite)
	gfx.fillRect(75, 50, 250, 140)

	gfx.setColor(gfx.kColorBlack)
	gfx.drawRect(75, 50, 250, 140)
	gfx.fillRect(80, 55, 240, 130)

	gfx.setColor(gfx.kColorWhite)
	gfx.drawText('GAME OVER', 400 / 2 - textWidth('GAME OVER') / 2, 70)

	gfx.drawText('Score:', 140, 100)
	gfx.drawText(tostring(score), 260 - textWidth(tostring(score)), 100)

	gfx.drawText('Highscore:', 140, 120)
	gfx.drawText(tostring(highscore), 260 - textWidth(tostring(highscore)), 120)

	gfx.drawText('Press A to restart', 400 / 2 - textWidth('Press A to restart') / 2, 155)
	gfx.setColor(gfx.kColorBlack)

	if pd.buttonIsPressed(pd.kButtonA) then restart() end

end

function moveSnake()
	snake:move(lastDirection)
end

function printOnScreen()
	gfx.clear()
	gfx.fillRect(snake:getX(), snake:getY(), 10, 10) -- This is the snake's head
	gfx.fillRect(point[1], point[2], 10, 10) -- This is the point the snake has to eat

	snake:displayTail(gfx) -- This is the snake's body
end

function pd.update()
	buttonPressed()
	crankPressed()

	if (gameRunning == true) then
		if (frameCountVelocity == difficulty) then
			moveSnake()

			if (snake:OutOfScreen() == true or snake:eatenItself() == true) then
				gameOver()
			end

			if (snake:pointEaten(point, initState) == true) then
				eatSound:playNote(880, 0.8, 0.06)
				score = score + 1
				if (difficulty > 1 and snake:getTailLength() % 5 == 0) then
					difficulty = difficulty - 1
				end
			else
				initState = false
			end

			printOnScreen()
			movementBlocked = false
			frameCountVelocity = 0
		else
			frameCountVelocity = frameCountVelocity + 1
		end
	else
		gameOver()
	end
end
