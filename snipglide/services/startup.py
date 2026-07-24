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
            root_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            bat_path = os.path.join(root_dir, "run.bat")
            if os.path.exists(bat_path):
                cmd = f'cmd.exe /c start /min "" "{bat_path}"'
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
            else:
                app_py = os.path.join(root_dir, "app.py")
                cmd = f'"{sys.executable}" "{app_py}"'
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
