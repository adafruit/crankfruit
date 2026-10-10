"""Finite real-device showcase with injected gameplay, real HDMI/audio output."""
hardware=None
passed=0
failed=0
try:
    from direct_hardware import DirectHardware
    from crankfruit import run_scene, entries
    hardware=DirectHardware();hardware.initialize()
    run_scene(hardware,dict(slug='splash'),duration=2500,name='splash')
    items=entries()
    run_scene(hardware,items=items,duration=4000)
    for slug,duration in (('almost-tennis',12000),('orbit-breaker',12000),('sound-explorer',18000)):
        item=next(x for x in items if x['slug']==slug)
        run_scene(hardware,item,duration=duration,scripted=True)
    run_scene(hardware,items=entries(),duration=4000)
    passed+=1;print('PASS: real-device video/audio showcase completed')
except Exception as exc:
    failed+=1;print('FAIL: showcase:',repr(exc))
finally:
    if hardware is not None:
        if hardware.close():passed+=1;print('PASS: showcase cleanup')
        else:failed+=1;print('FAIL: showcase cleanup')
    print('summary:',passed,'passed;',failed,'failed')
    print('~~END~~')
