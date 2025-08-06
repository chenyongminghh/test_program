#!/bin/bash
USER=`whoami`
MAIN_PATH=`echo ~`
STV_PATH=$MAIN_PATH"/MLU370/mlu370_test"
LOG_FILE=$MAIN_PATH"/start_utp.log"
QUIT_PATH=$MAIN_PATH"/quit.now"

function log_info()
{
    if [  -d /var/log  ];then
        mkdir -p /var/log 
    fi
    DATE_N=`date +"%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo "${DATE_N} INFO $@" |tee -a $LOG_FILE
}

log_info "Clean Auto Environment"

if [ -f $QUIT_PATH ];then
    log_info "Remove quit.now"
    echo 'hello123'|sudo -S rm -rf $QUIT_PATH
fi

if [ -d $STV_PATH ];then
    log_info "Remove "$STV_PATH
    echo 'hello123'|sudo -S rm -rf $STV_PATH
fi

echo ''

