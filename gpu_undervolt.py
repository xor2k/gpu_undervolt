#!/bin/sh
#
# MIT License
#
# Copyright (c) 2022 Michael Siebert
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
################################################################################
#
# Undervolting can save a lot of energy and can also make a GPU run cooler.
# No liability taken for any damages, see license above. However, this script
# is pretty short and all actions taken are not a particular rocket science.
#
# For Windows, there are special tools like MSI Afterburner to undervolt. For
# Linux however, the situation is trickier. This script might help.
#
# Requirements:
# 1. Ubuntu Desktop Linux 22.04 (Ubuntu Server won't work)
# 2. nvidia-driver-515 (other versions might work, too)
# 3. heterogenous multi GPU systems (single GPU works too of course)
#
# Currently supported cards: see gpu_info below. If your card is not listed,
# just look up the clocks at Wikipedia and add them to the list. In
#
#     'core': 1395, 'boost': 1695, 'offset': 200, 'threshold': 120
#
# the offset (here 200) means a clock offset of 200 Mhz. The larger, the more
# intense the undervolting. Too much undervolting destabilizes the system and
# can make it crash. Therefore, this value can be tuned and an actual setting
# can be verfied with a benchmark, e.g. some deep learning training or your
# favorite GPU intense game.
#
# Generally, once undervolting is turned on, the GPU clocks are locked and the
# GPU will consume more energy while idle. To overcome this, this script can
# run as a daemon in the background and monitor whether the power draw is
# above or below a certain threshold (120 watts in the line above). Once below
# the threshold, the script will automatically turn off undervolting again.
#
# The threshold can be determined by running an idle GPU, turning on
# undervolting, look at 'watch -n 0.1 nvidia-smi' and turning undervolting off
# again. The power use will ramp up for a short moment (e.g. from 110W to
# 119W) and then fall to back to actual idle levels (around 30W for RTX 3090).
################################################################################

import os, subprocess, asyncio, sys, re, argparse, signal
from enum import Enum
from pathlib import Path

gpu_info = {
    # e.g. https://en.wikipedia.org/wiki/GeForce_30_series + experimentation
    'NVIDIA GeForce RTX 3090': {
        'core': 1395, 'boost': 1695, 'offset': 200, 'threshold': 120
    },
}

xorg_conf_file=Path('/etc/X11/xorg.conf.d/10-nvidia.conf')
xwrapper_file=Path('/etc/X11/Xwrapper.config')

gpus=None
affected_gpus=None
display_to_use=None
xauthority_to_use=None
event_loop=None

power_draw_poll_intervall_s=0.5
daemon_action_interval_s=1

def get_gpus():
    output = subprocess.run([
        'nvidia-smi', '--query-gpu=gpu_name', '--format=csv,noheader'
    ], capture_output=True, encoding='utf-8')

    gpus_ = output.stdout.splitlines()

    gpus = []
    for i, gpu in enumerate(gpus_):
        if gpu not in gpu_info:
            raise TypeError('gpu "'+gpu+'" unknown')
        gpus += [{
            'info': gpu_info[gpu],
            'index': i
        }]
    
    return gpus

def need_modify_xwrapper_msg():
    print('"error: ${xwrapper_file} needs modification"')
    init_msg()

def xwrapper_needs_modification():
    xwrapper_content = xwrapper_file.read_text()

    return re.search(
        '^allowed_users=console', xwrapper_content, re.MULTILINE
    ) or not re.search(
        '^allowed_users=anybody', xwrapper_content, re.MULTILINE
    ) or not re.search(
        '^needs_root_rights=yes', xwrapper_content, re.MULTILINE
    )

def xorg_needs_extra_config():
    return not xorg_conf_file.exists()

def initialize_system():
    some_modifications_happened = False
    
    if xwrapper_needs_modification():
        xwrapper_content = xwrapper_file.read_text()
        xwrapper_content = xwrapper_content.replace(
            'allowed_users=console', '#allowed_users=console'
        )
        if 'allowed_users=anybody' not in xwrapper_content:
            xwrapper_content += '\nallowed_users=anybody'
        if 'needs_root_rights=yes' not in xwrapper_content:
            xwrapper_content += '\nneeds_root_rights=yes'
        
        xwrapper_file.write_text(xwrapper_content)
        
        print(f'modified {xwrapper_file}')
        print('these modifications may weaken xorg security')
        some_modifications_happened=True
    
    if xorg_needs_extra_config():
        xorg_conf_file.write_text(
            'Section "OutputClass"\n'+ \
            '    Identifier "nvidia"\n'+ \
            '    MatchDriver "nvidia-drm"\n'+ \
            '    Driver "nvidia"\n'+ \
            '    Option "AllowEmptyInitialConfiguration"\n'+ \
            '    Option "Coolbits" "28"\n'+ \
            '    ModulePath "/usr/lib/x86_64-linux-gnu/nvidia/xorg"\n'+ \
            'EndSection\n'
        )
        
        print(f'created {xorg_conf_file}')
        some_modifications_happened=True

    if some_modifications_happened:
        print('some modifications happened, please reboot')
    else:
        print('did not do anything, system already initialized')

