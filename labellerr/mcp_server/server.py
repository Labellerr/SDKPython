#!/usr/bin/env python3
"""
Labellerr MCP Server - SDK Core Implementation

A Model Context Protocol server for the Labellerr platform that uses
the SDK core module for all API operations.
"""

import os
import sys
import json
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

# Import SDK core modules
from labellerr.core import LabellerrClient
from labellerr.core.exceptions import LabellerrError
from labellerr.core import datasets as dataset_ops
from labellerr.core import projects as project_ops
from labellerr.core import annotation_templates as template_ops
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.datasets.base import LabellerrDatasetMeta
from labellerr.core.datasets.utils import upload_files, upload_folder_files_to_dataset
from labellerr.core.projects import LabellerrProject
from labellerr.core.projects.base import LabellerrProjectMeta
from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
from labellerr.core import schemas
from labellerr.core.schemas.annotation_templates import (
    CreateTemplateParams as TemplateParams,
    AnnotationQuestion,
    QuestionType,
    Option,
)

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


class LabellerrMCPServer:
    """MCP Server for Labellerr - SDK Core Implementation"""

    def __init__(self):
        self.server = Server("labellerr-mcp-server")
        self.client: Optional[LabellerrClient] = None
        self.client_id: Optional[str] = None
        self.operation_history: List[Dict[str, Any]] = []
        self.active_projects: Dict[str, Dict[str, Any]] = {}
        self.active_datasets: Dict[str, Dict[str, Any]] = {}

        # Initialize SDK client
        self._initialize_client()

        # Setup request handlers
        self._setup_handlers()

    def _initialize_client(self):
        """Initialize Labellerr SDK client with credentials from environment"""
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
            self.client = LabellerrClient(
                api_key=api_key,
                api_secret=api_secret,
                client_id=self.client_id
            )
            logger.info("Labellerr SDK client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Labellerr SDK client: {e}")

    def _setup_handlers(self):
        """Setup MCP request handlers"""

        @self.server.list_tools()
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

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool execution"""
            if not self.client:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "SDK client not initialized. Please check environment variables."
                    }, indent=2)
                )]

            try:
                # Route to appropriate handler based on tool category
                if name.startswith("project_"):
                    result = await self._handle_project_tool(name, arguments)
                elif name.startswith("dataset_"):
                    result = await self._handle_dataset_tool(name, arguments)
                elif name.startswith("annotation_") or name == "template_create":
                    result = await self._handle_annotation_tool(name, arguments)
                elif name.startswith("monitor_"):
                    result = await self._handle_monitoring_tool(name, arguments)
                elif name.startswith("query_"):
                    result = await self._handle_query_tool(name, arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]

            except LabellerrError as e:
                logger.error(f"SDK error in tool execution: {e}", exc_info=True)

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
                        "error": f"SDK Error: {str(e)}"
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
                    description=(f"Project: {project.get('project_name', project_id)} "
                                 f"({project.get('data_type', 'unknown')})")
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
        """Handle project management tools using SDK core"""
        start_time = datetime.now()
        result = {}

        try:
            if name == "project_create":
                # Simplified project creation - requires dataset_id and template_id
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
                        }
                    }

                if not template_id:
                    return {
                        "error": "annotation_template_id is required",
                        "message": "Please create an annotation template first using template_create tool"
                    }

                # Validate dataset exists and is ready
                logger.info(f"Validating dataset {dataset_id}...")
                try:
                    dataset_data = await asyncio.to_thread(
                        LabellerrDatasetMeta.get_dataset,
                        self.client,
                        dataset_id
                    )

                    if not dataset_data:
                        return {
                            "error": f"Dataset {dataset_id} not found",
                            "dataset_id": dataset_id
                        }

                    dataset_status = dataset_data.get("status_code")
                    if dataset_status != 300:
                        return {
                            "error": f"Dataset {dataset_id} is not ready",
                            "dataset_id": dataset_id,
                            "status_code": dataset_status,
                            "message": "Dataset is still processing. Please wait and try again."
                        }

                    logger.info(f"✓ Dataset {dataset_id} is ready")
                except Exception as e:
                    return {
                        "error": f"Failed to validate dataset {dataset_id}",
                        "details": str(e)
                    }

                # Create project using SDK
                logger.info(f"Creating project '{args['project_name']}'...")

                rotations_config = args.get("rotation_config", {
                    "annotation_rotation_count": 1,
                    "review_rotation_count": 1,
                    "client_review_rotation_count": 1
                })

                # Create params using Pydantic schema
                params = schemas.CreateProjectParams(
                    project_name=args["project_name"],
                    data_type=args["data_type"],
                    rotations=schemas.RotationConfig(**rotations_config),
                    use_ai=args.get("autolabel", False),
                    created_by=args.get("created_by")
                )

                # Get dataset and template objects
                dataset_obj = await asyncio.to_thread(
                    LabellerrDataset, self.client, dataset_id
                )
                template_obj = await asyncio.to_thread(
                    LabellerrAnnotationTemplate, self.client, template_id
                )

                # Create project
                project = await asyncio.to_thread(
                    project_ops.create_project,
                    self.client,
                    params,
                    [dataset_obj],
                    template_obj
                )

                project_id = project.project_id

                # Cache the project
                self.active_projects[project_id] = {
                    "project_id": project_id,
                    "project_name": args["project_name"],
                    "data_type": args["data_type"],
                    "dataset_id": dataset_id,
                    "template_id": template_id,
                    "created_at": datetime.now().isoformat()
                }
                logger.info(f"✓ Project created successfully: {project_id}")

                result = {
                    "response": {
                        "project_id": project_id
                    },
                    "workflow_completed": {
                        "step_1": f"✓ Dataset: {dataset_id}",
                        "step_2": f"✓ Template: {template_id}",
                        "step_3": f"✓ Project: {project_id}"
                    }
                }

            elif name == "project_list":
                # Use SDK to list projects
                projects = await asyncio.to_thread(
                    project_ops.list_projects,
                    self.client
                )

                # Convert project objects to dicts
                projects_list = []
                for project in projects:
                    project_data = await asyncio.to_thread(
                        LabellerrProjectMeta.get_project,
                        self.client,
                        project.project_id
                    )
                    if project_data:
                        projects_list.append(project_data)
                        self.active_projects[project.project_id] = project_data

                result = {"response": projects_list}

            elif name == "project_get":
                # Use SDK to get project details
                project_data = await asyncio.to_thread(
                    LabellerrProjectMeta.get_project,
                    self.client,
                    args["project_id"]
                )

                if project_data:
                    self.active_projects[args["project_id"]] = project_data

                result = {"response": project_data}

            elif name == "project_update_rotation":
                # Get project object and update rotation
                project = await asyncio.to_thread(
                    LabellerrProject, self.client, args["project_id"]
                )
                update_result = await asyncio.to_thread(
                    project.update_rotation_count,
                    args["rotation_config"]
                )
                result = {"response": update_result}

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
        """Handle dataset management tools using SDK core"""
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
                        upload_result = await asyncio.to_thread(
                            upload_folder_files_to_dataset,
                            self.client,
                            {
                                "client_id": self.client_id,
                                "folder_path": args["folder_path"],
                                "data_type": args["data_type"]
                            }
                        )
                        connection_id = upload_result.get("connection_id")
                        logger.info(f"✓ Files uploaded! Connection ID: {connection_id}")
                    elif args.get("files"):
                        logger.info(f"[1/3] Uploading {len(args['files'])} files...")
                        connection_id = await asyncio.to_thread(
                            upload_files,
                            self.client,
                            self.client_id,
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

                dataset_config = schemas.DatasetConfig(
                    dataset_name=args["dataset_name"],
                    data_type=args["data_type"],
                    dataset_description=args.get("dataset_description", ""),
                    multimodal_indexing=False
                )

                dataset = await asyncio.to_thread(
                    dataset_ops.create_dataset_from_connection,
                    self.client,
                    dataset_config,
                    connection_id,
                    "local"
                )

                dataset_id = dataset.dataset_id
                logger.info(f"✓ Dataset created! Dataset ID: {dataset_id}")

                # STEP 3: Wait for dataset processing (default: enabled)
                if args.get("wait_for_processing", True):
                    logger.info("[3/3] Waiting for dataset to be processed...")
                    try:
                        dataset_status = await asyncio.to_thread(dataset.status)

                        status_code = dataset_status.get("status_code")
                        files_count = dataset_status.get("files_count", 0)

                        if status_code == 300:
                            logger.info(f"✓ Dataset ready! Files: {files_count}")
                            result = {
                                "response": {
                                    "dataset_id": dataset_id,
                                    "files_count": files_count,
                                    "status": "ready",
                                    "status_code": 300
                                }
                            }
                        else:
                            logger.warning(f"Dataset processing completed with status {status_code}")
                            result = {
                                "response": {
                                    "dataset_id": dataset_id,
                                    "status_code": status_code,
                                    "status": "processing_failed"
                                }
                            }
                    except Exception as e:
                        logger.error(f"Error waiting for dataset processing: {e}")
                        result = {
                            "response": {
                                "dataset_id": dataset_id,
                                "warning": f"Dataset created but processing status unknown: {str(e)}",
                                "status": "unknown"
                            }
                        }
                else:
                    result = {
                        "response": {
                            "dataset_id": dataset_id
                        }
                    }

                # Cache the dataset
                self.active_datasets[dataset_id] = {
                    "dataset_id": dataset_id,
                    "name": args["dataset_name"],
                    "data_type": args["data_type"],
                    "created_at": datetime.now().isoformat()
                }

            elif name == "dataset_upload_files":
                connection_id = await asyncio.to_thread(
                    upload_files,
                    self.client,
                    self.client_id,
                    args["files"]
                )
                result = {"connection_id": connection_id, "success": True}

            elif name == "dataset_upload_folder":
                upload_result = await asyncio.to_thread(
                    upload_folder_files_to_dataset,
                    self.client,
                    {
                        "client_id": self.client_id,
                        "folder_path": args["folder_path"],
                        "data_type": args["data_type"]
                    }
                )
                result = {
                    "connection_id": upload_result.get("connection_id"),
                    "success": True,
                    "uploaded_files": len(upload_result.get("success", []))
                }

            elif name == "dataset_list":
                data_type = args.get("data_type", "image")
                scope = args.get("scope", "client")

                # Use SDK to list datasets (returns generator)
                datasets_gen = await asyncio.to_thread(
                    dataset_ops.list_datasets,
                    self.client,
                    data_type,
                    schemas.DataSetScope(scope),
                    page_size=100  # Get first 100 datasets
                )

                # Convert generator to list
                datasets_list = list(datasets_gen)

                # Update datasets cache
                for dataset in datasets_list:
                    dataset_id = dataset.get("dataset_id")
                    if dataset_id:
                        self.active_datasets[dataset_id] = dataset

                result = {"response": {"datasets": datasets_list}}

            elif name == "dataset_get":
                # Use SDK to get dataset details
                dataset_data = await asyncio.to_thread(
                    LabellerrDatasetMeta.get_dataset,
                    self.client,
                    args["dataset_id"]
                )

                if dataset_data:
                    self.active_datasets[args["dataset_id"]] = dataset_data

                result = {"response": dataset_data}

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
        """Handle annotation tools using SDK core"""
        start_time = datetime.now()
        result = {}

        try:
            if name == "template_create":
                logger.info(f"Creating annotation template: {args['template_name']}")

                # Convert questions to AnnotationQuestion objects
                questions = []
                for q in args["questions"]:
                    question_type = q.get("question_type", q.get("option_type", "BoundingBox"))

                    # Handle options
                    options = None
                    if q.get("options"):
                        options = [Option(option_name=opt.get("option_name", opt)) for opt in q["options"]]

                    question = AnnotationQuestion(
                        question_number=q.get("question_number", 1),
                        question=q["question"],
                        question_id=q.get("question_id", str(uuid.uuid4())),
                        question_type=QuestionType(question_type),
                        required=q.get("required", True),
                        options=options,
                        color=q.get("color")
                    )
                    questions.append(question)

                # Create template params
                params = TemplateParams(
                    template_name=args["template_name"],
                    data_type=args["data_type"],
                    questions=questions
                )

                # Create template using SDK
                template = await asyncio.to_thread(
                    template_ops.create_template,
                    self.client,
                    params
                )

                template_id = template.annotation_template_id
                logger.info(f"Template created successfully: {template_id}")

                result = {
                    "response": {
                        "template_id": template_id
                    }
                }

            elif name == "annotation_export":
                # Get project and create export
                project = await asyncio.to_thread(
                    LabellerrProject, self.client, args["project_id"]
                )

                export_config = schemas.CreateExportParams(
                    export_name=args["export_name"],
                    export_description=args.get("export_description", ""),
                    export_format=args["export_format"],
                    statuses=args["statuses"],
                    export_destination=schemas.ExportDestination.LOCAL
                )

                export = await asyncio.to_thread(
                    project.create_export,
                    export_config
                )

                result = {
                    "response": {
                        "report_id": export.report_id
                    }
                }

            elif name == "annotation_check_export_status":
                # Get project and check export status
                project = await asyncio.to_thread(
                    LabellerrProject, self.client, args["project_id"]
                )

                status_result = await asyncio.to_thread(
                    project.check_export_status,
                    args["export_ids"]
                )

                # Parse JSON string result if needed
                if isinstance(status_result, str):
                    status_result = json.loads(status_result)

                result = status_result

            elif name == "annotation_download_export":
                # Get project and fetch download URL (using internal method)
                project = await asyncio.to_thread(
                    LabellerrProject, self.client, args["project_id"]
                )

                download_result = await asyncio.to_thread(
                    project._LabellerrProject__fetch_exports_download_url,
                    args["project_id"],
                    str(uuid.uuid4()),
                    args["export_id"],
                    self.client_id
                )

                result = {"response": download_result}

            elif name == "annotation_upload_preannotations":
                # Get project and upload preannotations
                project = await asyncio.to_thread(
                    LabellerrProject, self.client, args["project_id"]
                )

                upload_result = await asyncio.to_thread(
                    project.upload_preannotations,
                    args["annotation_format"],
                    args["annotation_file"],
                    _async=False
                )

                result = {"response": upload_result}

            elif name == "annotation_upload_preannotations_async":
                # Get project and upload preannotations asynchronously
                project = await asyncio.to_thread(
                    LabellerrProject, self.client, args["project_id"]
                )

                future = await asyncio.to_thread(
                    project.upload_preannotations,
                    args["annotation_format"],
                    args["annotation_file"],
                    _async=True
                )

                result = {
                    "response": {
                        "status": "Job started",
                        "message": "Preannotation upload job has been submitted"
                    }
                }

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
                result = {
                    "success": True,
                    "job_id": args["job_id"],
                    "status": "This feature requires specific job tracking API",
                    "message": "Use check_export_status for export jobs"
                }

            elif name == "monitor_project_progress":
                # Get project details for progress using SDK
                project_data = await asyncio.to_thread(
                    LabellerrProjectMeta.get_project,
                    self.client,
                    args["project_id"]
                )
                result = {"response": project_data}

            elif name == "monitor_active_operations":
                recent_ops = [op for op in self.operation_history[-50:]]
                result = {
                    "active_operations": recent_ops,
                    "total_operations": len(self.operation_history)
                }

            elif name == "monitor_system_health":
                result = {
                    "status": "healthy",
                    "connected": self.client is not None,
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
                # Get project details using SDK
                project_data = await asyncio.to_thread(
                    LabellerrProjectMeta.get_project,
                    self.client,
                    args["project_id"]
                )

                if project_data:
                    result = {
                        "project_id": args["project_id"],
                        "project_name": project_data.get("project_name", ""),
                        "data_type": project_data.get("data_type", ""),
                        "total_files": project_data.get("total_files", 0),
                        "annotated_files": project_data.get("annotated_files", 0),
                        "reviewed_files": project_data.get("reviewed_files", 0),
                        "accepted_files": project_data.get("accepted_files", 0),
                        "completion_percentage": project_data.get("completion_percentage", 0)
                    }
                else:
                    result = {"error": f"Project {args['project_id']} not found"}

            elif name == "query_dataset_info":
                dataset_data = await asyncio.to_thread(
                    LabellerrDatasetMeta.get_dataset,
                    self.client,
                    args["dataset_id"]
                )
                result = {"response": dataset_data}

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
                # Get all projects using SDK and filter
                projects = await asyncio.to_thread(
                    project_ops.list_projects,
                    self.client
                )

                query = args["query"].lower()
                matching_projects = []

                for project in projects:
                    project_data = await asyncio.to_thread(
                        LabellerrProjectMeta.get_project,
                        self.client,
                        project.project_id
                    )
                    if project_data:
                        if (query in project_data.get("project_name", "").lower() or
                                query in project_data.get("data_type", "").lower()):
                            matching_projects.append(project_data)

                result = {"projects": matching_projects}

            else:
                result = {"error": f"Unknown query tool: {name}"}

            return result

        except Exception as e:
            logger.error(f"Query tool error: {e}", exc_info=True)
            raise

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Labellerr MCP Server (SDK Core Implementation)...")
        logger.info(f"Connected to Labellerr SDK: {self.client is not None}")

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
