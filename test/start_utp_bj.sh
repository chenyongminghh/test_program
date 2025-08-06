#!/bin/bash

USER=`whoami`
MAIN_PATH=`echo ~`
QUIT_PATH=$MAIN_PATH"/quit.now"
LOG_FILE=$MAIN_PATH"/start_utp.log"
LOCAL_FLG=$MAIN_PATH"/autotest.local"
NFS_PATH="/spider_test"
STV_PATH=$MAIN_PATH"/MLU370/mlu370_test"

function log_info()
{
    if [  -d /var/log  ];then
        mkdir -p /var/log 
    fi
    DATE_N=`date +"%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo "${DATE_N} INFO $@" |tee -a $LOG_FILE
}

function mount_nfs()
{
    if [ ! -d $NFS_PATH ];then
        log_info "mkdir $NFS_PATH" 
        echo 'hello123'|sudo -S mkdir $NFS_PATH
    fi
    
    if mountpoint -q /spider_test;then
        log_info "Check NFS mounted"
    else
        log_info "Check NFS not mounted, start mounting"
        echo 'hello123'|sudo -S mount -t nfs -o soft,nolock,rw,vers=3 10.100.32.2:/spider_test $NFS_PATH
        if [ $? -eq 0 ]; then
            log_info "NFS Mount succeess"
        else
            log_info "NFS Mount failed"
            return 1
        fi
    fi
    
    if [ ! -d $NFS_PATH"/STV1" ];then
        log_info "NFS not mounted, exit auto testing"
        return 1
    fi
    return 0
}

function copy_file()
{
    MC290_Qty=`lspci -d cabc:0290 |wc -l`
    MC370_Qty=`lspci -d cabc:0370 |wc -l`
    MC365_Qty=`lspci -d cabc:0365 |wc -l`
    log_info "Detect ${MC290_Qty} mlu290 cards"
    log_info "Detect ${MC370_Qty} mlu370 cards"
    log_info "Detect ${MC365_Qty} mlu365 cards"
    
    if [ "$MC290_Qty" -gt 0 ];then
        SOURCE_PATH="${NFS_PATH}/STV1/start_mfg_mlu290.sh"
    elif [[ "$MC370_Qty" -gt 0 ]] || [[ "$MC365_Qty" -gt 0 ]];then
        if [ -f $LOCAL_FLG ];then
            SOURCE_PATH="${STV_PATH}/tests/mlu370_host.sh"
        else
            SOURCE_PATH="${NFS_PATH}/MLU370/mlu370_test/tests/mlu370_server.sh"
        fi
    else
        log_info "Not found mlu290 or mlu370 cards"
        return 1
    fi
    log_info "Copy $SOURCE_PATH"
    cp -rf $SOURCE_PATH $MAIN_PATH"/start_mfg.sh" || return 1
    return 0
}

log_info "**********UTP Start**********"
log_info "$0 PID  : $$"
log_info "$0 PPID : $PPID"
log_info "$0 UID  : $UID"

log_info "Sleep 30 seconds"
sleep 30

if [ ! -f $LOCAL_FLG ];then
    mount_nfs || exit 1
fi

if [ -f $QUIT_PATH ];then
    log_info "Exist quit.now, exit runing"
    exit 0
fi

log_info "Start running start_utp.sh"
copy_file || ! log_info "Copy start_mfg.sh failed" || exit 1

./start_mfg.sh
log_info "End running start_mfg.sh"
