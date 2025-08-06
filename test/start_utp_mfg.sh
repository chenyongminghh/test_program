#!/bin/bash

USER=`whoami`
MAIN_PATH=`echo ~`
QUIT_PATH=$MAIN_PATH"/quit.now"
LOG_FILE=$MAIN_PATH"/start_utp.log"
STV_PATH=$MAIN_PATH"/MLU370/mlu370_test"

SERVER_IP="10.100.130.180"
NFS_SHARE=$SERVER_IP":/mnt/spider_test"
NFS_PATH="/home/cambricon/spider_test"

function log_info()
{
    if [  -d /var/log  ];then
        mkdir -p /var/log 
    fi
    DATE_N=`date +"%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo "${DATE_N} INFO $@" |tee -a $LOG_FILE
}

function check_nfs_common()
{
    dpkg --get-selections | grep nfs-common >/dev/null
    if [ $? -eq 0 ]; then
        return 0
    else
        log_info "nfs-common not installed"
        return 1
    fi
}

function mount_nfs()
{
    if [ ! -d $NFS_PATH ];then
        log_info "mkdir $NFS_PATH" 
        mkdir -p $NFS_PATH || ! log_info "mkdir spider_test failed" || return 1
    fi
    
    if mountpoint -q $NFS_PATH;then
        log_info "NFS mounted"
    else
        log_info "NFS not mounted, start mounting"
        echo "hello123" | sudo -S mount -t nfs $NFS_SHARE $NFS_PATH
        if [ $? -eq 0 ]; then
            log_info "NFS Mount succeess"
            return 0
        else
            log_info "NFS Mount failed"
            return 1
        fi
    fi
}

function copy_file()
{
    SOURCE_PATH=$NFS_PATH"/program/$1"
    if [ ! -f $SOURCE_PATH ]; then
        log_info "$1 not exists"
        return 1
    fi
    log_info "Copy $1"
    cp -rf $SOURCE_PATH $MAIN_PATH"/" || return 1
    return 0
}

log_info "**********UTP Start**********"
log_info "$0 PID  : $$"
log_info "$0 PPID : $PPID"
log_info "$0 UID  : $UID"

log_info "Start running start_utp.sh"
log_info "Sleep 30 seconds"
sleep 30

check_nfs_common || exit 1
mount_nfs || exit 1

copy_file "setup_program.sh" || ! log_info "Copy setup_program.sh failed" || exit 1
copy_file "start_mfg.sh" || ! log_info "Copy start_mfg.sh failed" || exit 1
copy_file "start_utp.sh" || ! log_info "Copy start_utp.sh failed" || exit 1

HOSTIP=`/sbin/ifconfig -a|grep inet|grep -v 127.0.0.1|grep -v inet6|awk '{print $2}'|tr -d 'addr:'|grep '10.100'|grep -v '10.100.193'|grep -v $SERVER_IP`
log_info "HostIP "$HOSTIP

INIT_FLAG=$NFS_PATH"/mtsn/"$HOSTIP"/init.need"
INIT_SEQ=$NFS_PATH"/mtsn/"$HOSTIP"/seqname.txt"
if [ -f "$INIT_FLAG" ]; then
    ./setup_program.sh || exit 1
    cp -rf $INIT_FLAG $STV_PATH"/" || ! log_info "Copy init.need failed" || exit 1
    cp -rf $INIT_SEQ $STV_PATH"/" || ! log_info "Copy seqname.txt failed" || exit 1
fi

if [ -f $QUIT_PATH ];then
    log_info "Exist quit.now, exit runing"
    exit 0
fi

if [ -d "$STV_PATH" ]; then
    log_info "Start FCT/Stress Testing"
    ./start_mfg.sh || ! log_info "start_mfg.sh test failed" || exit 1
else
    log_info "Please call engineer setup ServerHost firstly!!!"
    exit 1
fi

log_info "End running start_utp.sh"
exit 0
