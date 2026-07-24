import ctypes
from ctypes import wintypes
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_active_window_info() -> tuple[str, str]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
        
    length = user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    title = buff.value
    
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    process_name = ""
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    
    h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if h_process:
        try:
            psapi = ctypes.windll.psapi
            buff_path = ctypes.create_unicode_buffer(260)
            psapi.GetModuleFileNameExW(h_process, 0, buff_path, 260)
            process_name = os.path.basename(buff_path.value)
        except Exception:
            pass
        finally:
            kernel32.CloseHandle(h_process)
            
    return title, process_name

def is_password_field_active() -> bool:
    title, proc = get_active_window_info()
    lower_title = title.lower()
    # Simple heuristics to avoid logging inside security panels
    if "password" in lower_title or "login" in lower_title or "sign in" in lower_title:
        return True
    return False