async def run_power_draw():
    global gpus, power_draw_poll_intervall_s
    
    proc = await asyncio.create_subprocess_exec(
        'nvidia-smi', *[
            '--query-gpu=index,power.draw,pstate',
            '--format=csv,noheader',
            f'--loop-ms={int(power_draw_poll_intervall_s*1000)}'
        ],
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )

    while True:
        line = await proc.stdout.readline()
      
        if line == b'':
            break

        line = line.decode('ascii').rstrip()
        index, power_draw_, pstate_ = line.split(',')
        index = int(index)
        gpu = gpus[index]
        gpu['power_draw'] = float(power_draw_.strip()[:-2])
        gpu['pstate'] = int(pstate_.strip()[1:])

    await proc.wait()

def get_display():
    for file in Path('/tmp/.X11-unix').glob('X*'):
        return file.name[1:]

def get_xauthority_to_use():
    ps = subprocess.run(['ps', 'aux'], capture_output=True, encoding='utf-8')
    for line in ps.stdout.splitlines():
        m = re.match('.*/run/user/(?P<uid>\\d+)/gdm/Xauthority.*', line)
        if m:
            return f'/run/user/{m.group("uid")}/gdm/Xauthority'

def run_nvidia_settings(*args):
    global display_to_use, xauthority_to_use
    env = os.environ.copy()

    env['DISPLAY'] = ':'+display_to_use
    env['XAUTHORITY'] = xauthority_to_use
    subprocess.run(
        ['nvidia-settings', *args], env=env, capture_output=True
    )

def undervolt_gpu(gpu, disable):
    index = gpu['index']
    if disable:
        subprocess.run(
            ['nvidia-smi', '-i', str(index), '-pm', '0'],
            stdout=subprocess.DEVNULL
        )
        subprocess.run(
            ['nvidia-smi', '-i', str(index), '-rgc'],
            stdout=subprocess.DEVNULL
        )
        run_nvidia_settings(
            '-a', 'GPUPowerMizerMode=0',
            '-a', 'GPUGraphicsClockOffsetAllPerformanceLevels=0'
        )
        return
    
    gpu_info = gpu['info']
    offset = gpu_info['offset']
    subprocess.run(
        ['nvidia-smi', '-i', str(index), '-pm', '1'],
        stdout=subprocess.DEVNULL
    )
    subprocess.run([
        'nvidia-smi', '-i', str(index),
        '-lgc', f"{gpu_info['core']-offset},{gpu_info['boost']-offset}"
    ], stdout=subprocess.DEVNULL)
    run_nvidia_settings(
        '-a', 'GPUPowerMizerMode=1',
        '-a', f'GPUGraphicsClockOffsetAllPerformanceLevels={offset}'
    )

def init_msg():
    print(f'please run "sudo sh {sys.argv[0]} init"')
    print('some modifications may weaken xorg security')
    exit(1)

def signal_handler():
    global event_loop
    event_loop.stop()
    for gpu in affected_gpus:
        undervolt_gpu(gpu, True)
    print('gpu_undervolt daemon stopped and undervolting disabled, goodbye!')
    sys.exit(0)

async def daemon_main():
    global affected_gpus, daemon_action_interval_s, event_loop

    task = asyncio.create_task(run_power_draw())

    event_loop = task.get_loop()
    event_loop.add_signal_handler(signal.SIGINT, signal_handler)
    event_loop.add_signal_handler(signal.SIGTERM, signal_handler)

    print('daemon initialized, press ctrl+c or send SIGTERM to stop')

    while True:
        for gpu in affected_gpus:
            if 'pstate' not in gpu or gpu['pstate'] > 2:
                continue
            
            undervolt_gpu(gpu, gpu['power_draw'] <= gpu['info']['threshold'])

        await asyncio.sleep(daemon_action_interval_s)

def int_list(arg):
    return list(map(lambda x: int(x), sorted(list(set(arg.split(','))))))

class UsageMode(Enum):
    init = 'init'
    enable = 'enable'
    disable = 'disable'
    daemon = 'daemon'

    def __str__(self):
        return self.value

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'mode', type=lambda x: UsageMode[x], choices=list(UsageMode)
    )
    parser.add_argument(
        '-i', dest='gpu_list', type=int_list, nargs='?',
        help='comma separated indices of GPUs to use'
    )

    args = parser.parse_args()

    if os.geteuid() != 0:
        print('Please run as root')
        exit(1)

    gpus = get_gpus()
    if len(gpus) == 0:
        print('error: no GPUs found')
        exit(1)

    display_to_use = get_display()
    if display_to_use is None:
        print('error: could not determine DISPLAY to use')
        exit(1)

    xauthority_to_use = get_xauthority_to_use()
    if xauthority_to_use is None:
        print(
            'error: could not determine Xauthority to use, gdm not running?'
        )
        exit(1)

    if args.mode == UsageMode.init:
        initialize_system()
        exit(0)

    if xwrapper_needs_modification():
        print(f'error: {xwrapper_file} needs modification')
        init_msg()

    if xorg_needs_extra_config():
        print(f'error: {xorg_conf_file} does not exist')
        init_msg()

    affected_gpus = gpus if args.gpu_list is None \
        else list(map(lambda x: gpus[x], args.gpu_list))

    do_disable = args.mode == UsageMode.disable
    if args.mode == UsageMode.enable or do_disable:
        for gpu in affected_gpus:
            undervolt_gpu(gpu, do_disable)
        exit(0)

    if args.mode == UsageMode.daemon:
        asyncio.run(daemon_main())
        exit(0)