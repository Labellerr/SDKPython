# Labellerr SDK Test Suite

This directory contains the comprehensive test suite for the Labellerr SDK, organized into unit and integration tests.

## Directory Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── pytest.ini                 # Pytest configuration
├── unit/                       # Unit tests (no external dependencies)
│   ├── test_client.py         # Client validation and parameter tests
│   ├── test_keyframes.py      # KeyFrame functionality tests
│   ├── test_create_dataset_path.py  # Dataset path validation tests
│   └── test_dataset_pagination.py  # Pagination functionality tests
└── integration/               # Integration tests (require real API)
    ├── conftest.py           # Integration-specific fixtures
    ├── test_labellerr_integration.py  # Main integration test suite
    ├── test_sync_datasets.py # Dataset sync operations
    └── ...                   # Other integration test files
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Dependencies**: No external API calls, use mocks and fixtures
- **Speed**: Fast execution
- **Markers**: `@pytest.mark.unit`

### Integration Tests (`tests/integration/`)
- **Purpose**: Test complete workflows with real API calls
- **Dependencies**: Require valid API credentials and external services
- **Speed**: Slower execution due to network calls
- **Markers**: `@pytest.mark.integration`

## Running Tests

### Prerequisites
Set up environment variables in `.env` file:
```bash
API_KEY=your_api_key
API_SECRET=your_api_secret
CLIENT_ID=your_client_id
TEST_EMAIL=test@example.com
```

### Test Commands

```bash
# Run all tests
make test

# Run only unit tests (fast, no credentials needed)
make test-unit

# Run only integration tests (requires credentials)
make test-integration

# Run fast tests only (exclude slow tests)
make test-fast

# Run AWS-specific tests
make test-aws

# Run GCS-specific tests
make test-gcs
```

### Direct pytest commands

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/ -m "unit"

# Integration tests only
pytest tests/integration/ -m "integration"

# Specific test file
pytest tests/unit/test_client.py -v

# Tests with specific marker
pytest tests/ -m "aws" -v
```

## Test Markers

The test suite uses pytest markers to categorize tests:

- `unit`: Unit tests that don't require external dependencies
- `integration`: Integration tests that require real API credentials
- `slow`: Tests that take a long time to run
- `aws`: Tests that require AWS credentials and services
- `gcs`: Tests that require Google Cloud Storage credentials and services
- `skip_ci`: Tests to skip in CI environment

## Writing Tests

### Unit Tests
- Use mocks and fixtures from `conftest.py`
- Test individual functions/methods in isolation
- Focus on edge cases and error handling
- Should run quickly without external dependencies

Example:
```python
@pytest.mark.unit
class TestMyFeature:
    def test_valid_input(self, mock_client):
        # Test with valid input using mock client
        pass
    
    def test_invalid_input_raises_error(self, mock_client):
        # Test error handling
        with pytest.raises(ValidationError):
            # Test code here
            pass
```

### Integration Tests
- Use real API credentials from fixtures
- Test complete workflows end-to-end
- Include proper cleanup and error handling
- Use appropriate markers for external dependencies

Example:
```python
@pytest.mark.integration
@pytest.mark.aws  # If test requires AWS
class TestMyWorkflow:
    def test_complete_workflow(self, integration_client, test_credentials):
        # Test with real API calls
        pass
```

## Fixtures

### Shared Fixtures (from `tests/conftest.py`)
- `test_config`: Test configuration and constants
- `test_credentials`: API credentials from environment
- `mock_client`: Mock client for unit tests
- `integration_client`: Real client for integration tests
- `temp_files`: Helper for creating temporary test files
- `sample_project_payload`: Sample data for project creation

### Integration-Specific Fixtures (from `tests/integration/conftest.py`)
- AWS and GCS specific configuration
- Connection parameters
- Service-specific test data

## Best Practices

1. **Isolation**: Unit tests should not depend on external services
2. **Cleanup**: Integration tests should clean up resources they create
3. **Parameterization**: Use `@pytest.mark.parametrize` for testing multiple scenarios
4. **Descriptive Names**: Test names should clearly describe what is being tested
5. **Documentation**: Include docstrings explaining the test purpose
6. **Error Handling**: Test both success and failure scenarios
7. **Markers**: Use appropriate pytest markers for test categorization

## Troubleshooting

### Common Issues

1. **Missing Credentials**: Set required environment variables in `.env`
2. **Import Errors**: Ensure the SDK is installed in development mode: `pip install -e .`
3. **API Timeouts**: Some integration tests may timeout in slow networks
4. **Resource Conflicts**: Integration tests may conflict if run in parallel

### Debugging Tests

```bash
# Run with verbose output and stop on first failure
pytest tests/ -v -x

# Run specific test with detailed output
pytest tests/unit/test_client.py::TestMyClass::test_my_method -v -s

# Run with pdb debugger on failures
pytest tests/ --pdb
```

## Contributing

When adding new tests:

1. Choose the appropriate directory (`unit/` vs `integration/`)
2. Add proper pytest markers
3. Use existing fixtures when possible
4. Follow the naming conventions
5. Include both positive and negative test cases
6. Update this README if adding new test categories or markers
