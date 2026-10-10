"""Finite on-device qualification; injected controls, not physical button presses."""
passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print('PASS:', name)
    else:
        failed += 1
        print('FAIL:', name)

try:
    import board
    import struct
    import _crankfruit_pcm
    import _crankfruit_blit
    import _crankfruit_sprite
    check('Fruit Jam selected', board.board_id == 'adafruit_fruit_jam')
    dst = bytearray(b'xxxxxx')
    check('clean native PCM helper', _crankfruit_pcm.copy_into(dst,b'abcdef',1,2,3)==3 and dst==b'xcdexx')
    source = bytearray(12480)
    source[0] = 128
    scan = bytearray(38400)
    check('clean native scanout helper', _crankfruit_blit.blit(source,scan)==12000 and sum(scan)==1)
    frame = bytearray(12480)
    result = _crankfruit_sprite.compose(frame,bytes([255])*12000,b'',b'',b'')
    check('clean native masked sprite helper', result==12000 and frame[:50]==bytes([255])*50 and frame[50:52]==b'\0\0')
    del source,scan,frame,dst
    import crankfruit
    games = crankfruit.entries()
    check('independent source games discovered',
          all(any(x['slug']==slug and x['enabled'] for x in games)
              for slug in ('almost-tennis','orbit-breaker','sound-explorer')))
    check('courier absent from player library',not any('courier' in x['slug'] for x in games))
    crankfruit.main(test=True)
    check('library games sound and hold-to-return completed', True)
except Exception as error:
    failed += 1
    print('FAIL: unhandled exception:',repr(error))
finally:
    print('summary:',passed,'passed;',failed,'failed')
    print('~~END~~')
