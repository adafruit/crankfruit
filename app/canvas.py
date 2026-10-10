"""Small fixed-command sprite canvas. Files load before audio playback.

PDI/PDT are validated/normalized off-device. No decompression or filesystem
access in a frame. The native compositor validates buffers before writing.
"""
import json
import struct
import _crankfruit_sprite

def _read(path,limit):
    with open(path,'rb') as f:data=f.read(limit+1)
    if len(data)>limit:raise ValueError('oversized asset: '+path)
    return data

class Canvas:
    def __init__(self,path='/player/assets'):
        info=json.loads(_read(path+'/manifest.json',65536))
        if info['version']!=1 or info['width']!=400 or info['height']!=240:
            raise ValueError('unsupported canvas manifest')
        self.sprites=info['sprites']
        self.backgrounds={}
        for name,filename in info['backgrounds'].items():
            if '/' in filename or '..' in filename:raise ValueError('invalid asset path')
            data=_read(path+'/'+filename,12000)
            if len(data)!=12000:raise ValueError('invalid background size')
            self.backgrounds[name]=data
        self.atlas=_read(path+'/sprites.bin',262144)
        self.descriptors=_read(path+'/sprites.desc',3072)
        if len(self.descriptors)%12:raise ValueError('bad sprite descriptors')
        self.ids={name:value['id'] for name,value in self.sprites.items()}
        self.labels={text:self.ids[name] for text,name in info.get('labels',{}).items()}
        for value in self.ids.values():
            if not 0<=value<len(self.descriptors)//12:raise ValueError('bad sprite id')
        self.framebuffer=bytearray(12480)
        self.commands=bytearray(256*8)
        view=memoryview(self.commands)
        self.views=tuple(view[:i*8] for i in range(257))
        self.count=0
        self.background=self.backgrounds['game']
        self.frames=0
        self.max_commands=0
        self.glyphs={scale:{chr(c):self.ids['glyph%d_%d'%(scale,c)]
                          for c in range(32,96) if 'glyph%d_%d'%(scale,c) in self.ids}
                     for scale in (1,2)}

    def begin(self,name):
        self.background=self.backgrounds[name]
        self.count=0

    def _sprite_id(self,index,x,y,flags=0):
        if self.count>=256:raise ValueError('sprite command budget exceeded')
        if not -32768<=x<=32767 or not -32768<=y<=32767:
            raise ValueError('sprite coordinate out of bounds')
        struct.pack_into('<HhhH',self.commands,self.count*8,index,int(x),int(y),flags)
        self.count+=1

    def sprite(self,name,x,y,flags=0):
        self._sprite_id(self.ids[name],x,y,flags)

    def text(self,text,x,y,scale=1):
        if scale==1 and text in self.labels:
            self._sprite_id(self.labels[text],x,y)
            return
        font=self.glyphs[scale]
        for c in text:
            if 'a'<=c<='z':c=chr(ord(c)-32)
            self._sprite_id(font.get(c,font['?']),x,y)
            x+=6*scale

    def render(self):
        result=_crankfruit_sprite.compose(self.framebuffer,self.background,self.atlas,
                                         self.descriptors,self.views[self.count])
        if result!=12000:raise RuntimeError('sprite compositor byte count mismatch')
        self.frames+=1
        self.max_commands=max(self.max_commands,self.count)

    def copy_framebuffer_into(self,target,stride=52):
        if stride!=52 or len(target)!=12480:raise ValueError('canvas requires stride52')
        target[:]=self.framebuffer
        return 12000

    def close(self):
        self.backgrounds=self.atlas=self.descriptors=self.views=self.framebuffer=None
