#!/usr/bin/env python3
"""
Test Runner for MCP Server Integration Tests

This script runs all integration tests for the Labellerr MCP Server.
It tests all 23 tools to ensure the server is working correctly.

Usage:
    python tests/integration/run_mcp_tools_tests.py

    Or with specific test class:
    python tests/integration/run_mcp_tools_tests.py TestProjectTools

    Or with specific test:
    python tests/integration/run_mcp_tools_tests.py TestProjectTools::test_project_list

Environment Variables Required:
    LABELLERR_API_KEY
    LABELLERR_API_SECRET
    LABELLERR_CLIENT_ID
    LABELLERR_TEST_DATA_PATH (optional, for file upload tests)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Check environment variables
required_vars = ['LABELLERR_API_KEY', 'LABELLERR_API_SECRET', 'LABELLERR_CLIENT_ID']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print("❌ Missing required environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nPlease set these variables before running tests.")
    print("\nExample:")
    print("  export LABELLERR_API_KEY='your_key'")
    print("  export LABELLERR_API_SECRET='your_secret'")
    print("  export LABELLERR_CLIENT_ID='your_client_id'")
    sys.exit(1)

# Optional test data path
test_data_path = os.getenv('LABELLERR_TEST_DATA_PATH')
if test_data_path:
    print(f"ℹ️  Test data path: {test_data_path}")
else:
    print("ℹ️  No test data path provided - file upload tests will be skipped")
    print("   Set LABELLERR_TEST_DATA_PATH to enable file upload tests")

print("\n" + "="*80)
print("LABELLERR MCP SERVER - INTEGRATION TESTS")
print("="*80)
print(f"\nAPI Key: {os.getenv('LABELLERR_API_KEY')[:10]}...")
print(f"Client ID: {os.getenv('LABELLERR_CLIENT_ID')}")
print("="*80 + "\n")

# Run pytest
import pytest

# Build pytest args
pytest_args = [
    'tests/integration/test_mcp_tools.py',
    '-v',           # Verbose
    '-s',           # Show print statements
    '--tb=short',   # Short traceback format
    '--color=yes',  # Colored output
]

# Add any command line arguments
if len(sys.argv) > 1:
    # User specified specific test(s)
    test_filter = sys.argv[1]
    pytest_args.append(f'-k={test_filter}')
    print(f"Running tests matching: {test_filter}\n")

# Run tests
exit_code = pytest.main(pytest_args)

# Print summary
print("\n" + "="*80)
if exit_code == 0:
    print("✅ ALL TESTS PASSED!")
else:
    print("❌ SOME TESTS FAILED")
print("="*80 + "\n")

sys.exit(exit_code)
