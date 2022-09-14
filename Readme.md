# Excerpt from gpu_undervolt.sh
Undervolting can save a lot of energy and can also make a GPU run cooler.
No liability taken for any damages, see license above. However, this script
is pretty short and all actions taken are not a particular rocket science.

For Windows, there are special tools like MSI Afterburner to undervolt. For
Linux however, the situation is trickier. This script might help.

Requirements:
1. Ubuntu Desktop Linux 22.04 (Ubuntu Server won't work)
2. nvidia-driver-515 (other versions might work, too)
3. heterogenous multi GPU systems (single GPU works too of course)

Currently supported cards: see undervolt_all_gpu below. If your card is not
listed, just look up the clocks at Wikipedia and add them to the list. In

    adjust_gpu $i 1695 200

the third argument (here 200) means a clock offset of 200 Mhz. The larger,
the more intense the undervolting. Too much undervolting destabilizes the
system and can make it crash. Therefore, this value can be tuned and an
actual setting can be verfied with a benchmark, e.g. some deep learning
training or your favorite GPU intense game.