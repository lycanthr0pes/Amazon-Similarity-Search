"""Linux exec helper: bind the model lifetime to its creating process/thread."""

import ctypes
import errno
import os
import signal
import stat
import sys


PR_SET_PDEATHSIG = 1
STARTUP_FAILURE = 70


def _exec_owned(parent, lease_fd, command):
    if parent <= 1 or os.getppid() != parent or not command:
        raise ValueError("Model owner is unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, *([ctypes.c_ulong] * 4)]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot bind model lifetime")
    # Death before prctl does not emit the signal: check the owner again.
    if os.getppid() != parent:
        raise ValueError("Model owner exited during startup")
    if os.stat(command[0]).st_mode & (stat.S_ISUID | stat.S_ISGID):
        raise ValueError("Privileged executables clear parent-death protection")
    try:
        capabilities = os.getxattr(command[0], "security.capability")
    except OSError as error:
        if error.errno not in {errno.ENODATA, errno.ENOTSUP}:
            raise
    else:
        if capabilities:
            raise ValueError("File capabilities clear parent-death protection")
    # Keep the abstract socket lease through exec; the kernel releases it on exit.
    os.set_inheritable(lease_fd, True)
    os.execv(command[0], command)


if __name__ == "__main__":
    try:
        _exec_owned(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3:])
    except (OSError, ValueError, IndexError, AttributeError):
        # Arguments and environment never belong in model diagnostics.
        sys.exit(STARTUP_FAILURE)
