"""Requires the two source fixtures under /games/zz-test-*; remove after testing."""
passed=0
failed=0
hardware=None
def check(name,condition):
    global passed,failed
    if condition: passed+=1; print('PASS:',name)
    else: failed+=1; print('FAIL:',name)
try:
    from direct_hardware import DirectHardware
    from cartridges import inspect_folder, discover
    from crankfruit import run_scene, entries
    hardware=DirectHardware()
    hardware.initialize()
    for slug in ('zz-test-load-error','zz-test-step-error'):
        item=inspect_folder('/games/'+slug)
        check(slug+' accepted only as source candidate',item['enabled'])
        caught=False
        try: run_scene(hardware,item,duration=1000)
        except Exception as exc:
            caught='deliberate-fixture' in str(exc)
            print('EXPECTED_GAME_REJECTION',str(exc))
        check(slug+' actual runtime rejection',caught)
        check(slug+' audio stopped before recovery',hardware.fb.audio_pending==0)
        run_scene(hardware,items=entries(),duration=500)
        check(slug+' real library rendered after fault',True)
    item=inspect_folder('/games/orbit-breaker')
    run_scene(hardware,item,duration=2000,scripted=True)
    check('second real game works after both faults',True)
except Exception as exc:
    failed+=1;print('FAIL: recovery exception:',repr(exc))
finally:
    if hardware is not None:
        check('hardware cleanup',hardware.close())
    print('summary:',passed,'passed;',failed,'failed')
    print('~~END~~')
