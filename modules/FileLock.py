#!/usr/local/bin/python35
import os
import os.path as osp

from fcntl import lockf,LOCK_EX,LOCK_UN,LOCK_SH,LOCK_NB


class FileLock:
    """! Class for locking files

    You can pass in filename and it will automatically be created
    if needed.  You can also pass an already-created file handle.

    @b Example
    @verbatim
    with FileLock('my_new_file') as fh:
         fh.write('here is some data under exclusive advisory lock')
    @endverbatim
    """

    def __init__(self, fname_or_fh, shared=False, do_not_block=False,
                 exit_state=LOCK_UN):
        """! Create a context manager for a lock
        @param fname_or_fh  Pass in an already-open file handle or just a file
                            name.  If the file does not exist, it will be
                            created.
        @param shared       Set to True to make the locked shared.  Any
                            number of lock owners can hold a the same lock
                            as long as the lock type is shared.   Default
                            is to False.
        @param do_not_block Set to True and any attempt to get a lock
                            will fail with IOError exception if the lock
                            is not immediately granted.   Default is False.
        @param exit_state   By default, exiting the with block will unlock
                            the lock.   You can specify an alternate state,
                            however, note that lock conversion is not
                            atomic.   Converting from LOCK_EX to LOCK_SH
                            for instance, is equivlent to
                            LOCK_EX
                            LOCK_UN
                            LOCK_SH
                            So there is a brief period where no lock is held
                            and another locking party can grab the lock.
        """
        self.locked = False
        if isinstance(fname_or_fh, str):
            self.fname = fname_or_fh
            self.fh = None
            self.do_close = True

            if (not osp.exists(self.fname)):
                # 'touch' a file of this name
                try:
                    with open(self.fname, 'a'):
                        os.utime(self.fname, None)
                        os.chmod(self.fname, 0o0666)
                except:
                    pass
        else:
            self.fh = fname_or_fh
            try:
                self.fname = self.fh.name
            except AttributeError:
                self.fname = str(self.fh)

            self.do_close = False

        if (shared):
            self.lock_type = LOCK_SH
        else:
            self.lock_type = LOCK_EX

        if (do_not_block):
            self.lock_type |= LOCK_NB

        self.exit_state = exit_state

    def __enter__(self):
        if self.fh == None:
            mode = "r+"
            self.fh = open(self.fname, mode)
        lockf(self.fh.fileno(), self.lock_type)
        self.locked = self.lock_type
        return self.fh


    def __exit__(self, etype, evalue, tb):
        lockf(self.fh.fileno(),self.exit_state)
        self.locked = False
        if self.do_close:
            self.fh.close()
            self.fh = None

        return False




if __name__ == "__main__":
    with FileLock(sys.argv[1], shared=True) as fh:
        print("got shared lock")
        with FileLock(fh):   # shared -> exclusive
            print("got exclusive lock")
