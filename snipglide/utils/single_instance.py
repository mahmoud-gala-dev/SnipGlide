import ctypes
import os


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str):
        self.name = name
        self.handle = None
        self.is_primary = True

    def acquire(self) -> bool:
        if os.name != "nt":
            self.is_primary = True
            return True

        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        self.is_primary = kernel32.GetLastError() != ERROR_ALREADY_EXISTS
        return self.is_primary

    def release(self):
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

