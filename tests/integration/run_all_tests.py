#!/usr/bin/env python3
"""
Simple orchestrator to run integration tests in sequence:
1. Create projects (test_create_project.py)
2. Create datasets (test_dataset_creation.py)
3. Create templates (test_template_creation.py)
4. Delete projects (cleanup)

Usage:
    python run_all_tests.py
"""

import subprocess
import sys
from pathlib import Path

def run_tests(test_file: str, description: str) -> int:
    """Run pytest on a test file. Returns exit code."""
    print(f"\n{'='*80}")
    print(f"RUNNING: {description}")
    print(f"{'='*80}\n")

    result = subprocess.run(
        ["pytest", f"tests/integration/{test_file}", "-v", "-s"],
        cwd=Path(__file__).parent.parent.parent
    )

    if result.returncode == 0:
        print(f"\n✅ {description} PASSED")
    else:
        print(f"\n❌ {description} FAILED")

    return result.returncode

def main():
    results = {}

    # 1. Create projects
    results["create_project"] = run_tests(
        "test_create_project.py::TestCreateProjectIntegration",
        "Create Projects"
    )

    # 2. Create datasets (if test file exists)
    dataset_test = Path(__file__).parent / "test_dataset_creation.py"
    if dataset_test.exists():
        results["create_dataset"] = run_tests(
            "test_dataset_creation.py",
            "Create Datasets"
        )
    else:
        print(f"\n⏭️  Skipping test_dataset_creation.py (not found)")

    # 3. Create templates (if test file exists)
    template_test = Path(__file__).parent / "test_template_creation.py"
    if template_test.exists():
        results["create_template"] = run_tests(
            "test_template_creation.py",
            "Create Templates"
        )
    else:
        print(f"\n⏭️  Skipping test_template_creation.py (not found)")

    # 4. Delete projects
    results["delete_project"] = run_tests(
        "test_create_project.py::TestDeleteProjectIntegration",
        "Delete Projects"
    )

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for name, code in results.items():
        status = "✅ PASSED" if code == 0 else "❌ FAILED"
        print(f"  {name:20s}: {status}")
    print(f"{'='*80}\n")

    # Return 0 if all passed, 1 otherwise
    return 0 if all(code == 0 for code in results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
