"""Prevent idle system sleep while the one release finalizer is alive.

Does not keep the display on or change persistent power settings. The request
is cleared on exit; explicit user sleep/lid actions still take precedence.
"""
import ctypes
import sys
import time
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]
k.OpenProcess.restype=ctypes.c_void_p
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
k.WaitForSingleObject.restype=ctypes.c_uint32
k.CloseHandle.argtypes=[ctypes.c_void_p]
k.SetThreadExecutionState.argtypes=[ctypes.c_uint32]
k.SetThreadExecutionState.restype=ctypes.c_uint32
handle=k.OpenProcess(0x00100000,False,int(sys.argv[1]))
assert handle
assert k.SetThreadExecutionState(0x80000001)
try:
    end=time.monotonic()+13*3600
    while time.monotonic()<end and k.WaitForSingleObject(handle,10000)==258:pass
finally:
    k.SetThreadExecutionState(0x80000000)
    k.CloseHandle(handle)
