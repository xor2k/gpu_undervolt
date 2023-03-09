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
# Currently supported cards: see undervolt_all_gpu below. If your card is not
# listed, just look up the clocks at Wikipedia and add them to the list. In
#
#     adjust_gpu $i 1695 200
#
# the third argument (here 200) means a clock offset of 200 Mhz. The larger,
# the more intense the undervolting. Too much undervolting destabilizes the
# system and can make it crash. Therefore, this value can be tuned and an
# actual setting can be verfied with a benchmark, e.g. some deep learning
# training or your favorite GPU intense game.
#
################################################################################

types=$(nvidia-smi --query-gpu=gpu_name --format=csv,noheader | sed -e 's/ /_/g')

undervolt_all_gpu(){
    i=0

    for type in $types; do
        if [ "$type" = "NVIDIA_GeForce_GTX_1080_Ti" ]; then
            adjust_gpu $i 1582 100
        elif [ "$type" = "NVIDIA_GeForce_GTX_1070" ]; then
            adjust_gpu $i 1683 100
        elif [ "$type" = "NVIDIA_GeForce_GTX_1650_with_Max-Q_Design" ]; then
            # discussion see https://github.com/xor2k/gpu_undervolt/issues/3
            adjust_gpu $i 1595 220            
        elif [ "$type" = "NVIDIA_GeForce_RTX_2070_SUPER" ]; then
            adjust_gpu $i 1770 100
        elif [ "$type" = "NVIDIA_GeForce_RTX_3090" ]; then
            adjust_gpu $i 1695 200
        else
            echo unknown type: $type
            exit 1
        fi
        i=$((i+1))
    done

    exit 0
}

if [ $(id -u) -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

init_msg() {
    echo Please run \"sudo sh $0 init\"
    echo Some modifications may weaken xorg security
    exit 1
}

xwrapper_file=/etc/X11/Xwrapper.config

need_modify_xwrapper_msg() {
    echo "error: ${xwrapper_file} needs modification"
    init_msg
}

modify_xwrapper() {
    cp -a $xwrapper_file ${xwrapper_file}.orig
    echo created ${xwrapper_file}.orig as backup of ${xwrapper_file}

    sed -i 's/allowed_users=console/#allowed_users=console/g' $xwrapper_file
    echo 'allowed_users=anybody' >> $xwrapper_file
    echo 'needs_root_rights=yes' >> $xwrapper_file
    echo "modified $xwrapper_file, may weaken xorg security"
    
    some_modifications_happened=True
}

check_xwrapper() {
    if grep -q ^allowed_users=console $xwrapper_file || \
    ! grep -q 'allowed_users=anybody' $xwrapper_file || \
    ! grep -q 'needs_root_rights=yes' $xwrapper_file; then
        $1
    fi
}

xorg_conf_file=/etc/X11/xorg.conf.d/10-nvidia.conf

if [ $# -eq 1 ] && [ $1 = 'init' ]; then
    check_xwrapper modify_xwrapper

    if ! [ -e $xorg_conf_file ]; then
cat > $xorg_conf_file << EOF
Section "OutputClass"
    Identifier "nvidia"
    MatchDriver "nvidia-drm"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration"
    Option "Coolbits" "28"
    ModulePath "/usr/lib/x86_64-linux-gnu/nvidia/xorg"
EndSection
EOF
        echo "created $xorg_conf_file."
        some_modifications_happened=true
    fi
    if [ "$some_modifications_happened" = true ]; then
        echo "Some modifications happened, please reboot."
    else
        echo "Did not do anything, system already initialized"
    fi
    exit 0
fi

check_xwrapper need_modify_xwrapper_msg

if ! [ -e $xorg_conf_file ]; then
    echo "error: $xorg_conf_file does not exist"
    init_msg
fi

count() {
    echo $#
}

xauthority_to_use=$(ps aux | grep -o /run/user/\[0-9\]*/gdm/Xauthority)

if [ $(count $xauthority_to_use) -lt 1 ]; then
    echo "error: gdm not running"
    exit 1
fi

run_nvidia_settings() {
    DISPLAY=$(cd /tmp/.X11-unix && for x in X*; do echo ":${x#X}"; done) \
    XAUTHORITY=$xauthority_to_use nvidia-settings $@
}

if [ $# -eq 1 ] && [ $1 = 'disable' ]; then
    echo disabling...
    nvidia-smi -pm 0
    nvidia-smi -rgc
    run_nvidia_settings \
     -a GPUGraphicsClockOffsetAllPerformanceLevels=0

    exit 0
fi


adjust_gpu() {
    
    gpu=$1
    gpu_high=$2 # e.g. 1770 (RTX 2070 Super)
    offset=$3

    nvidia-smi -i $gpu -pm 1
    nvidia-smi -i $gpu -lgc 0,$((gpu_high - offset))

    run_nvidia_settings \
     -a [gpu:$gpu]/GPUGraphicsClockOffsetAllPerformanceLevels=$offset

}

undervolt_all_gpu
