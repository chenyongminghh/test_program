#!/bin/bash
USER=`whoami`
MAIN_PATH=`echo ~`
LOG_FILE=$MAIN_PATH"/start_utp.log"

function log_info()
{
    if [  -d /var/log  ];then
        mkdir -p /var/log 
    fi
    DATE_N=`date +"%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo "${DATE_N} INFO $@" |tee -a $LOG_FILE
}
