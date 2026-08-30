import sys
import os

# Ensure current directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from snipglide.main_qt import run_app

if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Failed to start SnipGlide: {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")
