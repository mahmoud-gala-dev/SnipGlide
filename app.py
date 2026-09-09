import sys
import os

# Ensure current directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Force Windows Taskbar to display custom App Icon instead of default Python icon
try:
    import ctypes
    myappid = "snipglide.text.expander.pro.v2"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

from snipglide.main_qt import run_app

if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open(os.path.join(BASE_DIR, "crash.log"), "w", encoding="utf-8") as f:
                f.write(err_msg)
        except Exception:
            pass
        print(f"\n[ERROR] Failed to start SnipGlide: {e}\n{err_msg}")

