import sys
from snipglide.utils.single_instance import SingleInstance

if __name__ == "__main__":
    with SingleInstance("Local\\SnipGlidePythonPro") as instance:
        if not instance.is_primary:
            print("[INFO] SnipGlide is already running in the background / system tray.")
            sys.exit(0)

        # High-performance, GPU-accelerated PySide6 Qt Application
        from snipglide.main_qt import run_app

        run_app()
