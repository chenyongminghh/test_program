#!/bin/bash
USER=`whoami`
MAIN_PATH=`echo ~`
STV_PATH=$MAIN_PATH"/MLU370/mlu370_test"
LOG_FILE=$MAIN_PATH"/start_utp.log"
LOCAL_FLG=$MAIN_PATH"/autotest.local"

function log_info()
{
    if [  -d /var/log  ];then
        mkdir -p /var/log 
    fi
    DATE_N=`date +"%Y-%m-%d %H:%M:%S"`
    USER_N=`whoami`
    echo "${DATE_N} INFO $@" |tee -a $LOG_FILE
}

function creat_testlink()
{
    if [ ! -d $STV_PATH ];then
        log_info "Create $STV_PATH and link files"
        
        mkdir -p $STV_PATH || ! log_info "mkdir $STV_PATH FAILED" || return 1
        echo 'hello123'|sudo -S chown -R $USER:$USER $STV_PATH
        
        ln -s /spider_test/MLU370/mlu370_test/tests $STV_PATH"/tests" || return 1
        ln -s /spider_test/MLU370/mlu370_test/modules $STV_PATH"/modules" || return 1
        ln -s /spider_test/MLU370/mlu370_test/utilities $STV_PATH"/utilities" || return 1
        mkdir -p $STV_PATH"/sequences" || return 1
        
        cp -rf /spider_test/MLU370/mlu370_test/logs $STV_PATH"/" || return 1
        cp -rf /spider_test/MLU370/mlu370_test/variables $STV_PATH"/" || return 1
        cp -rf /spider_test/MLU370/mlu370_test/_PWD_TEMP_ $STV_PATH"/" || return 1
        cp -rf /spider_test/MLU370/mlu370_test/saved.log $STV_PATH"/" || return 1
        log_info "create soft link success."
    fi
}

if [ ! -f $LOCAL_FLG ];then
    log_info "$LOCAL_FLG not exists"
    log_info "Lab multi UUT autotest"
    creat_testlink
    if [ $? -ne 0 ]; then
        log_info "create soft link FAILED"
        exit 1
    fi
    log_info "Update sequences files"
    cp -rf /spider_test/MLU370/mlu370_test/sequences/* $STV_PATH"/sequences/" || exit 1
fi

if [ ! -d $STV_PATH ];then
    log_info "$STV_PATH not exists, please check"
    exit 1
fi

HOSTIP=`/sbin/ifconfig -a|grep inet|grep -v 127.0.0.1|grep -v inet6|awk '{print $2}'|tr -d 'addr:'|grep '10.100'|grep -v '10.100.193'`
log_info "HostIP "$HOSTIP

cd $STV_PATH
export SUDO_ASKPASS=./_PWD_TEMP_
sudo -A python3 tests/setup_variables.py || ! log_info "Setup Variables FAILED" || exit 1

SEQNAME=`grep "SEQNAME" $STV_PATH"/variables" |cut -d' ' -f3 |sed 's/\"//g'`
if [ -z "$SEQNAME" ]; then
    log_info "SEQNAME is empty"
    exit 1
else
    log_info "SEQNAME is "$SEQNAME
fi

log_info "Start running "$SEQNAME
sudo -A python3 tests/seq.py $SEQNAME
if [ $? -ne 0 ]; then
    log_info "Running "$SEQNAME" FAILED"
    exit 1
fi
