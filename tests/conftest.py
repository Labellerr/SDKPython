"""
Pytest configuration and fixtures for the test suite.

This file provides:
- Custom pytest metadata for HTML reports
- Timestamped report organization
- Session-wide fixtures
- Custom markers
- Test environment configuration
"""

import os
import platform
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def cleanup_old_reports(reports_dir: Path, days_to_keep: int = 30):
    """
    Clean up test report folders older than the specified number of days.

    Args:
        reports_dir: Base directory containing timestamped report folders
        days_to_keep: Number of days to keep reports (default: 30)
    """
    if not reports_dir.exists():
        return

    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    deleted_count = 0
    failed_deletions = []

    # Iterate through timestamped folders (format: YYYYMMDD_HHMMSS)
    for folder in reports_dir.iterdir():
        if not folder.is_dir():
            continue

        # Skip non-timestamped folders (like assets, or other directories)
        if not folder.name.replace('_', '').isdigit():
            continue

        try:
            # Parse folder name to get creation date
            folder_date = datetime.strptime(folder.name, "%Y%m%d_%H%M%S")

            # Delete if older than cutoff date
            if folder_date < cutoff_date:
                shutil.rmtree(folder)
                deleted_count += 1
        except (ValueError, OSError) as e:
            # Skip folders that don't match format or can't be deleted
            failed_deletions.append((folder.name, str(e)))

    if deleted_count > 0:
        print(f"\n🧹 Cleaned up {deleted_count} old test report folder(s) (older than {days_to_keep} days)")

    if failed_deletions:
        print(f"⚠️  Failed to delete {len(failed_deletions)} folder(s):")
        for folder_name, error in failed_deletions:
            print(f"   - {folder_name}: {error}")


def pytest_configure(config):
    """Configure pytest with custom metadata and timestamped reports."""
    # Generate timestamp for this test run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create reports directory structure: test_reports/YYYYMMDD_HHMMSS/
    reports_base_dir = Path("tests/integration/test_reports")
    run_report_dir = reports_base_dir / timestamp
    run_report_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old reports (older than 30 days)
    cleanup_old_reports(reports_base_dir, days_to_keep=30)

    # Configure HTML report path - use static path for pytest-html to write to
    html_option = getattr(config.option, 'htmlpath', None) or config.getoption("--html", default=None)

    if html_option and html_option != "None":
        # Let pytest-html write to a static temporary path
        static_html_path = reports_base_dir / ".temp_report.html"
        config.option.htmlpath = str(static_html_path)

        # Store the static path and final timestamped path for later move
        config._static_html = str(static_html_path)

        if html_option == "report.html":
            # Default from pytest.ini - will move to timestamped folder
            config._timestamped_html = str(run_report_dir / "test-report.html")
        else:
            # Specific path provided
            config._timestamped_html = str(Path(html_option))
    else:
        config._static_html = None
        config._timestamped_html = None

    # Configure JUnit XML report path
    junit_option = config.getoption("--junit-xml", default=None)
    if junit_option is None:
        # No --junit-xml provided, set path inside timestamped folder
        junit_report = run_report_dir / "junit.xml"
        config.option.xmlpath = str(junit_report)
    else:
        # --junit-xml was provided via command line, use that
        junit_report = Path(junit_option)

    # Store paths for later use
    config._run_report_dir = str(run_report_dir)
    config._timestamped_junit = str(junit_report)
    config._latest_html = str(reports_base_dir / "test-report.html")
    config._latest_junit = str(reports_base_dir / "junit.xml")
    config._full_html = str(reports_base_dir / "full-test-report.html")
    config._full_junit = str(reports_base_dir / "full-junit.xml")

    # Add custom metadata to HTML report
    config._metadata = {
        "Project": "Labellerr SDK",
        "Python Version": platform.python_version(),
        "Platform": platform.platform(),
        "Test Environment": os.getenv("TEST_ENV", "local"),
        "Test Run Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Timestamp": timestamp,
        "Report Directory": str(run_report_dir),
    }


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Hook that runs after all tests finish."""
    # Add summary information
    if hasattr(session.config, "_metadata"):
        session.config._metadata["Exit Status"] = exitstatus


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Hook that runs at the very end, after pytest-html writes reports."""
    import time

    # Small delay to ensure pytest-html has finished writing
    time.sleep(0.5)

    # Move HTML report from static path to timestamped location
    if hasattr(config, '_static_html') and config._static_html:
        static_html_path = Path(config._static_html)
        if static_html_path.exists() and config._timestamped_html:
            try:
                timestamped_html_path = Path(config._timestamped_html)
                timestamped_assets = timestamped_html_path.parent / "assets"

                # Move the HTML report from static to timestamped location
                shutil.move(str(static_html_path), str(timestamped_html_path))

                # Move assets folder if it exists
                static_assets = static_html_path.parent / "assets"
                if static_assets.exists():
                    if timestamped_assets.exists():
                        shutil.rmtree(timestamped_assets)
                    shutil.move(str(static_assets), str(timestamped_assets))

                # Now copy to base directory for easy access
                shutil.copy2(str(timestamped_html_path), config._latest_html)
                shutil.copy2(str(timestamped_html_path), config._full_html)

                # Copy assets folder to base directory if it exists
                if timestamped_assets.exists():
                    base_assets = Path(config._latest_html).parent / "assets"
                    if base_assets.exists():
                        shutil.rmtree(base_assets)
                    shutil.copytree(str(timestamped_assets), str(base_assets))

            except Exception as e:
                print(f"\n⚠️  Warning: Could not move/copy HTML report: {e}")

    # Copy JUnit XML reports
    if hasattr(config, '_timestamped_junit') and config._timestamped_junit:
        if Path(config._timestamped_junit).exists():
            try:
                shutil.copy2(config._timestamped_junit, config._latest_junit)
                shutil.copy2(config._timestamped_junit, config._full_junit)
            except Exception as e:
                print(f"\n⚠️  Warning: Could not copy JUnit report: {e}")

    # Print report location summary
    if hasattr(config, '_run_report_dir'):
        print("\n" + "=" * 80)
        print("📊 TEST REPORTS GENERATED")
        print("=" * 80)
        print(f"  📁 Report folder: {config._run_report_dir}")
        if hasattr(config, '_timestamped_html') and config._timestamped_html and Path(config._timestamped_html).exists():
            print(f"  📄 HTML report:   {config._timestamped_html}")
        if hasattr(config, '_timestamped_junit') and Path(config._timestamped_junit).exists():
            print(f"  📄 JUnit XML:     {config._timestamped_junit}")
        print(f"\n  🔗 Quick Access:")
        if hasattr(config, '_latest_html'):
            print(f"     Latest report:  {config._latest_html}")
        if hasattr(config, '_full_html'):
            print(f"     Full report:    {config._full_html}")
        print("=" * 80)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture test results and add extra information.
    This is called for setup, call, and teardown phases of each test.
    """
    outcome = yield
    report = outcome.get_result()

    # Add extra information to failed tests
    if report.when == "call" and report.failed:
        # Add test duration to report
        if hasattr(report, "duration"):
            report.extra = getattr(report, "extra", [])


def pytest_collection_modifyitems(config, items):
    """
    Modify test items after collection.
    This can be used to mark tests or sort them.
    """
    # Sort tests to run faster ones first (optional)
    pass
