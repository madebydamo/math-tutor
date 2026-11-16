"""Cut a process (and everything it starts) off the network with a seccomp filter.

The tutor's maths tools run model-written code (`python`) and parse model-written
expressions. They only talk to Claude Code over stdio, so they get no network:
after `deny_network()` the process and its children can open Unix sockets only;
`socket()` for any other family fails with EACCES, and io_uring (which could open
sockets past the filter) is refused. Works unprivileged inside a Docker container
(no user namespaces needed): PR_SET_NO_NEW_PRIVS + SECCOMP_MODE_FILTER.
"""
from __future__ import annotations

import ctypes
import platform
import struct

# seccomp_data: int nr; u32 arch; u64 ip; u64 args[6]  (little endian on both arches)
_OFF_NR, _OFF_ARCH, _OFF_ARG0 = 0, 4, 16

# arch → (AUDIT_ARCH_*, __NR_socket, __NR_io_uring_setup)
_ARCHES = {
    "x86_64": (0xC000003E, 41, 425),
    "aarch64": (0xC00000B7, 198, 425),
}
_X32_BIT = 0x40000000          # x32 syscalls on x86_64 carry this bit: refuse them all
_AF_UNIX = 1
_EACCES = 13

_BPF_LD_W_ABS = 0x20
_BPF_JEQ_K = 0x15
_BPF_JGE_K = 0x35
_BPF_RET_K = 0x06
_RET_ALLOW = 0x7FFF0000
_RET_DENY = 0x00050000 | _EACCES  # SECCOMP_RET_ERRNO | EACCES

_PR_SET_NO_NEW_PRIVS = 38
_PR_SET_SECCOMP = 22
_SECCOMP_MODE_FILTER = 2


def _program(arch: int, nr_socket: int, nr_io_uring: int) -> list[tuple[int, int, int, int]]:
    return [
        (_BPF_LD_W_ABS, 0, 0, _OFF_ARCH),     # 0
        (_BPF_JEQ_K, 1, 0, arch),             # 1  native arch → 3
        (_BPF_RET_K, 0, 0, _RET_DENY),        # 2  i386/compat syscalls (socketcall) refused
        (_BPF_LD_W_ABS, 0, 0, _OFF_NR),       # 3
        (_BPF_JGE_K, 0, 1, _X32_BIT),         # 4
        (_BPF_RET_K, 0, 0, _RET_DENY),        # 5  x32 ABI refused
        (_BPF_JEQ_K, 0, 1, nr_io_uring),      # 6
        (_BPF_RET_K, 0, 0, _RET_DENY),        # 7  io_uring refused
        (_BPF_JEQ_K, 0, 3, nr_socket),        # 8  socket() → 9, else → 12
        (_BPF_LD_W_ABS, 0, 0, _OFF_ARG0),     # 9  domain
        (_BPF_JEQ_K, 1, 0, _AF_UNIX),         # 10 AF_UNIX → 12
        (_BPF_RET_K, 0, 0, _RET_DENY),        # 11 any other family refused
        (_BPF_RET_K, 0, 0, _RET_ALLOW),       # 12
    ]


def deny_network() -> None:
    """Install the filter on the calling process. Raises OSError when that is not possible."""
    machine = platform.machine()
    if machine not in _ARCHES:
        raise OSError(f"no network sandbox for {machine}")
    insns = _program(*_ARCHES[machine])
    buf = ctypes.create_string_buffer(b"".join(struct.pack("<HBBI", *i) for i in insns))

    class SockFprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    prog = SockFprog(len(insns), ctypes.cast(buf, ctypes.c_void_p))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, None, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
    if libc.prctl(_PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, ctypes.byref(prog), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "seccomp filter refused")
