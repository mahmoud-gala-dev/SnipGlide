import sys

from snipglide.utils.single_instance import SingleInstance

if __name__ == "__main__":
    with SingleInstance("Local\\SnipGlidePythonPro") as instance:
        if not instance.is_primary:
            sys.exit(0)

        from snipglide.main import run_app

        run_app()
