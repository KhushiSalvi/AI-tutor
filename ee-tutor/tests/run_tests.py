"""Standalone test runner using Python standard library.
Discovers and runs all test functions and unittest.TestCase classes in tests/test_*.py.
Compatible with pytest when installed.
"""
import importlib.util
import inspect
import sys
import time
import traceback
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_all_tests():
    test_dir = ROOT / "tests"
    test_files = sorted(test_dir.glob("test_*.py"))

    total_passed = 0
    total_failed = 0
    start_time = time.time()

    print(f"=== Discovering tests in {test_dir} ===")
    for tf in test_files:
        module_name = tf.stem
        spec = importlib.util.spec_from_file_location(module_name, tf)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"\n[FAIL LOAD] {tf.name}: {e}")
            traceback.print_exc()
            total_failed += 1
            continue

        # --- Collect tests: plain test_ functions + unittest.TestCase subclasses ---
        plain_funcs = [
            (name, func) for name, func in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("test_")
        ]
        tc_classes = [
            cls for _, cls in inspect.getmembers(mod, inspect.isclass)
            if issubclass(cls, unittest.TestCase) and cls is not unittest.TestCase
        ]

        # Build a count for the header
        tc_method_count = sum(
            len([m for m in dir(cls) if m.startswith("test_")])
            for cls in tc_classes
        )
        total_in_file = len(plain_funcs) + tc_method_count
        print(f"\nRunning {tf.name} ({total_in_file} tests):", flush=True)

        # Run plain functions
        for name, func in plain_funcs:
            try:
                func()
                print(f"  [PASS] {name}", flush=True)
                total_passed += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}", flush=True)
                traceback.print_exc()
                total_failed += 1

        # Run unittest.TestCase subclasses
        for cls in tc_classes:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromTestCase(cls)
            for test in suite:
                method_name = test._testMethodName
                try:
                    test.setUp()
                    getattr(test, method_name)()
                    test.tearDown()
                    print(f"  [PASS] {cls.__name__}.{method_name}", flush=True)
                    total_passed += 1
                except Exception as e:
                    try:
                        test.tearDown()
                    except Exception:
                        pass
                    print(f"  [FAIL] {cls.__name__}.{method_name}: {e}", flush=True)
                    traceback.print_exc()
                    total_failed += 1

    elapsed = time.time() - start_time
    print("\n" + "=" * 50, flush=True)
    print(f"TEST SUMMARY: {total_passed} PASSED, {total_failed} FAILED in {elapsed:.2f}s", flush=True)
    print("=" * 50, flush=True)

    return total_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
