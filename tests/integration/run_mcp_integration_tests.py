#!/usr/bin/env python3
"""
Interactive Test Runner for Labellerr MCP Integration Tests

This script:
1. Checks for required environment variables
2. Prompts user for missing credentials
3. Validates credentials with API
4. Runs pytest integration tests
5. Shows test results summary

Usage:
    python tests/integration/run_mcp_integration_tests.py
"""

import os
import sys
import getpass
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv


def get_project_root():
    """Find the project root directory"""
    current = Path(__file__).resolve()
    # Go up from tests/integration/
    return current.parent.parent.parent


def get_env_file():
    """Get or create .env file path"""
    project_root = get_project_root()
    env_file = project_root / '.env'

    # Try to find existing .env file
    found = find_dotenv(str(project_root))
    if found:
        return found

    return str(env_file)


def check_and_prompt_credentials():
    """
    Check for required environment variables and prompt if missing

    Returns:
        bool: True if all credentials are available, False otherwise
    """
    env_file = get_env_file()
    load_dotenv(env_file)

    required_vars = {
        'LABELLERR_API_KEY': 'API Key',
        'LABELLERR_API_SECRET': 'API Secret',
        'LABELLERR_CLIENT_ID': 'Client ID',
        'LABELLERR_TEST_DATA_PATH': 'Test Data Path (folder with images)'
    }

    print("=" * 60)
    print("Labellerr MCP Integration Tests")
    print("=" * 60)
    print()
    print("Checking credentials...\n")

    missing = []
    found_vars = {}

    for env_var, display_name in required_vars.items():
        value = os.getenv(env_var)
        if not value:
            print(f"❌ {env_var} not found")
            missing.append((env_var, display_name))
        else:
            print(f"✓ {env_var} found")
            found_vars[env_var] = value

    if missing:
        print("\n" + "=" * 60)
        print("Missing Credentials")
        print("=" * 60)
        print("\nPlease provide the following credentials:")
        print("(These will be saved to .env file for future use)\n")

        for env_var, display_name in missing:
            # Use getpass for sensitive fields
            if 'SECRET' in env_var or 'KEY' in env_var:
                value = getpass.getpass(f"{display_name}: ")
            else:
                value = input(f"{display_name}: ")

            if value.strip():
                os.environ[env_var] = value
                found_vars[env_var] = value

                # Save to .env file
                try:
                    # Create .env file if it doesn't exist
                    if not os.path.exists(env_file):
                        with open(env_file, 'w') as f:
                            f.write("# Labellerr API Credentials\n")

                    set_key(env_file, env_var, value)
                    print(f"  ✓ Saved {env_var} to {env_file}")
                except Exception as e:
                    print(f"  ⚠ Warning: Could not save to .env file: {e}")
            else:
                print(f"  ⚠ Warning: {env_var} left empty")

    # Check if all required vars are now available
    all_present = all(os.getenv(var) for var in required_vars.keys())

    if all_present:
        print("\n✓ All credentials configured")
    else:
        print("\n❌ Some credentials are still missing")

    return all_present


def validate_credentials():
    """
    Validate credentials by making a test API call

    Returns:
        bool: True if credentials are valid, False otherwise
    """
    print("\n" + "=" * 60)
    print("Validating Credentials")
    print("=" * 60)
    print("\nTesting API connection...")

    try:
        # Import here to avoid issues if module not found
        sys.path.insert(0, str(get_project_root()))
        from labellerr.mcp_server.api_client import LabellerrAPIClient

        client = LabellerrAPIClient(
            api_key=os.getenv('LABELLERR_API_KEY'),
            api_secret=os.getenv('LABELLERR_API_SECRET'),
            client_id=os.getenv('LABELLERR_CLIENT_ID')
        )

        # Try to list projects as validation
        result = client.list_projects()

        if result and "response" in result:
            print("✓ API connection successful")
            print(f"✓ Found {len(result.get('response', {}).get('projects', []))} projects")
            client.close()
            return True
        else:
            print("❌ API returned unexpected response")
            client.close()
            return False

    except Exception as e:
        print(f"❌ Credential validation failed: {e}")
        print("\nPlease check your credentials and try again.")
        return False


def check_test_data():
    """
    Check if test data path exists and contains files

    Returns:
        bool: True if test data is accessible
    """
    test_data_path = os.getenv('LABELLERR_TEST_DATA_PATH')

    if not test_data_path:
        print("\n⚠ Warning: LABELLERR_TEST_DATA_PATH not set")
        print("  Some tests that require file uploads will be skipped")
        return False

    if not os.path.exists(test_data_path):
        print(f"\n⚠ Warning: Test data path does not exist: {test_data_path}")
        print("  Tests requiring file uploads will be skipped")
        return False

    # Check for image files
    image_extensions = ['.jpg', '.jpeg', '.png', '.tiff']
    files = []
    for ext in image_extensions:
        files.extend(Path(test_data_path).rglob(f'*{ext}'))

    if not files:
        print(f"\n⚠ Warning: No image files found in: {test_data_path}")
        print("  Tests requiring file uploads will be skipped")
        return False

    print(f"\n✓ Test data found: {len(files)} image files in {test_data_path}")
    return True


def run_tests():
    """
    Run pytest integration tests

    Returns:
        int: Exit code from pytest
    """
    print("\n" + "=" * 60)
    print("Running Integration Tests")
    print("=" * 60)
    print()

    try:
        import pytest

        # Get the directory containing this script
        test_dir = Path(__file__).parent
        test_file = test_dir / "test_mcp_server.py"

        # Run pytest with verbose output
        exit_code = pytest.main([
            str(test_file),
            "-v",
            "-s",
            "--tb=short",
            "--color=yes"
        ])

        return exit_code

    except ImportError:
        print("❌ pytest not found. Please install it:")
        print("   pip install pytest pytest-asyncio")
        return 1


def main():
    """Main entry point"""
    # Step 1: Check and prompt for credentials
    if not check_and_prompt_credentials():
        print("\n❌ Cannot proceed without required credentials")
        return 1

    # Step 2: Validate credentials
    if not validate_credentials():
        return 1

    # Step 3: Check test data (warning only, not blocking)
    check_test_data()

    # Step 4: Run tests
    exit_code = run_tests()

    # Step 5: Show summary
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✓ All tests passed!")
    else:
        print(f"❌ Tests failed with exit code: {exit_code}")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
