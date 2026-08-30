import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set Windows App User Model ID
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
        log_path = os.path.join(BASE_DIR, "error.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[ERROR] {e}\n")
            traceback.print_exc(file=f)
