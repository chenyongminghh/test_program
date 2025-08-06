#!/usr/local/bin/python35
import os
import os.path as osp
import select
import signal
import json
import logging

from getpass import getuser

import socket
from socket import socketpair

import Fails  # this will import all Fail classes and ItemType into builtins namespace

LPD_ASK_PASS_CMD = osp.abspath(osp.join(osp.dirname(osp.dirname(__file__)), 'utilities',
                                        'ask.py'))


def fork_run(cmd):
    in_main, in_fork = socketpair()
    out_main, out_fork = socketpair()
    err_main, err_fork = socketpair()


    pass_bind_s = socket.socket(socket.AF_INET,
                                socket.SOCK_STREAM)
    pass_bind_s.bind(("127.0.0.1", 0))
    pass_bind_s.listen(5)

    port = pass_bind_s.getsockname()[1]

    pid = os.fork()

    if (pid == 0):
        os.setsid()   # new session so we don't have a tty
        os.environ["PASS_PORT"] = str(port)
        os.environ["SSH_ASKPASS"] = LPD_ASK_PASS_CMD
        os.environ["SUDO_ASKPASS"] = LPD_ASK_PASS_CMD
        os.environ["DISPLAY"] = "1"   # only needs to be set
        os.environ["UTP_CMD_ID"] = "102"

        #
        # We won't be using these socket ends
        #
        in_main.close()
        out_main.close()
        err_main.close()


        #
        # The sockets become the stdin/out/err for the child
        #
        os.dup2(in_fork.fileno(), 0)
        os.dup2(out_fork.fileno(), 1)
        os.dup2(err_fork.fileno(), 2)


        for i in (3,4,5,6,7,8,9,10,11,12,13,14,15):
            try:
                os.close(i)
            except:
                pass

        os.execvp(cmd[0], cmd)
        os._exit(1)   # should never get here!

    #
    # Main thread doesn't need these
    #
    in_fork.close()
    out_fork.close()
    err_fork.close()


    return {"in": in_main, "out": out_main, "err": err_main,
            "pass": pass_bind_s, "pid" : pid}


def run_cmd(cmd, password, stdinput="", yes_no="yes",
            combine_std_out_err=False, echo=False, timeout=None):
    fd = fork_run(cmd)

    write_args = [fd["in"]] if stdinput else []
    read_args = [fd["out"], fd["err"], fd["pass"]]

    fd["in"].setblocking(False)
    fd["out"].setblocking(False)
    fd["err"].setblocking(False)

    s = None
    output = ""
    errput = ""
    ask = ""
    answer = None
    while len(read_args) > 1:
        if timeout is not None:
            r, w, e = select.select(read_args, write_args, [], timeout)
        else:
            r, w, e = select.select(read_args, write_args, [])

        if not any([r, w]):
            try:
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
                    os.kill(fd["pid"], sig)
            except ProcessLookupError:
                        pass
            raise TimeoutFail(ItemType.ssh, 'ssh command <{cmd}> has timeouted out with no response', cmd=cmd)

        for f in r:
            if f == fd["pass"]:
                (s, addr) = f.accept()
                ask = ""
                # remove fd["pass"] and replace with s
                read_args = [fd["out"], fd["err"], s]
                continue

            if f == s:
                msg = s.recv(1024).decode()
                if not msg:
                    logging.warning('ask.py died')
                    # replace s with fd["pass"]
                    read_args = [fd["out"], fd["err"], fd["pass"]]
                    continue

                ask += msg

                if ask.find('\n') != -1:
                    question = json.loads(ask.strip())['question']
                    # replace s with fd["pass"]
                    read_args = [fd["out"], fd["err"], fd["pass"]]

                    if question.find("assword") != -1:
                        if isinstance(password, str):
                            answer = password
                        else:
                            answer = password(question)
                    elif question.find("(yes/no)") != -1:
                        answer = yes_no
                    else:
                        raise RuntimeFail(ItemType.ssh, "Don't know how to answer question: {question}", question=question)
                    s.sendall(json.dumps({'answer':answer}).encode() + b'\n')
                    s.close()

                continue

            c = f.recv(1024)
            if not c:
                read_args.remove(f)
                continue

            if f == fd["out"] or combine_std_out_err:
                output += c.decode()
                if echo:
                    os.write(sys.stdout.fileno(), c)
            else:
                errput += c.decode()
                if echo:
                    os.write(sys.stderr.fileno(), c)
        for f in w:
            if f == fd["in"]:
                n = f.send(stdinput.encode())
                if n == 0:
                    stdinput = ""
                else:
                    stdinput = stdinput[n:]

                if not stdinput:
                    write_args.remove(fd["in"])
                    fd["in"].close()


    return os.waitpid(fd["pid"], 0)[1], output, errput


def ssh(host, cmd, password, stdinput="", use_pseudo_tty=False, port="22",
        ssh="/usr/bin/ssh", user=getuser()):
    ssh_cmd = [ssh, "-oStrictHostKeyChecking=no", "-oUserKnownHostsFile=/dev/null", "-oLogLevel=quiet", "-t" if use_pseudo_tty else "-T",
               "-p", port, "%s@%s" % (user, host), cmd]

    rc, out, err = run_cmd(ssh_cmd, password=password,
                            stdinput=stdinput, combine_std_out_err=True)

    return rc, out


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--password', type=str, default='',
                        help="The user's password")
    parser.add_argument('-i', '--input', type=str, default='',
                        help='Input the command may expect')
    parser.add_argument('-n', '--no', action='store_true', default=False,
                        help="Answer 'no' to any yes/no questions "
                        "(default is to answer 'yes')")
    parser.add_argument('-q', '--quiet', action='store_true', default=False,
                        help='Do not echo command output')
    parser.add_argument('command', type=str, nargs='+')

    args = parser.parse_args()

    yes_no = 'no' if args.no else 'yes'

    rc, out, err = run_cmd(cmd=args.command, password=args.password,
                           stdinput=args.input, yes_no=yes_no,
                           combine_std_out_err=True, echo=not args.quiet)

    return  rc>>8 | rc

if __name__ == "__main__":
    exit(main())
