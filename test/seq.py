#!/usr/bin/python3.5
import os
import sys
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP

def main():
    return UTP.run_sequence(sys.argv[1])


if __name__ == '__main__':
    sys.exit(UTP.runmain(main))
