#!/usr/bin/env python3
"""Run all tests for Squid Digest project."""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))


def run_all_tests():
    """Run all test files and return success status."""
    test_dir = Path(__file__).parent.parent / "tests"
    
    # Discover all test files
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Find all test_*.py files
    test_files = list(test_dir.glob("test_*.py"))
    
    if not test_files:
        print("No test files found!")
        return False
    
    print(f"Found {len(test_files)} test file(s):")
    for test_file in sorted(test_files):
        print(f"  - {test_file.name}")
    
    print("\n" + "=" * 80)
    print("Running tests...")
    print("=" * 80 + "\n")
    
    # Load tests from each file
    for test_file in sorted(test_files):
        module_name = test_file.stem
        try:
            # Import the test module
            test_dir_str = str(test_file.parent)
            if test_dir_str not in sys.path:
                sys.path.insert(0, test_dir_str)
            
            # Import module using importlib for better control
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, test_file)
            if spec is None or spec.loader is None:
                print(f"ERROR: Could not create spec for {test_file.name}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            suite.addTests(loader.loadTestsFromModule(module))
        except Exception as e:
            print(f"ERROR: Failed to load tests from {test_file.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("=" * 80)
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
