"""Dynamic source-cartridge library. Never executes a cartridge while scanning."""
from canvas import Canvas

SOUND = b'''local p=playdate
local s=p.sound.synth.new(p.sound.kWaveSquare)
s:setVolume(0.16)
s:setADSR(0.002,0.035,0,0.015)
function p.update()
 if p.buttonJustPressed(p.kButtonA) then s:playNote(660,0.6,0.05) end
end'''
CRANK_STEP = 18.0  # degrees per highlight move: one click of a 20-count encoder
CRANK_MAX_MOVES = 3  # per frame, so a fast spin cannot race through the list


class Library:
    def __init__(self, runtime_class, items, selected=0, message='', path='/player/assets'):
        self.canvas = Canvas(path)
        self.sound = runtime_class(SOUND, heap_cap=32768)
        self.items = items
        self.selected = min(max(0, selected), len(items)-1)
        self.previous = 0
        self.crank = 0.0  # accumulated crank degrees not yet turned into moves
        self.crank_step = CRANK_STEP  # replaced by the crank's step_degrees
        self.action = None
        self.message = message[:60]
        self.dirty = True
        self.phase = -1
        # Prepare all bounded library pages before audio starts. Glyph command
        # construction must not contend with live mixing and HDMI service.
        original=self.selected
        self.phase=0
        pages=[]
        for index in range(len(items)):
            self.selected=index
            self.message=items[index]['reason'][:60] if not items[index]['enabled'] else ''
            self.draw()
            packed=bytearray(12000)
            frame=self.canvas.framebuffer
            for row in range(240): packed[row*50:(row+1)*50]=frame[row*52:row*52+50]
            pages.append(bytes(packed))
        self.pages=tuple(pages)
        self.selected=original
        self.message=message[:60]
        self.error_page=None
        if self.message:
            self.draw()
            packed=bytearray(12000)
            frame=self.canvas.framebuffer
            for row in range(240): packed[row*50:(row+1)*50]=frame[row*52:row*52+50]
            self.error_page=bytes(packed)

    def refresh_rate(self): return 30

    def step(self, buttons, angle, delta, elapsed):
        phase = (elapsed//200)%4
        if phase != self.phase:
            self.phase = phase; self.dirty = True
        pressed = buttons & ~self.previous
        self.previous = buttons
        if pressed & 1:
            self.selected = (self.selected-1) % len(self.items)
            self.error_page=None; self.dirty = True
        if pressed & 2:
            self.selected = (self.selected+1) % len(self.items)
            self.error_page=None; self.dirty = True
        # Crank: clockwise highlights the next game, counter-clockwise the previous.
        self.crank += delta
        moved = 0
        step = self.crank_step - 0.001  # single-precision floats: a whole click must count
        while self.crank >= step and moved < CRANK_MAX_MOVES:
            self.crank -= self.crank_step; moved += 1
            self.selected = (self.selected+1) % len(self.items)
        while self.crank <= -step and moved < CRANK_MAX_MOVES:
            self.crank += self.crank_step; moved += 1
            self.selected = (self.selected-1) % len(self.items)
        if moved:
            if moved == CRANK_MAX_MOVES:
                self.crank = 0.0  # drop the rest of a fast spin instead of replaying it
            self.error_page=None; self.dirty = True
            pressed |= 64  # navigation beep below, without being a button
        if pressed & 32:
            item = self.items[self.selected]
            if item['enabled']: self.action = self.selected
            else:
                self.message = item['reason'][:60]; self.dirty = True
        self.sound.step(32 if pressed else 0, 0, 0, elapsed)
        if self.dirty:
            c=self.canvas
            c.backgrounds['_page']=self.error_page or self.pages[self.selected]
            c.begin('_page')
            if 'crank_badapple0' in c.ids: c.sprite('crank_badapple%d'%self.phase,300,8)
            c.render()
            self.dirty = False

    def draw(self):
        c = self.canvas
        c.begin('library')
        first = (self.selected//3)*3
        for row, item in enumerate(self.items[first:first+3]):
            y = 62+46*row
            if first+row == self.selected: c.sprite('selection',18,y)
            c.text(item['title'][:27], 43, y+7, 2)
            desc = item['description'] if item['enabled'] else 'UNSUPPORTED: '+item['reason']
            c.text(desc[:34], 43, y+27)
        c.text('%d/%d'%(self.selected+1,len(self.items)), 350, 43)
        if 'crank_badapple0' in c.ids:
            c.sprite('crank_badapple%d'%self.phase,300,8)
        c.text(self.message[:60] or 'SOURCE LUA PROFILE V1 / HOLD B3 TO RETURN', 18, 205)
        c.render()

    def audio_into(self,target,rate=32000): return self.sound.audio_into(target,rate=rate)
    def copy_framebuffer_into(self,target,stride=52): return self.canvas.copy_framebuffer_into(target,stride=stride)
    def heap_stats(self): return self.sound.heap_stats()
    def close(self):
        self.sound.close(); self.canvas.close()
