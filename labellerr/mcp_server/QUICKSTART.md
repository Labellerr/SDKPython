# Labellerr MCP Server - Quick Start Guide

Get up and running in 5 minutes! 🚀

## What You'll Need

1. **Python 3.8+** installed on your computer
2. **Labellerr account** with API credentials
3. **Cursor** or **Claude Desktop** installed

## Step 1: Get Your Credentials (2 minutes)

1. Go to [https://pro.labellerr.com](https://pro.labellerr.com)
2. Log in to your account
3. Find your API settings and copy:
   - **API Key**
   - **API Secret**
   - **Client ID**

Keep these handy - you'll need them in Step 3!

## Step 2: Install (1 minute)

Open your terminal and run:

```bash
cd /path/to/SDKPython
pip install -r requirements.txt
```

That's it! No complex setup needed.

## Step 3: Configure Your AI Assistant (2 minutes)

### For Cursor:

1. Open Cursor
2. Go to **Settings** → **Features** → **Beta** → **MCP Settings**
3. Or directly edit: `~/.cursor/mcp.json`
4. Add this (replace the placeholders):

```json
{
  "mcpServers": {
    "labellerr": {
      "command": "python3",
      "args": ["/FULL/PATH/TO/SDKPython/labellerr/mcp_server/server.py"],
      "env": {
        "LABELLERR_API_KEY": "paste_your_api_key_here",
        "LABELLERR_API_SECRET": "paste_your_api_secret_here",
        "LABELLERR_CLIENT_ID": "paste_your_client_id_here"
      }
    }
  }
}
```

**Important:** Use the FULL path! For example:
- macOS: `/Users/yourname/Documents/SDKPython/labellerr/mcp_server/server.py`
- Windows: `C:\\Users\\yourname\\Documents\\SDKPython\\labellerr\\mcp_server\\server.py`

### For Claude Desktop:

Same config, but put it in:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Step 4: Test It! (1 minute)

1. **Completely quit** and reopen your AI assistant (restart is important!)
2. In your AI chat, type:

```
List all my Labellerr projects
```

3. You should see your projects! 🎉

If you get an error, see [Troubleshooting](#troubleshooting) below.

## What Can You Do Now?

Just talk naturally to your AI assistant:

### Create Projects
```
Create an image annotation project called "Product Detection" 
with bounding boxes. Upload images from /Users/me/photos
```

### Check Progress
```
What's the status of all my projects?
```

### Upload Data
```
Upload all images from /Users/me/more-images to dataset xyz123
```

### Export Results
```
Export all accepted annotations from project abc123 in COCO JSON format
```

### Get Help
```
What Labellerr tools do you have available?
```

## Common Commands

| What You Want | What To Say |
|---------------|-------------|
| See all projects | "List all my Labellerr projects" |
| Create a project | "Create a new [type] project for [purpose]" |
| Upload files | "Upload [files/folder] to [dataset/new dataset]" |
| Check progress | "What's the progress on project [id/name]?" |
| Export data | "Export annotations from project [id] as [format]" |
| Search projects | "Find all my [video/image/...] projects" |

## Troubleshooting

### "AI doesn't show Labellerr tools"

1. Did you **completely restart** your AI assistant? (Quit → Reopen)
2. Is your path absolute? (must start with `/` or `C:\`)
3. Try running manually:
   ```bash
   python3 /your/full/path/to/server.py
   ```
   If you see errors, fix those first.

### "Authentication error" or "401/403"

Your credentials are wrong or expired:
1. Get fresh credentials from [https://pro.labellerr.com](https://pro.labellerr.com)
2. Update your config file
3. Restart your AI assistant

### "File not found" errors

Check your path is correct:
```bash
ls -la /your/full/path/to/server.py
```
If the file exists, you're good. Copy that exact path to your config.

### "Python not found"

Make sure Python 3.8+ is installed:
```bash
python3 --version
```

### Still stuck?

1. Check the full [README.md](README.md) for detailed troubleshooting
2. Enable debug logging (add `"LOG_LEVEL": "DEBUG"` to your env config)
3. Contact support at support@labellerr.com

## Next Steps

- Read the full [README.md](README.md) for all features and tools
- Check out [example use cases](README.md#common-use-cases)
- Learn about [direct Python usage](README.md#direct-python-usage)

---

**Questions?** Check the [FAQ](README.md#frequently-asked-questions-faq) or the full [README](README.md)

**Happy annotating! 🎯**





