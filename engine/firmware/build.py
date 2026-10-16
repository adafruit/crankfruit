#!/usr/bin/env python3
"""Configurable cross-build, no private donor or device operations."""
import argparse,os,subprocess,sys
from pathlib import Path
F=Path(__file__).resolve().parent
R=F.parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--circuitpython',type=Path,default=F/'circuitpython')
    p.add_argument('--cross-prefix',default=os.environ.get('CROSS_COMPILE','arm-none-eabi-'))
    p.add_argument('--make',default='make')
    p.add_argument('--jobs',type=int,default=1)
    p.add_argument('--plan',action='store_true')
    a=p.parse_args()
    if a.jobs<1:p.error('--jobs must be positive')
    cp=a.circuitpython.resolve()
    # Keep the original module-local float semantics and linker integration.
    # Remap build locations so a new build need not expose local source paths.
    maps='-fstack-usage -ffile-prefix-map='+str(R)+'=engine -fmacro-prefix-map='+str(R)+'=engine -ffile-prefix-map='+str(cp)+'=circuitpython -fmacro-prefix-map='+str(cp)+'=circuitpython'
    command=[a.make,'-j'+str(a.jobs),'-C',str(cp/'ports/raspberrypi'),
             'BOARD=adafruit_fruit_jam','BUILD=build-crankfruit',
             'CROSS_COMPILE='+a.cross_prefix,'USER_C_MODULES='+str(R/'backends/circuitpython'),
             'PYTHON='+sys.executable,'CFLAGS_EXTRA='+maps,'V=commands']
    if a.plan:
        print('PLAN ONLY: RP2350 Adafruit Fruit Jam, USER_C_MODULES=engine/backends/circuitpython, jobs='+str(a.jobs))
        print('prepared source required; output ports/raspberrypi/build-crankfruit/firmware.uf2; no flash')
        return
    if not (cp/'py').is_dir():raise SystemExit('prepare pinned CircuitPython sources first')
    env=dict(os.environ)
    for key in ('CPATH','LIBRARY_PATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','GCC_EXEC_PREFIX','COMPILER_PATH','BASH_ENV','ENV'):
        env.pop(key,None)
    prefixdir=str(Path(a.cross_prefix).parent)
    if prefixdir!='.':env['PATH']=prefixdir+os.pathsep+env.get('PATH','')
    subprocess.run([sys.executable,str(R/'backends/circuitpython/generate_wrappers.py')],check=True)
    subprocess.run(command,env=env,check=True)
    print('FIRMWARE_BUILD_FINISHED: verify format, privacy, and hardware before substituting new firmware')
if __name__=='__main__':main()
