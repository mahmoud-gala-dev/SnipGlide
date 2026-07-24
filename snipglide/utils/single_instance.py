import ctypes
import os


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str):
        self.name = name
        self.handle = None
        self.is_primary = True

    def __enter__(self):
        if os.name != "nt":
            return self

        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        self.is_primary = kernel32.GetLastError() != ERROR_ALREADY_EXISTS
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
