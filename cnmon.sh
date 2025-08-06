#!/bin/bash

curPath=$(dirname $(readlink -f "$0"))
STV_PATH=${curPath}
LOG_PATH=$STV_PATH"/logs"

DEBUG_TOOL="cnmon"
DEBUG_PATH=$STV_PATH"/utilities/"$DEBUG_TOOL

function debug_tool_test()
{
    expect -c "
        spawn sudo $DEBUG_PATH info -c ${1} -${2}
        set timeout -1
        expect {
                \"*assword*\"  {send \"hello123\r\"; exp_continue;}
        }
    "
}

Card_ID=$1
current_time=`date +"%Y-%m-%d %H:%M:%S"`
echo $current_time "Start monitoring Card"$Card_ID" from" $PPID "-->" $$

while [ true ]
do
    start_time=`date +"%Y%m%d-%H%M%S"`
    LOADDRV=`lsmod |grep cambricon_drv`
    DRV_LOAD_FLAG=$LOG_PATH"/driver_loaded"
    if [[ -z "$LOADDRV" ]] || [[ ! -f "$DRV_LOAD_FLAG" ]]; then
        LOG_NAME=$LOG_PATH"/monitor_card"$Card_ID".log"
        sleep 2
    else
        BA_SN=`debug_tool_test ${Card_ID} p | grep SN | awk '{print $3}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        MCU_Ver=`debug_tool_test ${Card_ID} p | grep Firmware | awk '{print $3}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        ChipTemp=`debug_tool_test ${Card_ID} e | grep Chip | awk '{print $3}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        BoardTemp=`debug_tool_test ${Card_ID} e | grep Board | awk '{print $3}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        BoardPower=`debug_tool_test ${Card_ID} p |grep Usage | grep W | awk '{print $3}' | sed 's/[\t]//g;s/[\r]//g;s/[\n]//g'`
        LOG_NAME=$LOG_PATH"/monitor_card"$Card_ID"_"$BA_SN".log"
        echo "${start_time} BA:${BA_SN} VER:${MCU_Ver} Power:${BoardPower} ChipTemp:${ChipTemp} BoardTemp:${BoardTemp}" >> $LOG_NAME
        sleep 1
    fi
done
