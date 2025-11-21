#!/usr/bin/env python3
"""
Labellerr MCP Server - Pure API Implementation

A Model Context Protocol server for the Labellerr platform that makes
direct REST API calls, completely independent of SDK implementation.
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

# Import the pure API client (no SDK dependencies)
try:
    from .api_client import LabellerrAPIClient, LabellerrAPIError
except ImportError:
    # If running as a script, use absolute import
    from api_client import LabellerrAPIClient, LabellerrAPIError

# Import tool definitions
try:
    from .tools import ALL_TOOLS
except ImportError:
    from tools import ALL_TOOLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


class LabellerrMCPServer:  # main server object
    """MCP Server for Labellerr - Pure API Implementation"""

    def __init__(self):
        self.server = Server("labellerr-mcp-server")
        self.api_client: Optional[LabellerrAPIClient] = None
        self.client_id: Optional[str] = None
        self.operation_history: List[Dict[str, Any]] = []
        self.active_projects: Dict[str, Dict[str, Any]] = {}
        self.active_datasets: Dict[str, Dict[str, Any]] = {}

        # Initialize API client
        self._initialize_client()

        # Setup request handlers
        self._setup_handlers()

    def _initialize_client(self):
        """Initialize Labellerr API client with credentials from environment"""
        api_key = os.getenv("LABELLERR_API_KEY")
        api_secret = os.getenv("LABELLERR_API_SECRET")
        self.client_id = os.getenv("LABELLERR_CLIENT_ID")

        if not all([api_key, api_secret, self.client_id]):
            logger.error(
                "Missing required environment variables. "
                "Please set LABELLERR_API_KEY, LABELLERR_API_SECRET, and LABELLERR_CLIENT_ID"
            )
            return

        try:
            self.api_client = LabellerrAPIClient(
                api_key=api_key,
                api_secret=api_secret,
                client_id=self.client_id
            )
            logger.info("Labellerr API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Labellerr API client: {e}")

    def _setup_handlers(self):
        """Setup MCP request handlers"""

        @self.server.list_tools()  # list all available tools
        async def list_tools() -> list[Tool]:
            """List all available tools"""
            return [
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"]
                )
                for tool in ALL_TOOLS
            ]

        @self.server.call_tool()  # execute a tool
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool execution"""
            if not self.api_client:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "API client not initialized. Please check environment variables."
                    }, indent=2)
                )]

            try:
                # Route to appropriate handler based on tool category
                if name.startswith("project_"):
                    result = await self._handle_project_tool(name, arguments)
                elif name.startswith("dataset_"):
                    result = await self._handle_dataset_tool(name, arguments)
                elif name.startswith("annotation_"):
                    result = await self._handle_annotation_tool(name, arguments)
                elif name.startswith("monitor_"):
                    result = await self._handle_monitoring_tool(name, arguments)
                elif name.startswith("query_"):
                    result = await self._handle_query_tool(name, arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            except LabellerrAPIError as e:
                logger.error(f"API error in tool execution: {e}", exc_info=True)

                # Log operation for history
                self.operation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "tool": name,
                    "status": "failed",
                    "error": str(e),
                    "status_code": e.status_code
                })

                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"API Error {e.status_code}: {e.message}",
                        "details": e.response_data
                    }, indent=2)
                )]

            except Exception as e:
                logger.error(f"Tool execution failed: {e}", exc_info=True)

                # Log operation for history
                self.operation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "tool": name,
                    "status": "failed",
                    "error": str(e)
                })

                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Tool execution failed: {str(e)}"
                    }, indent=2)
                )]

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available resources"""
            resources = []

            # Add active projects as resources
            for project_id, project in self.active_projects.items():
                resources.append(Resource(
                    uri=f"labellerr://project/{project_id}",
                    name=project.get("project_name", project_id),
                    mimeType="application/json",
                    description=f"Project: {project.get('project_name', project_id)} ({project.get('data_type', 'unknown')})"
                ))

            # Add active datasets as resources
            for dataset_id, dataset in self.active_datasets.items():
                resources.append(Resource(
                    uri=f"labellerr://dataset/{dataset_id}",
                    name=dataset.get("name", dataset_id),
                    mimeType="application/json",
                    description=f"Dataset: {dataset.get('name', dataset_id)}"
                ))

            # Add operation history as a resource
            resources.append(Resource(
                uri="labellerr://history",
                name="Operation History",
                mimeType="application/json",
                description="History of all operations performed"
            ))

            return resources

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource content"""
            if uri == "labellerr://history":
                return json.dumps(self.operation_history, indent=2)

            # Parse URI
            parts = uri.split("/")
            if len(parts) >= 4 and parts[0] == "labellerr:":
                resource_type = parts[2]
                resource_id = parts[3]

                if resource_type == "project" and resource_id in self.active_projects:
                    return json.dumps(self.active_projects[resource_id], indent=2)
                elif resource_type == "dataset" and resource_id in self.active_datasets:
                    return json.dumps(self.active_datasets[resource_id], indent=2)

            raise ValueError(f"Resource not found: {uri}")

    async def _handle_project_tool(self, name: str, args: dict) -> dict:
        """Handle project management tools using direct API calls"""
        start_time = datetime.now()
        result = {}

        try:
            if name == "project_create":
                # Simplified project creation - requires dataset_id and template_id
                # This enforces an explicit three-step workflow:
                # Step 1: User creates dataset → gets dataset_id
                # Step 2: User creates template → gets template_id
                # Step 3: User creates project with both IDs

                dataset_id = args.get("dataset_id")
                template_id = args.get("annotation_template_id")

                # Require both IDs to be provided
                if not dataset_id:
                    return {
                        "error": "dataset_id is required",
                        "message": "Please create a dataset first using one of these tools:",
                        "workflow": {
                            "step_1": "Create dataset with files: dataset_upload_folder or dataset_upload_files",
                            "step_2": "Create annotation template: template_create",
                            "step_3": "Create project: project_create (with dataset_id and annotation_template_id)"
                        },
                        "example": {
                            "step_1_tool": "dataset_upload_folder",
                            "step_1_args": {
                                "folder_path": "/path/to/images",
                                "data_type": "image"
                            },
                            "step_2_tool": "template_create",
                            "step_2_args": {
                                "template_name": "My Template",
                                "data_type": "image",
                                "questions": [{"question": "Label", "question_type": "BoundingBox", "required": True}]
                            },
                            "step_3_tool": "project_create",
                            "step_3_args": {
                                "project_name": "My Project",
                                "data_type": "image",
                                "dataset_id": "<from_step_1>",
                                "annotation_template_id": "<from_step_2>",
                                "created_by": "user@example.com"
                            }
                        }
                    }

                if not template_id:
                    return {
                        "error": "annotation_template_id is required",
                        "message": "Please create an annotation template first using template_create tool",
                        "workflow": {
                            "step_1": "✓ Dataset created (dataset_id provided)",
                            "step_2": "Create annotation template: template_create",
                            "step_3": "Create project: project_create (with dataset_id and annotation_template_id)"
                        },
                        "example": {
                            "tool": "template_create",
                            "args": {
                                "template_name": "My Template",
                                "data_type": args.get("data_type", "image"),
                                "questions": [
                                    {
                                        "question_number": 1,
                                        "question": "Object Detection",
                                        "question_type": "BoundingBox",
                                        "required": True,
                                        "options": [{"option_name": "Object"}],
                                        "color": "#FF0000"
                                    }
                                ]
                            }
                        }
                    }

                # Validate dataset exists and is ready
                logger.info(f"Validating dataset {dataset_id}...")
                try:
                    dataset_info = await asyncio.to_thread(
                        self.api_client.get_dataset,
                        dataset_id
                    )

                    dataset_status = dataset_info.get("response", {}).get("status_code")
                    if dataset_status != 300:
                        return {
                            "error": f"Dataset {dataset_id} is not ready",
                            "dataset_id": dataset_id,
                            "status_code": dataset_status,
                            "message": "Dataset is still processing. Please wait and try again.",
                            "hint": "You can check dataset status using dataset_get tool"
                        }

                    logger.info(f"✓ Dataset {dataset_id} is ready")
                except Exception as e:
                    return {
                        "error": f"Failed to validate dataset {dataset_id}",
                        "details": str(e)
                    }

                # Create project (Step 3)
                logger.info(f"Creating project '{args['project_name']}'...")

                rotations = args.get("rotation_config", {
                    "annotation_rotation_count": 1,
                    "review_rotation_count": 1,
                    "client_review_rotation_count": 1
                })

                result = await asyncio.to_thread(
                    self.api_client.create_project,
                    project_name=args["project_name"],
                    data_type=args["data_type"],
                    attached_datasets=[dataset_id],
                    annotation_template_id=template_id,
                    rotations=rotations,
                    use_ai=args.get("autolabel", False),
                    created_by=args.get("created_by")
                )

                # Cache the project
                if result.get("response", {}).get("project_id"):
                    project_id = result["response"]["project_id"]
                    self.active_projects[project_id] = {
                        "project_id": project_id,
                        "project_name": args["project_name"],
                        "data_type": args["data_type"],
                        "dataset_id": dataset_id,
                        "template_id": template_id,
                        "created_at": datetime.now().isoformat()
                    }
                    logger.info(f"✓ Project created successfully: {project_id}")

                    # Add helpful response
                    result["workflow_completed"] = {
                        "step_1": f"✓ Dataset: {dataset_id}",
                        "step_2": f"✓ Template: {template_id}",
                        "step_3": f"✓ Project: {project_id}"
                    }

            elif name == "project_list":
                result = await asyncio.to_thread(self.api_client.list_projects)

                # Update active projects cache
                # Note: API returns list directly in response, not wrapped in "projects" key
                if result.get("response") and isinstance(result["response"], list):
                    for project in result["response"]:
                        project_id = project.get("project_id")
                        if project_id:
                            self.active_projects[project_id] = project

            elif name == "project_get":
                result = await asyncio.to_thread(
                    self.api_client.get_project,
                    args["project_id"]
                )

                # Update cache
                if result.get("response"):
                    self.active_projects[args["project_id"]] = result["response"]

            elif name == "project_update_rotation":
                result = await asyncio.to_thread(
                    self.api_client.update_project_rotations,
                    args["project_id"],
                    args["rotation_config"]
                )

            else:
                result = {"error": f"Unknown project tool: {name}"}

            # Log successful operation
            self.operation_history.append({
                "timestamp": datetime.now().isoformat(),
                "tool": name,
                "duration": (datetime.now() - start_time).total_seconds(),
                "status": "success",
                "args": {k: v for k, v in args.items() if k not in ["files_to_upload", "folder_to_upload"]}
            })

            return result

        except Exception as e:
            logger.error(f"Project tool error: {e}", exc_info=True)
            raise

    async def _handle_dataset_tool(self, name: str, args: dict) -> dict:
        """Handle dataset management tools using direct API calls"""
        start_time = datetime.now()
        result = {}

        try:
            if name == "dataset_create":
                # Complete dataset creation workflow with automatic file upload and status polling
                connection_id = args.get("connection_id")

                # STEP 1: Upload files if folder_path or files provided
                if not connection_id:
                    if args.get("folder_path"):
                        logger.info(f"[1/3] Uploading files from {args['folder_path']}...")
                        connection_id = await asyncio.to_thread(
                            self.api_client.upload_folder_to_connector,
                            args["folder_path"],
                            args["data_type"]
                        )
                        logger.info(f"✓ Files uploaded! Connection ID: {connection_id}")
                    elif args.get("files"):
                        logger.info(f"[1/3] Uploading {len(args['files'])} files...")
                        connection_id = await asyncio.to_thread(
                            self.api_client.upload_files_to_connector,
                            args["files"]
                        )
                        logger.info(f"✓ Files uploaded! Connection ID: {connection_id}")
                    else:
                        return {
                            "error": "Either connection_id, folder_path, or files must be provided",
                            "hint": "Provide folder_path to upload an entire folder, or files array for specific files"
                        }

                # STEP 2: Create dataset with connection_id
                logger.info(f"[2/3] Creating dataset '{args['dataset_name']}'...")
                result = await asyncio.to_thread(
                    self.api_client.create_dataset,
                    dataset_name=args["dataset_name"],
                    data_type=args["data_type"],
                    dataset_description=args.get("dataset_description", ""),
                    connection_id=connection_id
                )

                dataset_id = result.get("response", {}).get("dataset_id")
                if not dataset_id:
                    return {"error": "Failed to create dataset", "details": result}

                logger.info(f"✓ Dataset created! Dataset ID: {dataset_id}")

                # STEP 3: Wait for dataset processing (default: enabled)
                if args.get("wait_for_processing", True):
                    logger.info("[3/3] Waiting for dataset to be processed...")
                    try:
                        dataset_status = await asyncio.to_thread(
                            self.api_client.poll_dataset_status,
                            dataset_id,
                            interval=2.0,
                            timeout=args.get("processing_timeout", 300)
                        )

                        status_code = dataset_status.get("response", {}).get("status_code")
                        files_count = dataset_status.get("response", {}).get("files_count", 0)

                        if status_code == 300:
                            logger.info(f"✓ Dataset ready! Files: {files_count}")
                            result["files_count"] = files_count
                            result["status"] = "ready"
                            result["status_code"] = 300
                        else:
                            logger.warning(f"Dataset processing completed with status {status_code}")
                            result["status_code"] = status_code
                            result["status"] = "processing_failed"
                    except Exception as e:
                        logger.error(f"Error waiting for dataset processing: {e}")
                        result["warning"] = f"Dataset created but processing status unknown: {str(e)}"
                        result["status"] = "unknown"

                # Cache the dataset
                if dataset_id:
                    self.active_datasets[dataset_id] = {
                        "dataset_id": dataset_id,
                        "name": args["dataset_name"],
                        "data_type": args["data_type"],
                        "created_at": datetime.now().isoformat()
                    }

            elif name == "dataset_upload_files":
                connection_id = await asyncio.to_thread(
                    self.api_client.upload_files_to_connector,
                    args["files"]
                )
                result = {"connection_id": connection_id, "success": True}

            elif name == "dataset_upload_folder":
                connection_id = await asyncio.to_thread(
                    self.api_client.upload_folder_to_connector,
                    args["folder_path"],
                    args["data_type"]
                )
                result = {"connection_id": connection_id, "success": True}

            elif name == "dataset_list":
                data_type = args.get("data_type", "image")
                scope = args.get("scope", "client")
                result = await asyncio.to_thread(
                    self.api_client.list_datasets,
                    data_type=data_type,
                    scope=scope
                )

                # Update datasets cache
                if result.get("response", {}).get("datasets"):
                    for dataset in result["response"]["datasets"]:
                        dataset_id = dataset.get("dataset_id")
                        if dataset_id:
                            self.active_datasets[dataset_id] = dataset

            elif name == "dataset_get":
                result = await asyncio.to_thread(
                    self.api_client.get_dataset,
                    args["dataset_id"]
                )

                # Update cache
                if result.get("response"):
                    self.active_datasets[args["dataset_id"]] = result["response"]

            else:
                result = {"error": f"Unknown dataset tool: {name}"}

            self.operation_history.append({
                "timestamp": datetime.now().isoformat(),
                "tool": name,
                "duration": (datetime.now() - start_time).total_seconds(),
                "status": "success"
            })

            return result

        except Exception as e:
            logger.error(f"Dataset tool error: {e}", exc_info=True)
            raise

    async def _handle_annotation_tool(self, name: str, args: dict) -> dict:
        """Handle annotation tools using direct API calls"""
        start_time = datetime.now()
        result = {}

        try:
            if name == "template_create":
                logger.info(f"Creating annotation template: {args['template_name']}")
                result = await asyncio.to_thread(
                    self.api_client.create_annotation_template,
                    template_name=args["template_name"],
                    data_type=args["data_type"],
                    questions=args["questions"]
                )

                # Log success
                if result.get("response", {}).get("template_id"):
                    template_id = result["response"]["template_id"]
                    logger.info(f"Template created successfully: {template_id}")

            elif name == "annotation_export":
                result = await asyncio.to_thread(
                    self.api_client.create_export,
                    project_id=args["project_id"],
                    export_name=args["export_name"],
                    export_description=args.get("export_description", ""),
                    export_format=args["export_format"],
                    statuses=args["statuses"]
                )

            elif name == "annotation_check_export_status":
                result = await asyncio.to_thread(
                    self.api_client.check_export_status,
                    project_id=args["project_id"],
                    report_ids=args["export_ids"]
                )

            elif name == "annotation_download_export":
                result = await asyncio.to_thread(
                    self.api_client.get_export_download_url,
                    project_id=args["project_id"],
                    export_id=args["export_id"]
                )

            else:
                result = {"error": f"Unknown annotation tool: {name}"}

            self.operation_history.append({
                "timestamp": datetime.now().isoformat(),
                "tool": name,
                "duration": (datetime.now() - start_time).total_seconds(),
                "status": "success"
            })

            return result

        except Exception as e:
            logger.error(f"Annotation tool error: {e}", exc_info=True)
            raise

    async def _handle_monitoring_tool(self, name: str, args: dict) -> dict:
        """Handle monitoring tools"""
        result = {}

        try:
            if name == "monitor_job_status":
                # Return mock status - would need specific API endpoint
                result = {
                    "success": True,
                    "job_id": args["job_id"],
                    "status": "This feature requires specific job tracking API",
                    "message": "Use check_export_status for export jobs"
                }

            elif name == "monitor_project_progress":
                # Get project details for progress
                project_result = await asyncio.to_thread(
                    self.api_client.get_project,
                    args["project_id"]
                )
                result = project_result

            elif name == "monitor_active_operations":
                # Return current active operations from history
                recent_ops = [
                    op for op in self.operation_history[-50:]  # Last 50 ops
                ]
                result = {
                    "active_operations": recent_ops,
                    "total_operations": len(self.operation_history)
                }

            elif name == "monitor_system_health":
                result = {
                    "status": "healthy",
                    "connected": self.api_client is not None,
                    "active_projects": len(self.active_projects),
                    "active_datasets": len(self.active_datasets),
                    "operations_performed": len(self.operation_history),
                    "last_operation": self.operation_history[-1] if self.operation_history else None
                }

            else:
                result = {"error": f"Unknown monitoring tool: {name}"}

            return result

        except Exception as e:
            logger.error(f"Monitoring tool error: {e}", exc_info=True)
            raise

    async def _handle_query_tool(self, name: str, args: dict) -> dict:
        """Handle query tools"""
        result = {}

        try:
            if name == "query_project_statistics":
                # Get project details
                project_result = await asyncio.to_thread(
                    self.api_client.get_project,
                    args["project_id"]
                )

                project = project_result.get("response", {})
                result = {
                    "project_id": args["project_id"],
                    "project_name": project.get("project_name", ""),
                    "data_type": project.get("data_type", ""),
                    "total_files": project.get("total_files", 0),
                    "annotated_files": project.get("annotated_files", 0),
                    "reviewed_files": project.get("reviewed_files", 0),
                    "accepted_files": project.get("accepted_files", 0),
                    "completion_percentage": project.get("completion_percentage", 0)
                }

            elif name == "query_dataset_info":
                result = await asyncio.to_thread(
                    self.api_client.get_dataset,
                    args["dataset_id"]
                )

            elif name == "query_operation_history":
                limit = args.get("limit", 10)
                status = args.get("status")

                history = self.operation_history.copy()
                if status:
                    history = [op for op in history if op.get("status") == status]

                result = {
                    "total": len(history),
                    "operations": list(reversed(history[-limit:]))
                }

            elif name == "query_search_projects":
                # Get all projects and filter
                projects_result = await asyncio.to_thread(
                    self.api_client.list_projects
                )

                query = args["query"].lower()
                # Note: API returns list directly in response, not wrapped in "projects" key
                projects = projects_result.get("response", [])
                if isinstance(projects, dict):
                    projects = projects.get("projects", [])

                result = {
                    "projects": [
                        p for p in projects
                        if (query in p.get("project_name", "").lower() or query in p.get("data_type", "").lower())
                    ]
                }

            else:
                result = {"error": f"Unknown query tool: {name}"}

            return result

        except Exception as e:
            logger.error(f"Query tool error: {e}", exc_info=True)
            raise

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Labellerr MCP Server (Pure API Implementation)...")
        logger.info(f"Connected to Labellerr API: {self.api_client is not None}")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    server = LabellerrMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
