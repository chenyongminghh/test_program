#!/bin/bash
USER=`whoami`
MAIN_PATH=`echo ~`
STV_PATH=$MAIN_PATH"/MLU370/mlu370_test"
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

DEBUG_TOOL=`grep "DEBUG_TOOL" $STV_PATH"/variables" |cut -d' ' -f3 |sed 's/\"//g'`
if [ -z "$DEBUG_TOOL" ]; then
    log_info "DEBUG_TOOL is empty"
    exit 1
else
    log_info "DEBUG_TOOL is "$DEBUG_TOOL
fi

MC_Qty=`lspci -d cabc:0370 |wc -l`
for ((i=0; i<$MC_Qty; i++))
do
    log_info "Start monitor card $i"
    ./monitor.sh $DEBUG_TOOL $i &
done

log_info "Start running "$SEQNAME
sudo -A python3 tests/seq.py $SEQNAME
if [ $? -ne 0 ]; then
    log_info "Running "$SEQNAME" FAILED"
    exit 1
fi
