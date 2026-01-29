#!/usr/bin/env python3
"""
Enhanced orchestrator to run integration tests with detailed summaries.

Runs tests in sequence:
1. Create projects (test_create_project.py)
2. Create datasets (test_create_dataset.py)
3. Create templates (test_create_annotation_template.py)
4. Create exports (test_create_export.py)
5. Delete projects (cleanup)

Usage:
    python run_all_integration_tests.py [--keep-reports N]

Options:
    --keep-reports N    Keep only the latest N test report directories (default: 10)
                       Set to 0 to keep all reports
"""

import subprocess
import sys
import re
import shutil
import argparse
import time
from pathlib import Path
from datetime import datetime


def cleanup_old_reports(test_reports_dir: Path, keep_latest: int = 10):
    """Keep only the latest N test report directories, delete older ones."""
    if keep_latest == 0:
        # Keep all reports
        return

    if not test_reports_dir.exists():
        return

    # Get all timestamped directories
    report_dirs = [d for d in test_reports_dir.iterdir() if d.is_dir()]

    # Sort by modification time (newest first)
    report_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    # Delete older directories beyond keep_latest
    deleted_count = 0
    for old_dir in report_dirs[keep_latest:]:
        try:
            shutil.rmtree(old_dir)
            deleted_count += 1
        except Exception as e:
            print(f"⚠️  Warning: Could not delete old report directory {old_dir}: {e}")

    if deleted_count > 0:
        print(
            f"🧹 Cleaned up {deleted_count} old test report(s), keeping latest {keep_latest}"
        )


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Run integration tests with detailed summaries and report generation"
    )
    parser.add_argument(
        "--keep-reports",
        type=int,
        default=10,
        help="Keep only the latest N test report directories (default: 10, 0 = keep all)",
    )
    args = parser.parse_args()

    # Create reports directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_reports_base = Path(__file__).parent / "test_reports"
    report_dir = test_reports_base / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"TEST REPORTS DIRECTORY: {report_dir}")
    print(f"{'='*80}")

    # Cleanup old reports
    cleanup_old_reports(test_reports_base, keep_latest=args.keep_reports)

    results = {}

    # Define test suites to run sequentially
    test_suites = [
        ("test_create_project.py::TestCreateProjectIntegration", "Create Projects", 3),
        ("test_create_dataset.py::TestCreateDatasetIntegration", "Create Datasets", 5),
        (
            "test_create_annotation_template.py::TestCreateAnnotationTemplateIntegration",
            "Create Templates",
            2,
        ),
        ("test_create_export.py::TestCreateExportIntegration", "Create Exports", 3),
        ("test_create_project.py::TestDeleteProjectIntegration", "Delete Projects", 0),
    ]

    # Collect results from each suite
    all_results = []
    junit_file = report_dir / "integration_tests_junit.xml"
    html_file = report_dir / "integration_tests_report.html"

    print(f"\n{'='*80}")
    print(f"RUNNING INTEGRATION TESTS SEQUENTIALLY")
    print(f"{'='*80}\n")

    for test_file, description, delay_seconds in test_suites:
        # Check if test file exists
        test_path = Path(__file__).parent / test_file.split("::")[0]
        if not test_path.exists():
            print(f"⏭️  Skipping {description} (file not found)\n")
            continue

        print(f"{'='*80}")
        print(f"▶️  Running: {description}")
        print(f"{'='*80}\n")

        try:
            result = subprocess.run(
                [
                    "pytest",
                    f"tests/integration/{test_file}",
                    "-v",
                    "-s",
                    "--tb=short",
                    "--timeout=300",  # 5 minute timeout per test
                ],
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for entire suite
            )
        except subprocess.TimeoutExpired:
            print(f"⏱️  {description} TIMED OUT after 10 minutes")
            all_results.append(
                {
                    "description": description,
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "returncode": 1,
                }
            )
            continue

        # Print output
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # Parse statistics for this suite
        passed_match = re.search(r"(\d+) passed", result.stdout)
        failed_match = re.search(r"(\d+) failed", result.stdout)
        skipped_match = re.search(r"(\d+) skipped", result.stdout)

        suite_passed = int(passed_match.group(1)) if passed_match else 0
        suite_failed = int(failed_match.group(1)) if failed_match else 0
        suite_skipped = int(skipped_match.group(1)) if skipped_match else 0

        all_results.append(
            {
                "description": description,
                "passed": suite_passed,
                "failed": suite_failed,
                "skipped": suite_skipped,
                "returncode": result.returncode,
            }
        )

        # Print suite summary
        if result.returncode == 0:
            print(f"✅ {description} PASSED")
        else:
            print(f"❌ {description} FAILED")

        # Delay before next suite to allow API to process
        if delay_seconds > 0:
            print(f"\n⏳ Waiting {delay_seconds} seconds before next test suite...")
            time.sleep(delay_seconds)
            print()

    # Now run all tests together to generate combined report
    print(f"\n{'='*80}")
    print(f"GENERATING COMBINED REPORT")
    print(f"{'='*80}\n")

    test_files_to_run = [tf for tf, _, _ in test_suites]
    result = subprocess.run(
        [
            "pytest",
            *[f"tests/integration/{tf}" for tf in test_files_to_run],
            "-v",
            "--tb=short",
            f"--junitxml={junit_file}",
            f"--html={html_file}",
            "--self-contained-html",
            "-q",  # Quiet mode for report generation
        ],
        cwd=Path(__file__).parent.parent.parent,
        capture_output=True,
        text=True,
    )

    # Calculate totals
    total_passed = sum(r["passed"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    total_skipped = sum(r["skipped"] for r in all_results)
    total_tests = total_passed + total_failed + total_skipped

    results = {
        "returncode": 1 if total_failed > 0 else 0,
        "passed": total_passed,
        "failed": total_failed,
        "skipped": total_skipped,
        "total": total_tests,
    }

    # Print summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"  ✅ Total Passed:   {results['passed']}")
    print(f"  ❌ Total Failed:   {results['failed']}")
    print(f"  ⏭️  Total Skipped:  {results['skipped']}")
    print(f"  📊 Total Tests:    {results['total']}")
    print(f"{'='*80}")

    # Show warnings if tests were skipped
    if results["skipped"] > 0:
        print(f"\n⚠️  {results['skipped']} tests were SKIPPED")
        print("   This is likely due to missing dataset paths in your .env file")
        print("   Add these variables to run all tests:")
        print("   - VIDEO_DATASET_PATH or VIDEO_DATASET_ID")
        print("   - AUDIO_DATASET_PATH or AUDIO_DATASET_ID")
        print("   - DOCUMENT_DATASET_PATH or DOCUMENT_DATASET_ID")
        print("   - TEXT_DATASET_PATH or TEXT_DATASET_ID")

    print(f"\n{'='*80}")
    print(f"TEST REPORTS SAVED TO: {report_dir}")
    print(f"{'='*80}\n")

    print("📄 Generated Report Files:")
    print(f"  - JUnit XML: {junit_file}")
    print(f"  - HTML Report: {html_file}")

    print(f"\n💡 Tip: Open HTML report in your browser to see detailed test results")
    print(
        f"💡 JUnit XML file can be used by CI/CD systems (GitHub Actions, Jenkins, etc.)"
    )

    # Return 0 if all passed (ignoring skipped), 1 if any failed
    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
