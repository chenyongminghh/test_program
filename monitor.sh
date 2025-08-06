#!/bin/bash

curPath=$(dirname $(readlink -f "$0"))
STV_PATH=${curPath}
LOG_PATH=$STV_PATH"/logs"

DEBUG_TOOL=$1
DEBUG_PATH=$STV_PATH"/utilities/"$DEBUG_TOOL

function debug_tool_test()
{
    expect -c "
        spawn sudo $DEBUG_PATH -i ${1} -p ${2}
        set timeout -1
        expect {
                \"*assword*\"  {send \"hello123\r\"; exp_continue;}
        }
    "
}

Card_ID=$2
current_time=`date +"%Y-%m-%d %H:%M:%S"`
echo $current_time "Start monitoring Card"$Card_ID" from" $PPID "-->" $$

while [ true ]
do
    start_time=`date +"%Y%m%d-%H%M%S"`
    LOADDRV=`lsmod |grep cambricon_drv`
    if [ -z "$LOADDRV" ]; then
        LOG_NAME=$LOG_PATH"/monitor_card"$Card_ID".log"
        #echo "${start_time} cambricon_drv do not loaded" >> $LOG_NAME
        sleep 2
    else
        BA_SN=`debug_tool_test ${Card_ID} 3 | grep sn_code | awk -F ':' '{print $2}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        MCU_Ver=`debug_tool_test ${Card_ID} 5 | grep mcu_version | awk -F ':' '{print $2}' | awk '{print $1}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        ChipTemp=`debug_tool_test ${Card_ID} 9 | grep chip_temp | awk -F ':' '{print $2}' | awk '{print $1}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        BoardTemp=`debug_tool_test ${Card_ID} 9 | grep board_temp | awk -F ':' '{print $2}' | awk '{print $1}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        BoardPower=`debug_tool_test ${Card_ID} 10 | grep board_power | awk -F ':' '{print $2}' | awk '{print $1}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        IPUDie0=`debug_tool_test ${Card_ID} 12 | grep die0_ipu_freq | awk -F ':' '{print $2}' | awk '{print $1}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        IPUDie1=`debug_tool_test ${Card_ID} 12 | grep die1_ipu_freq | awk -F ':' '{print $2}' | awk '{print $1}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        LOG_NAME=$LOG_PATH"/monitor_card"$Card_ID"_"$BA_SN".log"
        echo "${start_time} BA:${BA_SN} VER:${MCU_Ver} Power:${BoardPower} ChipTemp:${ChipTemp} BoardTemp:${BoardTemp} IPUDie0:${IPUDie0} IPUDie1:${IPUDie1}" >> $LOG_NAME
        sleep 0.2
    fi
done
