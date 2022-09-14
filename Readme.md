# Which file to use?
`gpu_undervolt_old.sh` has support for more GPUs, but does not come with a
daemon mode. It is obsolete and will be removed in the future.

`gpu_undervolt.py` script is the current version. Especially, its daemon mode
helps with idle power consumption, see below.
# Excerpt from gpu_undervolt.py
Undervolting can save a lot of energy and can also make a GPU run cooler.
No liability taken for any damages, see license above. However, this script
is pretty short and all actions taken are not a particular rocket science.

For Windows, there are special tools like MSI Afterburner to undervolt. For
Linux however, the situation is trickier. This script might help.

Requirements:
1. Ubuntu Desktop Linux 22.04 (Ubuntu Server won't work)
2. nvidia-driver-515 (other versions might work, too)
3. heterogenous multi GPU systems (single GPU works too of course)

Currently supported cards: see gpu_info below. If your card is not listed,
just look up the clocks at Wikipedia and add them to the list. In

    'core': 1395, 'boost': 1695, 'offset': 200, 'threshold': 120

the offset (here 200) means a clock offset of 200 Mhz. The larger, the more
intense the undervolting. Too much undervolting destabilizes the system and
can make it crash. Therefore, this value can be tuned and an actual setting
can be verfied with a benchmark, e.g. some deep learning training or your
favorite GPU intense game.

Generally, once undervolting is turned on, the GPU clocks are locked and the
GPU will consume more energy while idle. To overcome this, this script can
run as a daemon in the background and monitor whether the power draw is
above or below a certain threshold (120 watts in the line above). Once below
the threshold, the script will automatically turn off undervolting again.

The threshold can be determined by running an idle GPU, turning on
undervolting, look at 'watch -n 0.1 nvidia-smi' and turning undervolting off
again. The power use will ramp up for a short moment (e.g. from 110W to
119W) and then fall to back to actual idle levels (around 30W for RTX 3090).