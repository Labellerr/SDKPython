# Labellerr MCP Server (Python)

A Python-based Model Context Protocol (MCP) server for the Labellerr SDK. This server provides 22 specialized tools for managing annotation projects, datasets, and monitoring operations through AI assistants like Claude Desktop and Cursor.

## Features

- **🚀 Project Management** - Create, list, update, and track annotation projects
- **📊 Dataset Management** - Create datasets, upload files/folders, and query information
- **🏷️ Annotation Tools** - Upload pre-annotations, export data, and download results
- **📈 Monitoring & Insights** - Real-time progress tracking and system health monitoring
- **🔍 Query Capabilities** - Search projects, get statistics, and analyze operations

## Installation

### Prerequisites

- Python 3.8 or higher
- pip
- Labellerr API credentials (API Key, API Secret, Client ID)

### Setup

1. **Navigate to the SDK directory:**
```bash
cd /Users/sarthak/Documents/SDKPython
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

Create a `.env` file in the SDKPython directory:
```bash
cp .env.example .env
```

Edit `.env` and add your Labellerr credentials:
```env
LABELLERR_API_KEY=your_api_key_here
LABELLERR_API_SECRET=your_api_secret_here
LABELLERR_CLIENT_ID=your_client_id_here
ANTHROPIC_API_KEY=your_anthropic_key_here  # Optional, for testing
```

## Configuration

### Using with Cursor

Add to your Cursor MCP configuration file:

**Location:** `~/.cursor/mcp.json` (macOS/Linux) or `%APPDATA%\Cursor\mcp.json` (Windows)

```json
{
  "mcpServers": {
    "labellerr": {
      "command": "python3",
      "args": ["/Users/sarthak/Documents/SDKPython/labellerr/mcp_server/server.py"],
      "env": {
        "LABELLERR_API_KEY": "your_api_key",
        "LABELLERR_API_SECRET": "your_api_secret",
        "LABELLERR_CLIENT_ID": "your_client_id"
      }
    }
  }
}
```

**Important:** 
- Replace `/Users/sarthak/Documents/SDKPython/` with your actual path if different
- Use absolute paths
- Replace the credential placeholders with your actual credentials

After configuration:
1. Restart Cursor completely (Quit and reopen)
2. The Labellerr tools will be available in the AI assistant
3. Try asking: "List all my Labellerr projects"

### Using with Claude Desktop

Add to your Claude Desktop configuration file:

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "labellerr": {
      "command": "python3",
      "args": ["/Users/sarthak/Documents/SDKPython/labellerr/mcp_server/server.py"],
      "env": {
        "LABELLERR_API_KEY": "your_api_key",
        "LABELLERR_API_SECRET": "your_api_secret",
        "LABELLERR_CLIENT_ID": "your_client_id"
      }
    }
  }
}
```

## Testing

### Using the MCP Client

Test the server using the included MCP client:

```bash
cd /Users/sarthak/Documents/SDKPython
python mcp_client.py labellerr/mcp_server/server.py
```

This will start an interactive chat session where you can test the tools:

```
Query: List all my projects
Query: Check system health
Query: quit
```

### Direct Testing

Run the server directly to verify it starts:

```bash
cd /Users/sarthak/Documents/SDKPython
python3 labellerr/mcp_server/server.py
```

## Available Tools (22 total)

### 📋 Project Management (4 tools)
- `project_create` - Create projects with annotation guidelines
- `project_list` - List all projects
- `project_get` - Get detailed project information
- `project_update_rotation` - Update rotation configuration

### 📊 Dataset Management (5 tools)
- `dataset_create` - Create new datasets
- `dataset_upload_files` - Upload individual files
- `dataset_upload_folder` - Upload entire folders
- `dataset_list` - List all datasets
- `dataset_get` - Get dataset information

### 🏷️ Annotation Operations (5 tools)
- `annotation_upload_preannotations` - Upload pre-annotations (sync)
- `annotation_upload_preannotations_async` - Upload pre-annotations (async)
- `annotation_export` - Create annotation export
- `annotation_check_export_status` - Check export status
- `annotation_download_export` - Get export download URL

### 📈 Monitoring & Analytics (4 tools)
- `monitor_job_status` - Monitor background job status
- `monitor_project_progress` - Track project progress
- `monitor_active_operations` - List active operations
- `monitor_system_health` - Check system health

### 🔍 Query & Search (4 tools)
- `query_project_statistics` - Get detailed project stats
- `query_dataset_info` - Get dataset information
- `query_operation_history` - View operation history
- `query_search_projects` - Search projects by name/type

## Usage Examples

### Via AI Assistant in Cursor

Once configured, you can interact naturally:

**Project Management:**
- "List all my Labellerr projects"
- "Create a new image classification project for product categorization"
- "What's the progress of project XYZ?"

**Dataset Operations:**
- "Upload images from /path/to/folder"
- "List all my datasets"
- "Create a new dataset for video annotation"

**Monitoring:**
- "Show me system health"
- "Check the progress of my active projects"
- "What operations have been performed?"

### Via MCP Client

```python
# Interactive mode
python mcp_client.py labellerr/mcp_server/server.py

# Then type queries like:
Query: List all my projects
Query: Check system health
```

## Architecture

```
SDKPython/
├── labellerr/
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py          # Main MCP server
│   │   ├── tools.py           # Tool definitions
│   │   └── README.md          # This file
│   ├── client.py              # Labellerr SDK client
│   └── ...
├── mcp_client.py              # MCP test client
├── requirements.txt           # Dependencies
└── .env                       # Environment variables
```

## Dependencies

- `mcp` - Model Context Protocol SDK
- `anthropic` - For testing with Claude
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests
- `fastapi` - API framework (for future REST API)
- `uvicorn` - ASGI server (for future REST API)

## Troubleshooting

### Server won't start
- Verify Python version (requires 3.8+)
- Check environment variables are set correctly
- Ensure all dependencies are installed: `pip install -r requirements.txt`

### Tools return errors
- Verify Labellerr API credentials are correct
- Check network connectivity
- Review operation history for error details

### AI assistant can't find tools
- Verify configuration file path is correct
- Use absolute paths, not relative paths
- Restart the AI assistant completely after configuration
- Check that credentials are set in the config file

### Import errors
- Make sure you're in the correct directory
- Verify the Labellerr SDK is properly installed
- Check Python path: `python -c "import sys; print(sys.path)"`

## Development

### Adding New Tools

1. Define the tool schema in `tools.py`
2. Implement the handler in `server.py` (add to appropriate `_handle_*_tool` method)
3. Add the client method in `../client.py` if needed
4. Update documentation

### Running Tests

```bash
cd /Users/sarthak/Documents/SDKPython
pytest tests/
```

## Differences from Node.js Version

This Python implementation provides the same functionality as the Node.js version but with:

- Native integration with the Python Labellerr SDK
- Better async/await support in Python
- Easier to extend with Python libraries
- No Node.js/npm dependencies required
- Simpler deployment for Python-based workflows

## Resources

- **Labellerr Documentation:** [docs.labellerr.com](https://docs.labellerr.com)
- **MCP Protocol:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Support Email:** support@labellerr.com

## License

MIT License - see LICENSE file for details.

---

Made with ❤️ for the Labellerr community


