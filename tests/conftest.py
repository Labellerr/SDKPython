"""
Pytest configuration and fixtures for the test suite.

This file provides:
- Custom pytest metadata for HTML reports
- Timestamped report organization
- Session-wide fixtures
- Custom markers
- Test environment configuration
- Shared integration test fixtures
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
        if not folder.name.replace("_", "").isdigit():
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
        print(
            f"\n🧹 Cleaned up {deleted_count} old test report folder(s) (older than {days_to_keep} days)"
        )

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
    html_option = getattr(config.option, "htmlpath", None) or config.getoption(
        "--html", default=None
    )

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
    if hasattr(config, "_static_html") and config._static_html:
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
    if hasattr(config, "_timestamped_junit") and config._timestamped_junit:
        if Path(config._timestamped_junit).exists():
            try:
                shutil.copy2(config._timestamped_junit, config._latest_junit)
                shutil.copy2(config._timestamped_junit, config._full_junit)
            except Exception as e:
                print(f"\n⚠️  Warning: Could not copy JUnit report: {e}")

    # Print report location summary
    if hasattr(config, "_run_report_dir"):
        print("\n" + "=" * 80)
        print("📊 TEST REPORTS GENERATED")
        print("=" * 80)
        print(f"  📁 Report folder: {config._run_report_dir}")
        if (
            hasattr(config, "_timestamped_html")
            and config._timestamped_html
            and Path(config._timestamped_html).exists()
        ):
            print(f"  📄 HTML report:   {config._timestamped_html}")
        if (
            hasattr(config, "_timestamped_junit")
            and Path(config._timestamped_junit).exists()
        ):
            print(f"  📄 JUnit XML:     {config._timestamped_junit}")
        print("\n  🔗 Quick Access:")
        if hasattr(config, "_latest_html"):
            print(f"     Latest report:  {config._latest_html}")
        if hasattr(config, "_full_html"):
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


# ============================================================================
# Shared Integration Test Fixtures
# ============================================================================


def check_required_env_vars(*var_names, warn=True):
    """
    Check if required environment variables are set.

    Args:
        *var_names: Variable number of environment variable names to check
        warn: If True, prints a warning message with missing variables

    Returns:
        tuple: (all_present: bool, missing_vars: list)

    Example:
        all_present, missing = check_required_env_vars("API_KEY", "API_SECRET", "CLIENT_ID")
        if not all_present:
            pytest.skip(f"Missing environment variables: {', '.join(missing)}")
    """
    missing_vars = [var for var in var_names if not os.getenv(var)]
    all_present = len(missing_vars) == 0

    if not all_present and warn:
        print(
            "\n⚠️  WARNING: Missing required environment variables: "
            + ", ".join(missing_vars)
        )
        print("   Please set these variables to run the tests:")
        for var in missing_vars:
            print("   - " + var)

    return all_present, missing_vars


def skip_if_missing_env_vars(*var_names):
    """
    Skip test if any required environment variables are missing.
    Prints warning with missing variable names.

    Args:
        *var_names: Variable number of environment variable names to check

    Raises:
        pytest.skip: If any variables are missing
    """
    all_present, missing = check_required_env_vars(*var_names, warn=True)
    if not all_present:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")


def skip_if_auth_failed(exception):
    """
    Check if exception is an authentication error and skip test if so.
    Otherwise, re-raises the exception.

    Args:
        exception: The exception to check

    Raises:
        pytest.skip: If authentication error detected
        Exception: Re-raises the original exception if not auth-related
    """
    error_str = str(exception).lower()
    auth_indicators = [
        "not authorized",
        "unauthorized",
        "invalid api key",
        "invalid api",
        "403",
        "401",
    ]

    if any(indicator in error_str for indicator in auth_indicators):
        print(
            "\n⚠️  WARNING: Authentication failed - Invalid or expired API credentials"
        )
        pytest.skip(
            "Authentication failed - Invalid or expired credentials: " + str(exception)
        )

    # Not an auth error, re-raise
    raise exception


def handle_auth_errors(func):
    """
    Decorator to automatically handle authentication errors in test functions.
    Skips test if authentication fails instead of failing it.

    Usage:
        @handle_auth_errors
        def test_something(client):
            # test code that might raise auth errors
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            skip_if_auth_failed(e)

    return wrapper


# ============================================================================
# Mock Fixtures for Unit Tests
# ============================================================================


@pytest.fixture
def client():
    """
    Mock LabellerrClient for unit tests.
    
    This fixture provides a mocked client instance that doesn't make real API calls.
    Unit tests should use this instead of integration_client.
    """
    from unittest.mock import Mock, MagicMock
    from labellerr.client import LabellerrClient
    
    mock_client = Mock(spec=LabellerrClient)
    mock_client.api_key = "test_api_key"
    mock_client.api_secret = "test_api_secret"
    mock_client.client_id = "test_client_id"
    mock_client.base_url = "https://api.labellerr.com"
    mock_client._session = MagicMock()
    mock_client.make_request = Mock()
    
    return mock_client


@pytest.fixture
def project(client):
    """
    Real LabellerrProject instance with mocked client for unit tests.
    
    This provides a real project instance that uses a mocked client,
    so tests can verify the project logic without making API calls.
    """
    from labellerr.core.projects.image_project import ImageProject
    
    # Mock project data that would normally come from API
    project_data = {
        "project_id": "test_project_id_12345",
        "project_name": "Test Project",
        "data_type": "image",
        "status_code": 200,
        "annotation_template_id": "test_template_id",
        "created_by": "test@example.com",
        "created_at": "2024-01-01T00:00:00Z",
        "attached_datasets": []
    }
    
    # Mock the client.make_request to return proper project data when called
    # This is needed because LabellerrProject factory calls get_project during init
    client.make_request.return_value = {"response": project_data}
    
    # Use ImageProject directly to bypass the factory pattern
    # ImageProject is a concrete implementation that doesn't trigger factory lookup
    project_instance = ImageProject.__new__(ImageProject)
    project_instance.client = client
    project_instance._LabellerrProject__project_id_input = "test_project_id_12345"
    project_instance._LabellerrProject__project_data = project_data
    
    return project_instance


# ============================================================================
# Integration Test Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def api_credentials():
    """
    Load and validate API credentials from environment.

    Returns:
        dict: Dictionary with api_key, api_secret, client_id

    Skips:
        If credentials are missing
    """
    from dotenv import load_dotenv

    load_dotenv()

    skip_if_missing_env_vars("API_KEY", "API_SECRET", "CLIENT_ID")

    return {
        "api_key": os.getenv("API_KEY"),
        "api_secret": os.getenv("API_SECRET"),
        "client_id": os.getenv("CLIENT_ID"),
    }


@pytest.fixture(scope="session")
def integration_client(api_credentials):
    """
    Create a shared Labellerr client instance for integration tests.

    This session-scoped fixture creates a single authenticated client instance
    shared across all integration tests to avoid repeated authentication.

    Requires environment variables:
        - API_KEY: Labellerr API key
        - API_SECRET: Labellerr API secret
        - CLIENT_ID: Labellerr client ID

    Skips:
        Tests if credentials are not configured or invalid

    Returns:
        LabellerrClient: Authenticated client instance
    """
    try:
        from labellerr.client import LabellerrClient
    except ImportError:
        pytest.skip("Labellerr SDK not installed")

    try:
        client = LabellerrClient(
            api_key=api_credentials["api_key"],
            api_secret=api_credentials["api_secret"],
            client_id=api_credentials["client_id"],
        )
        return client
    except Exception as e:
        skip_if_auth_failed(e)
        # This line won't be reached but satisfies linter
        return None
