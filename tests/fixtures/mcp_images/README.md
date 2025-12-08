# Test Images for MCP Integration Tests

This folder contains sample images used for MCP dataset creation tests.

## Images

Add 2-3 sample images (JPG, JPEG, or PNG) to this folder for testing:
- Dataset upload functionality
- Complete end-to-end workflow tests

## Usage

The CI workflow sets `LABELLERR_TEST_DATA_PATH` environment variable to point to this folder.
Tests automatically discover and use images from here.



