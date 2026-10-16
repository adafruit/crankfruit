"""Crankfruit: standalone compatible-source game player for Adafruit Fruit Jam."""
import gc
import time
from player import GamePlayer
from cartridges import discover, load

class SceneCleanupError(RuntimeError):
    pass


def entries(root='/games'):
    items = discover(root)
    items.append(dict(slug='sound-explorer', title='Sound Explorer',
                      description='LIVE SYNTHS + PLAYDATE AUDIO FILES',
                      enabled=True, reason='', kind='builtin'))
    return items


def test_buttons(name, elapsed):
    if name == 'library':
        return 2 if 500 <= elapsed < 600 else 32 if 1100 <= elapsed < 1200 else 0
    if name == 'return': return 32 if 500 <= elapsed < 1900 else 0
    if name == 'sound-explorer':
        phase=elapsed%12000
        if 500<=phase<600 or 1500<=phase<1600 or 4100<=phase<4200 or 7100<=phase<7200 or 9600<=phase<9700: return 2
        if 3000<=phase<3100 or 6000<=phase<6100 or 8500<=phase<8600: return 32
        if 2200<=phase<2300 or 5000<=phase<5100 or 10500<=phase<10600: return 16
        return 0
    return ((1 if elapsed//1500%2 else 2) if elapsed>900 else 0) | (32 if elapsed%700<70 else 0)


def run_scene(hardware, item=None, items=None, selected=0, message='', duration=None, scripted=False, name=None, crank=None):
    runtime = player = None
    scene = name or ('library' if items is not None else item['slug'])
    try:
        gc.collect()
        if scene == 'splash':
            from bootclip import BootClip
            runtime = BootClip()
        elif items is not None:
            from library import Library
            runtime = Library(hardware.runtime_class,items,selected,message)
        elif item['kind'] == 'builtin':
            from sound_explorer import SoundExplorer
            runtime = SoundExplorer(hardware.runtime_class)
        else:
            source = load(item)
            runtime = hardware.runtime_class(source,heap_cap=item['heap_cap'])
            del source
        if hasattr(runtime, 'crank_step') and getattr(crank, 'step_degrees', None):
            runtime.crank_step = crank.step_degrees  # per crank type (/crank.json, /gamepad.json)
        gc.collect()
        print('SCENE',scene,'heap',runtime.heap_stats(),'python_free',gc.mem_free())
        player = GamePlayer(runtime,hardware,hardware.fb,hardware.clock,present_every=1,prefill_frames=4,crank=crank)
        player.start(0)
        start = hardware.clock.now()
        released = False
        held = None
        route = None
        while True:
            now = hardware.clock.now(); elapsed = now-start
            buttons = test_buttons(scene,elapsed) if scripted else hardware.read_buttons()
            if not released and buttons == 0: released = True
            active = buttons if released else 0
            before = player.metrics['frames']
            player.tick(active & 63)
            if player.metrics['frames'] != before:
                if items is not None:
                    route = runtime.action
                elif scene != 'splash':
                    if active & 64: route = 'library'  # gamepad Options
                    elif active & 32:
                        if held is None: held = hardware.clock.now()
                        elif hardware.clock.now()-held >= 1200: route = 'library'
                    else: held = None
            if route is not None or (duration is not None and elapsed >= duration): break
            time.sleep(.001)
        player.finish()
        deadline = hardware.clock.now()+1000
        while player.tick() != 'DRAINED':
            if hardware.clock.now()>deadline: raise RuntimeError('scene audio drain timeout')
            time.sleep(.001)
        print('SCENE_DONE',scene,player.metrics,player.stream.metrics,runtime.heap_stats())
        gamepad = getattr(hardware, 'gamepad', None)
        if gamepad is not None and gamepad.enabled:
            print('GAMEPAD_DONE',scene,gamepad.scene_metrics())
        sensor = getattr(crank, 'sensor', None)
        if hasattr(sensor, 'scene_metrics'):
            print('CRANK_DONE',scene,sensor.scene_metrics())  # encoder read glitches
        skipped = getattr(hardware, 'skipped_presents', None)
        if skipped is not None:
            print('DISPLAY_DONE',scene,'skipped_unchanged_presents',skipped)
            hardware.skipped_presents = 0
        if scripted:
            assert player.metrics['errors'] == player.metrics['deadline_failures'] == 0
            assert player.stream.metrics['errors'] == player.stream.metrics['dropped_bytes'] == player.stream.metrics['underrun_observations'] == 0
        return route
    finally:
        try:
            if player is not None and player.stream.state != 'DRAINED':
                print('INTERRUPTED_BEFORE_STOP',scene,player.metrics,player.stream.metrics)
                player.stop()
                deadline=hardware.clock.now()+1000
                while player.stream.poll_stop() != 'STOPPED':
                    if hardware.clock.now()>deadline: raise SceneCleanupError('audio stop did not complete; restart required')
                    time.sleep(.001)
        finally:
            if runtime is not None: runtime.close()
            gc.collect()


def main(test=False, endurance=0):
    import direct_hardware
    from direct_hardware import DirectHardware
    from crank_input import CrankInput, load_config
    from gamepad_input import GamepadInput, load_config as load_gamepad_config
    hardware = DirectHardware()
    crank = None
    try:
        load_display = getattr(direct_hardware, 'load_display_config', None)
        if load_display is not None:
            try: hardware.configure(load_display('/display.json'))  # 2-bit greys, B1 cycles 3 modes
            except OSError as exc:
                if exc.args[0] != 2: raise  # missing file keeps 1x
        hardware.initialize()
        try: config=load_config('/crank.json')
        except OSError as exc:
            if exc.args[0] != 2: raise
            config=None
        crank=CrankInput(config)
        print('CRANK_INPUT',crank.kind,'enabled',crank.enabled)
        try: config=load_gamepad_config('/gamepad.json')
        except OSError as exc:
            if exc.args[0] != 2: raise
            config=None
        hardware.gamepad=GamepadInput(config)
        print('GAMEPAD_INPUT',hardware.gamepad.kind,'enabled',hardware.gamepad.enabled)
        if hardware.gamepad.crank is not None:
            if crank.enabled:
                print('GAMEPAD_CRANK ignored: /crank.json hardware crank takes priority')
            else:
                crank.close()
                crank=hardware.gamepad.crank  # right stick feeds Lua games' crank
                print('CRANK_INPUT',crank.kind,'enabled',crank.enabled)
        run_scene(hardware,dict(slug='splash'),duration=2500,name='splash',scripted=test)
        selected = 0; message = ''
        if test:
            items = entries()
            assert len(items)>=3
            route = run_scene(hardware,items=items,duration=3000,scripted=True,crank=crank)
            assert route == 1, 'dynamic library selection mismatch'
            for item in items:
                if item['enabled']:
                    run_scene(hardware,item,duration=endurance or 16000,scripted=True,crank=crank)
            target = next(x for x in items if x['enabled'] and x['kind']=='lua')
            assert run_scene(hardware,target,duration=3000,scripted=True,name='return')=='library'
            print('CRANKFRUIT_PASS (injected inputs, not physical button presses)')
            return
        library_failures = []
        while True:
            items = entries()
            try:
                selected = run_scene(hardware,items=items,selected=selected,message=message,crank=crank)  # crank moves the highlight
            except Exception as exc:
                if isinstance(exc,SceneCleanupError): raise
                # e.g. a >100ms system freeze while the host writes to CIRCUITPY.
                # run_scene already stopped audio; reopen the library unless it
                # keeps failing (3 times within 60s).
                now = hardware.clock.now()
                library_failures = [t for t in library_failures if now-t < 60000]+[now]
                print('LIBRARY_ERROR',repr(exc),'recent',len(library_failures))
                if len(library_failures) >= 3: raise
                message = 'RECOVERED: '+str(exc)
                continue
            message = ''
            try:
                run_scene(hardware,items[selected],crank=crank)  # Lua games and Sound Explorer
            except Exception as exc:
                if isinstance(exc,SceneCleanupError): raise
                # Audio is stopped and runtime released by run_scene before UI recovery.
                print('CARTRIDGE_ERROR',items[selected]['slug'],repr(exc))
                message = 'GAME ERROR: '+str(exc)
    finally:
        try:
            if crank is not None: crank.close()
            gamepad = getattr(hardware, 'gamepad', None)
            if gamepad is not None: gamepad.close()
        finally:
            closed = hardware.close()
            print('CLEANUP',closed,hardware.cleanup_error)
            if not closed: raise RuntimeError('hardware stop still pending')
