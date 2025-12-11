# Labellerr MCP Server (Python)
This server provides 22 specialized tools for managing annotation projects, datasets, and monitoring operations through AI assistants like Claude Desktop and Cursor, powered by the Labellerr SDK.

> **⚡ New User?** Check out the [QUICKSTART.md](QUICKSTART.md) for a super simple 5-minute setup guide!

## 🚀 Quick Start (5 minutes)

Want to use Labellerr with your AI assistant? Follow these steps:

### Step 1: Get Your Credentials
You'll need three things from your Labellerr account:
- **API Key**
- **API Secret** 
- **Client ID**

Get these from your Labellerr dashboard at [https://pro.labellerr.com](https://pro.labellerr.com)

### Step 2: Install Dependencies
```bash
cd /path/to/SDKPython
pip install -r requirements.txt
```

### Step 3: Configure Your AI Assistant

**For Cursor:**

1. Open Cursor Settings → Features → Beta → MCP Settings (or find `~/.cursor/mcp.json`)
2. Add this configuration (replace `YOUR_PATH` and credentials):

```json
{
  "mcpServers": {
    "labellerr": {
      "command": "python3",
      "args": ["/YOUR_PATH/SDKPython/labellerr/mcp_server/server.py"],
      "env": {
        "LABELLERR_API_KEY": "your_api_key_here",
        "LABELLERR_API_SECRET": "your_api_secret_here",
        "LABELLERR_CLIENT_ID": "your_client_id_here"
      }
    }
  }
}
```

**For Claude Desktop:**

1. Open `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
2. Add the same configuration as above

### Step 4: Restart and Test

1. **Completely quit** and reopen your AI assistant
2. Try asking: **"List all my Labellerr projects"**
3. You should see your projects! 🎉

### What You Can Do Now

Once configured, talk naturally to your AI assistant:

```
You: "Create a new image annotation project called 'Product Detection' 
     with bounding box annotations"

AI: *Creates project with dataset, annotation template, and project setup*

You: "Upload all images from /Users/me/images/products to a new dataset"

AI: *Uploads files and creates dataset*

You: "What's the progress on project abc123?"

AI: *Shows completion percentage, files annotated, reviewed, etc.*

You: "Export all accepted annotations as COCO JSON"

AI: *Creates export and provides download link*
```

---

## 🚀 Architecture

**SDK Core Implementation**

This MCP server is built directly on top of the Labellerr SDK Core (`labellerr.core`). It exposes the SDK's capabilities through the Model Context Protocol, allowing LLMs to interact with Labellerr's robust infrastructure.

### Benefits

- ✅ **SDK Powered** - Uses the official, tested business logic from the SDK
- ✅ **Unified Logic** - Consistent behavior between your Python scripts and AI assistant
- ✅ **Type Safe** - Leverages Pydantic models and SDK typing
- ✅ **Maintainable** - Updates to the SDK Core automatically benefit the MCP server
- ✅ **Simple Dependencies** - Requires standard SDK dependencies + MCP

### Dependencies

```
labellerr-sdk # Core SDK
mcp           # Model Context Protocol SDK
python-dotenv # Environment variable management
```

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
cd /Users/sarthak/Documents/MCPLabellerr/SDKPython
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

Create a `.env` file in the SDKPython directory:

```bash
# Create .env file
touch .env
```

Edit `.env` and add your Labellerr credentials:

```env
LABELLERR_API_KEY=your_api_key_here
LABELLERR_API_SECRET=your_api_secret_here
LABELLERR_CLIENT_ID=your_client_id_here

# Optional: For integration tests
LABELLERR_TEST_DATA_PATH=/path/to/test/images
```

**Important:** Never commit your `.env` file to version control!

## Configuration

### Using with Cursor

Add to your Cursor MCP configuration file:

**Location:** `~/.cursor/mcp.json` (macOS/Linux) or `%APPDATA%\Cursor\mcp.json` (Windows)

```json
{
  "mcpServers": {
    "labellerr": {
      "command": "python3",
      "args": ["/Users/sarthak/Documents/MCPLabellerr/SDKPython/labellerr/mcp_server/server.py"],
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
- Replace `/Users/sarthak/Documents/MCPLabellerr/SDKPython/` with your actual path if different
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
      "args": ["/Users/sarthak/Documents/MCPLabellerr/SDKPython/labellerr/mcp_server/server.py"],
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

### Running Integration Tests

The integration tests verify the complete workflow using the SDK-based implementation:

```bash
cd /Users/sarthak/Documents/MCPLabellerr/SDKPython
python tests/integration/run_mcp_integration_tests.py
```

The test runner will:
1. Check for required environment variables
2. Prompt for any missing credentials
3. Validate credentials with the API
4. Run comprehensive integration tests
5. Show detailed test results

**Test Coverage:**
- ✅ SDK client initialization
- ✅ Dataset creation with file uploads
- ✅ Annotation template creation
- ✅ Project creation workflow
- ✅ List and query operations
- ✅ Export operations
- ✅ Complete end-to-end workflow

### Direct SDK Client Testing

You can also test the SDK client directly in Python:

```python
from labellerr.core import LabellerrClient
from labellerr.core import projects as project_ops

# Initialize client
client = LabellerrClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    client_id="your_client_id"
)

# List projects
projects = project_ops.list_projects(client)
print(f"Found {len(list(projects))} projects")

# Close client when done (not strictly necessary as it's stateless wrapper)
```

## Three-Step Project Creation Workflow

Projects in Labellerr follow a three-step creation process that aligns with the SDK architecture:

### Step 1: Create or Provide Dataset
- **Upload files and create dataset**, OR
- **Provide existing dataset_id**
- Dataset processing is monitored automatically (status polling)

### Step 2: Create or Provide Annotation Template  
- **Define annotation questions**, OR
- **Provide existing annotation_template_id**

### Step 3: Create Project
- **Links dataset and template together** with rotation config

### Using the `project_create` Tool

The `project_create` tool handles all three steps automatically with built-in status monitoring:

**Option A: Create Everything New (Full Workflow)**
```
You: "Create an image annotation project called 'Product Detection' 
     with files from /Users/me/images/products"

AI will automatically:
1. Upload files to GCS
2. Create dataset
3. Wait for dataset processing (polls status until ready)
4. Create annotation template from your questions
5. Create project linking everything together
```

**Option B: Use Existing Dataset**
```
You: "Create a project using existing dataset abc-123 with bounding box annotations"

AI will automatically:
1. Validate the dataset exists
2. Create annotation template
3. Create project
```

**Option C: Use Existing Template**
```
You: "Create a project with files from /path and existing template def-456"

AI will automatically:
1. Upload files and create dataset
2. Wait for dataset processing
3. Validate the template exists
4. Create project
```

**Option D: Use Both Existing Resources**
```
You: "Create a project using dataset abc-123 and template def-456"

AI will automatically:
1. Validate dataset exists
2. Validate template exists
3. Create project
```

### Using Individual Tools (Granular Control)

For step-by-step control, use separate tools:

1. **Create Dataset:**
   ```
   dataset_create or dataset_upload_folder → get dataset_id
   ```

2. **Check Dataset Status:**
   ```
   dataset_get → check status_code (100=processing, 300=ready, 400+=error)
   ```
   Note: `project_create` does this automatically!

3. **Create Template:**
   ```
   template_create → get template_id
   ```

4. **Create Project:**
   ```
   project_create with dataset_id and template_id
   ```

### Dataset Status Codes

When creating datasets, they are processed asynchronously:
- **100**: Processing (still uploading/indexing files)
- **300**: Ready (dataset is ready to use)
- **400+**: Error (processing failed)

The `project_create` tool automatically waits for status 300 before proceeding.

## Available Tools (23 total)

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

### 🏷️ Annotation Operations (6 tools)
- `template_create` - Create annotation template with questions
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

### Common Use Cases

#### 1. Create a Complete Annotation Project from Scratch

```
You: "I need to create an image annotation project for detecting cats and dogs. 
     I have 100 images in /Users/me/pets folder. Use bounding boxes."

AI will automatically execute the three-step workflow:
✓ Step 1: Upload your 100 images → Create dataset → Wait for processing
✓ Step 2: Create annotation template with bounding box tool
✓ Step 3: Create project linking dataset and template together
✓ Return project ID and confirmation

Note: Dataset processing is monitored automatically - you don't need to manually check status!
```

#### 2. Monitor Project Progress

```
You: "What's the status of all my projects?"

AI will show:
- List of all projects
- Completion percentage for each
- Files annotated, reviewed, accepted
- Data type and creation date
```

#### 3. Bulk Export Annotations

```
You: "Export all accepted annotations from project xyz in COCO JSON format"

AI will:
✓ Create the export job
✓ Monitor the export status
✓ Provide download URL when ready
```

#### 4. Create Reusable Annotation Templates

```
You: "Create an annotation template for vehicle detection with bounding boxes"

AI will:
✓ Create a template with the specified configuration
✓ Return template_id for reuse in multiple projects
✓ Template can be used with different datasets
```

#### 5. Upload Additional Data to Existing Project

```
You: "Upload the images from /Users/me/more-pets to dataset abc123"

AI will:
✓ Scan the folder
✓ Upload all matching files
✓ Add them to the existing dataset
```

#### 6. Search and Query Projects

```
You: "Find all my video annotation projects"

AI will:
✓ Search through all projects
✓ Filter by data type "video"
✓ Show matching projects with details
```

### Direct Python Usage

```python
import asyncio
from labellerr.core import LabellerrClient, datasets as dataset_ops, annotation_templates as template_ops

async def main():
    # Initialize client
    client = LabellerrClient(
        api_key="your_api_key",
        api_secret="your_api_secret",
        client_id="your_client_id"
    )
    
    # Upload files (SDK utility)
    # ... code to get files ...
    
    # Create dataset
    dataset_config = schemas.DatasetConfig(
        dataset_name="My Dataset",
        data_type="image",
        dataset_description="Created via SDK"
    )
    dataset = dataset_ops.create_dataset_from_connection(client, dataset_config, connection_id="...", source="local")
    
    print(f"Dataset created: {dataset.dataset_id}")
    
    # Create annotation template
    questions = [
        # ... AnnotationQuestion objects ...
    ]
    params = schemas.CreateTemplateParams(
        template_name="My Template",
        data_type="image",
        questions=questions
    )
    template = template_ops.create_template(client, params)
    
    print(f"Template created: {template.annotation_template_id}")

# Run logic
```

## Architecture Details

```
SDKPython/
├── labellerr/
│   ├── core/                  # Core SDK Logic
│   │   ├── projects/          # Project operations
│   │   ├── datasets/          # Dataset operations
│   │   └── ...
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py          # Main MCP server (Uses Core SDK)
│   │   ├── tools.py           # Tool definitions
│   │   └── README.md          # This file
│   └── ...
├── tests/
│   ├── integration/
│   │   ├── test_mcp_server.py              # Integration tests
│   │   └── run_mcp_integration_tests.py    # Interactive test runner
│   └── ...
├── .env                       # Environment variables (not in git)
└── requirements.txt           # Dependencies
```

### SDK Core Integration

The `server.py` module integrates directly with `labellerr.core`:

- **Shared Logic**: Uses the same business logic as the main SDK
- **Dataset Status Polling**: Automatically monitors dataset processing using SDK utilities
- **Error Handling**: Maps SDK exceptions to friendly MCP error messages
- **Type Safety**: Uses SDK Pydantic models for data validation

**Key Classes:**
- `LabellerrMCPServer` - Main server class
- `LabellerrClient` - Core SDK client (from `labellerr.core`)

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│             You in Cursor/Claude Desktop                    │
│  "Create an image annotation project"                      │
└──────────────────┬──────────────────────────────────────────┘
                   │ Natural Language
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI Assistant                              │
│  • Understands your intent                                  │
│  • Identifies tool: "project_create"                       │
│  • Extracts parameters                                      │
└──────────────────┬──────────────────────────────────────────┘
                   │ MCP Protocol (JSON-RPC)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              server.py (MCP Server)                        │
│  • Receives tool call request                              │
│  • Orchestrates three-step workflow:                       │
│    1. Upload files → Create dataset → Poll status          │
│    2. Create annotation template                           │
│    3. Create project (links dataset + template)            │
│  • Automatically monitors dataset processing               │
│  • Tracks operation history                                │
│  • Caches results                                          │
└──────────────────┬──────────────────────────────────────────┘
                   │ Uses
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           labellerr.core (SDK Logic)                       │
│  • Validates parameters                                    │
│  • Handles authentication                                  │
│  • Polls dataset status until ready                        │
│  • Manages retries & errors                                │
│  • Uploads files to GCS                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTPS REST API
                   ▼
┌─────────────────────────────────────────────────────────────┐
│          Labellerr API (api.labellerr.com)                 │
│  • Processes requests                                      │
│  • Manages your data                                       │
│  • Returns responses                                       │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### ❌ "AI assistant doesn't show Labellerr tools"

**Problem:** After configuration, you don't see Labellerr tools available.

**Solutions:**
1. **Completely restart** your AI assistant (Quit → Reopen, not just refresh)
2. Check configuration file location:
   - Cursor: `~/.cursor/mcp.json` (macOS/Linux) or `%APPDATA%\Cursor\mcp.json` (Windows)
   - Claude: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
3. Verify your configuration uses **absolute paths**:
   ```json
   "args": ["/full/path/to/SDKPython/labellerr/mcp_server/server.py"]
   ```
4. Test server manually:
   ```bash
   python3 /full/path/to/SDKPython/labellerr/mcp_server/server.py
   ```
   If you see errors, fix them first.

### ❌ "Server starts but tools fail with authentication errors"

**Problem:** Tools return 401 or 403 errors.

**Solutions:**
1. Verify credentials are correct:
   - Log into [https://pro.labellerr.com](https://pro.labellerr.com)
   - Get fresh API Key, API Secret, and Client ID
2. Check credentials in config file (not `.env`!)
3. Make sure there are no extra spaces or quotes in credentials
4. Test credentials with a simple SDK call.

### ❌ "File upload fails"

**Problem:** Uploading files returns errors.

**Solutions:**
1. Verify file paths exist and are readable:
   ```bash
   ls -la /path/to/your/files
   ```
2. Check file extensions match data type:
   - Image: `.jpg`, `.jpeg`, `.png`, `.tiff`
   - Video: `.mp4`
   - Audio: `.mp3`, `.wav`
   - Document: `.pdf`
3. Ensure internet connection for GCS uploads
4. Check file permissions (must be readable)

### ❌ "Python version or dependency errors"

**Problem:** Server won't start due to Python or package issues.

**Solutions:**
1. Check Python version (need 3.8+):
   ```bash
   python3 --version
   ```
2. Install dependencies:
   ```bash
   cd /path/to/SDKPython
   pip install -r requirements.txt
   ```
3. If using virtual environment, make sure it's activated
4. Try reinstalling packages:
   ```bash
   pip install --upgrade -r requirements.txt
   ```

### ❌ "Rate limit errors (429)"

**Problem:** Getting "Too Many Requests" errors.

**Solutions:**
1. Wait a few minutes before retrying
2. Reduce frequency of requests
3. The SDK client has automatic retry built-in
4. Contact support if limits are too restrictive

### 🐛 Enable Debug Logging

If you're still having issues, enable detailed logging:

1. Add to your MCP config:
   ```json
   "env": {
     "LABELLERR_API_KEY": "...",
     "LABELLERR_API_SECRET": "...",
     "LABELLERR_CLIENT_ID": "...",
     "LOG_LEVEL": "DEBUG"
   }
   ```

2. Restart AI assistant and check logs

3. Logs go to stderr - check your AI assistant's console/logs

## Frequently Asked Questions (FAQ)

### Q: Do I need to install the full Labellerr SDK?
**A:** Yes, the MCP server is part of the SDK package. Just install the requirements.

### Q: Can I use this with multiple AI assistants?
**A:** Yes! You can configure it in both Cursor and Claude Desktop (or any MCP-compatible client). Just add the configuration to each one.

### Q: Where do I get my API credentials?
**A:** Log into your Labellerr account at [https://pro.labellerr.com](https://pro.labellerr.com) and navigate to your account settings or API section to generate credentials.

### Q: Does this work on Windows?
**A:** Yes! Just use Windows paths in your configuration:
```json
"args": ["C:\\path\\to\\SDKPython\\labellerr\\mcp_server\\server.py"]
```
And the config file location is `%APPDATA%\Cursor\mcp.json`

### Q: Can I use this server from regular Python code (not just AI assistants)?
**A:** You should use the `labellerr.core` SDK modules directly for Python code, which gives you better control and type safety than calling the MCP server.

### Q: What happens if my API credentials change?
**A:** Update your AI assistant's MCP configuration file with new credentials and restart the assistant.

### Q: Can I limit which tools are available?
**A:** Currently, all 22 tools are exposed. If you need custom filtering, you can modify `tools.py` to remove unwanted tools from `ALL_TOOLS`.

### Q: Is my data secure?
**A:** Yes! All communication uses HTTPS. Your credentials are stored locally in your MCP config. The server only runs locally on your machine and communicates directly with Labellerr's API.

### Q: How do I update to the latest version?
**A:** Pull the latest code from the repository and reinstall dependencies:
```bash
git pull
pip install -r requirements.txt
```
Then restart your AI assistant.

### Q: Can I run this on a remote server?
**A:** The current implementation uses STDIO (standard input/output) for communication, which requires local execution. For remote deployment, you'd need to modify it to use HTTP transport instead.

### Q: What annotation types are supported?
**A:** All Labellerr annotation types:
- Bounding Box
- Polygon
- Dot/Point
- Classification (radio, checkbox, dropdown)
- Text input
- Audio annotation
- Video frame annotation

### Q: How do I report bugs or request features?
**A:** Open an issue in the repository or contact Labellerr support at support@labellerr.com

## License

MIT License - see LICENSE file for details.

---

**SDK Core Implementation** - Powerful, Type-Safe, and Maintainable • Built with ❤️ for the Labellerr community
