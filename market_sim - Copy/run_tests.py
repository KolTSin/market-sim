#!/usr/bin/env python3
"""
Run all unit tests in the tests/ directory using pytest.
"""

import pytest
import sys
import os

def main():
    # Set the working directory to project root
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    # Print a header
    print("🔍 Running all tests...\n")

    # Run pytest on the tests directory
    exit_code = pytest.main([
        "tests",          # directory containing your tests
        "-v",             # verbose output
        "--maxfail=10",    # stop after first failure (optional)
        "--disable-warnings",
    ])

    if exit_code == 0:
        print("\n✅ All tests passed successfully!")
    else:
        print("\n❌ Some tests failed. See output above.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
