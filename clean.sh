#!/bin/bash

curPath=$(dirname $(readlink -f "$0"))
logPath=${curPath}"/logs"
PASSWORD="hello123"

echo $curPath
echo $PASSWORD | sudo -S rm -rf error.log
echo $PASSWORD | sudo -S rm -rf errors.log
echo $PASSWORD | sudo -S rm -rf logdata.utp
echo $PASSWORD | sudo -S rm -rf onfail.log
echo $PASSWORD | sudo -S rm -rf rawtester.log
echo $PASSWORD | sudo -S rm -rf sequence.json
echo $PASSWORD | sudo -S rm -rf test.log
echo $PASSWORD | sudo -S rm -rf tester.log
echo $PASSWORD | sudo -S rm -rf logs/*
echo $PASSWORD | sudo -S rm -rf firmware
echo $PASSWORD | sudo -S rm -rf sttools

cp utilities/variables ./variables

echo

