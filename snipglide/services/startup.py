import winreg
import sys
import os
from snipglide.utils.logger import logger

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "SnipGlide"

def set_autostart(enabled: bool) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_WRITE)
        if enabled:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            venv_pythonw = os.path.join(root_dir, ".venv", "Scripts", "pythonw.exe")
            app_py = os.path.join(root_dir, "app.py")
            if os.path.exists(venv_pythonw):
                cmd = f'"{venv_pythonw}" "{app_py}"'
            else:
                pyw = sys.executable.replace("python.exe", "pythonw.exe")
                cmd = f'"{pyw}" "{app_py}"'
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
            logger.info("Application successfully registered in Windows Startup.")
        else:
            try:
                winreg.DeleteValue(key, APP_REG_NAME)
                logger.info("Application removed from Windows Startup.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Failed to configure registry startup: {e}")
        return False
