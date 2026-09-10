"""Comprehensive Test Suite Runner for SnipGlide Python Pro Developer Suite."""
import os
import sys
import unittest
import time

# Ensure project root is first in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from snipglide.database.connection import initialize_database

def run_suite():
    initialize_database()
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    tests_dir = os.path.join(PROJECT_ROOT, "tests")
    test_files = [
        "test_dev_tools_service.py",
        "test_phase2_ui_integration.py",
        "test_regex_service.py",
        "test_clipboard_detector.py",
        "test_clipboard_regression.py",
        "test_smart_snippets.py",
        "test_api_client.py",
        "test_git_tools.py",
        "test_ai_platform.py",
        "test_projects_and_commands.py",
        "test_unified_search.py",
    ]

    print("=" * 70)
    print("SnipGlide Developer Suite: Full Test Suite Execution")
    print("=" * 70)

    for f in test_files:
        module_name = f[:-3]
        file_path = os.path.join(tests_dir, f)
        if os.path.isfile(file_path):
            try:
                mod = __import__(f"tests.{module_name}", fromlist=[module_name])
                tests = loader.loadTestsFromModule(mod)
                suite.addTests(tests)
                print(f"  [Loaded] tests.{module_name} ({tests.countTestCases()} test cases)")
            except Exception as e:
                print(f"  [Error loading] {f}: {e}")

    print("-" * 70)
    print(f"Total Test Cases to Execute: {suite.countTestCases()}")
    print("-" * 70)

    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    print("=" * 70)
    print("FINAL TEST METRICS:")
    print(f"  Total Run: {total}")
    print(f"  Passed:    {passed}")
    print(f"  Failed:    {failures}")
    print(f"  Errors:    {errors}")
    print(f"  Skipped:   {skipped}")
    print(f"  Time:      {elapsed:.3f}s")
    print("=" * 70)

    return 0 if (failures == 0 and errors == 0) else 1

if __name__ == "__main__":
    sys.exit(run_suite())
