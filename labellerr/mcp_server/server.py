#!/usr/bin/env python3
"""
Labellerr MCP Server
A Model Context Protocol server for the Labellerr SDK
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Resource,
    ResourceTemplate,
)

# Import the Labellerr client from the SDK
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from labellerr.client import LabellerrClient

# Import tool definitions
from .tools import ALL_TOOLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


class LabellerrMCPServer:
    """MCP Server for Labellerr SDK operations"""
    
    def __init__(self):
        self.server = Server("labellerr-mcp-server")
        self.labellerr_client: Optional[LabellerrClient] = None
        self.operation_history: List[Dict[str, Any]] = []
        self.active_projects: Dict[str, Dict[str, Any]] = {}
        self.active_datasets: Dict[str, Dict[str, Any]] = {}
        
        # Initialize client
        self._initialize_client()
        
        # Setup request handlers
        self._setup_handlers()
        
    def _initialize_client(self):
        """Initialize Labellerr client with credentials"""
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
            self.labellerr_client = LabellerrClient(
                api_key=api_key,
                api_secret=api_secret
            )
            logger.info("Labellerr client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Labellerr client: {e}")
    
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
            if not self.labellerr_client:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Labellerr client not initialized. Please check environment variables."
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
                    name=project.get("name", project_id),
                    mimeType="application/json",
                    description=f"Project: {project.get('name', project_id)} ({project.get('dataType', 'unknown')})"
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
        """Handle project management tools"""
        start_time = datetime.now()
        result = {}
        
        try:
            if name == "project_create":
                # Use the initiate_create_project method which handles the full flow
                payload = {**args, "client_id": self.client_id}
                result = await asyncio.to_thread(
                    self.labellerr_client.initiate_create_project,
                    payload
                )
                # Try to cache the project if we have a valid ID
                try:
                    project_id = result.get("project_id")
                    if project_id and isinstance(project_id, str):
                        self.active_projects[project_id] = {
                            "id": project_id,
                            "name": args.get("project_name"),
                            "dataType": args.get("data_type"),
                            "createdAt": datetime.now().isoformat()
                        }
                except Exception:
                    pass  # Don't fail if caching doesn't work
            
            elif name == "project_list":
                result = await asyncio.to_thread(
                    self.labellerr_client.get_all_project_per_client_id,
                    self.client_id
                )
                # Update active projects cache
                if result.get("response"):
                    for project in result["response"]:
                        project_id = project.get("project_id")
                        if project_id:
                            self.active_projects[project_id] = project
            
            elif name == "project_get":
                # Note: Need to find the right method for getting a single project
                # For now, get all and filter
                all_projects = await asyncio.to_thread(
                    self.labellerr_client.get_all_project_per_client_id,
                    self.client_id
                )
                projects = all_projects.get("response", [])
                project = next((p for p in projects if p.get("project_id") == args["project_id"]), None)
                result = {"project": project} if project else {"error": "Project not found"}
            
            elif name == "project_update_rotation":
                # This method needs implementation in the SDK or use direct API call
                result = {"error": "Update rotation not yet implemented in SDK"}
            
            else:
                result = {"error": f"Unknown project tool: {name}"}
            
            # Log successful operation
            self.operation_history.append({
                "timestamp": datetime.now().isoformat(),
                "tool": name,
                "duration": (datetime.now() - start_time).total_seconds(),
                "status": "success",
                "args": args
            })
            
            return result
        
        except Exception as e:
            logger.error(f"Project tool error: {e}", exc_info=True)
            raise
    
    async def _handle_dataset_tool(self, name: str, args: dict) -> dict:
        """Handle dataset management tools"""
        start_time = datetime.now()
        result = {}
        
        try:
            if name == "dataset_create":
                dataset_config = {**args, "client_id": self.client_id}
                result = await asyncio.to_thread(
                    self.labellerr_client.create_dataset,
                    dataset_config
                )
                if result.get("dataset_id"):
                    self.active_datasets[result["dataset_id"]] = {
                        "id": result["dataset_id"],
                        "name": args.get("dataset_name"),
                        "dataType": args.get("data_type"),
                        "createdAt": datetime.now().isoformat()
                    }
            
            elif name == "dataset_upload_files":
                result = await asyncio.to_thread(
                    self.labellerr_client.upload_files,
                    self.client_id,
                    args["files"]
                )
            
            elif name == "dataset_upload_folder":
                data_config = {
                    "client_id": self.client_id,
                    "folder_path": args["folder_path"],
                    "data_type": args["data_type"]
                }
                result = await asyncio.to_thread(
                    self.labellerr_client.upload_folder_files_to_dataset,
                    data_config
                )
            
            elif name == "dataset_list":
                data_type = args.get("data_type", "image")
                result = await asyncio.to_thread(
                    self.labellerr_client.get_all_dataset,
                    self.client_id,
                    data_type,
                    "",  # project_id (empty for all)
                    "client"  # scope
                )
                # Update datasets cache
                response = result.get("response", {})
                if response.get("linked"):
                    for dataset in response["linked"]:
                        dataset_id = dataset.get("dataset_id")
                        if dataset_id:
                            self.active_datasets[dataset_id] = dataset
                if response.get("unlinked"):
                    for dataset in response["unlinked"]:
                        dataset_id = dataset.get("dataset_id")
                        if dataset_id:
                            self.active_datasets[dataset_id] = dataset
            
            elif name == "dataset_get":
                result = await asyncio.to_thread(
                    self.labellerr_client.get_dataset,
                    self.client_id,
                    args["dataset_id"]
                )
            
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
        """Handle annotation tools"""
        start_time = datetime.now()
        result = {}
        
        try:
            if name == "annotation_upload_preannotations":
                result = await asyncio.to_thread(
                    self.labellerr_client.upload_preannotation_data,
                    args["project_id"],
                    self.client_id,
                    args["annotation_format"],
                    args["annotation_file"]
                )
            
            elif name == "annotation_upload_preannotations_async":
                result = await asyncio.to_thread(
                    self.labellerr_client.upload_preannotation_data_async,
                    args["project_id"],
                    self.client_id,
                    args["annotation_format"],
                    args["annotation_file"]
                )
            
            elif name == "annotation_export":
                # Note: Need to check SDK for export methods
                result = {"error": "Export not yet implemented - check SDK for method"}
            
            elif name == "annotation_check_export_status":
                result = {"error": "Check export status not yet implemented - check SDK for method"}
            
            elif name == "annotation_download_export":
                result = {"error": "Download export not yet implemented - check SDK for method"}
            
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
                # Return mock status - SDK may not have this method
                result = {
                    "success": True,
                    "job_id": args["job_id"],
                    "status": "completed",
                    "message": "Job status monitoring not yet implemented in SDK"
                }
            
            elif name == "monitor_project_progress":
                # Get project details and extract progress
                all_projects = await asyncio.to_thread(
                    self.labellerr_client.get_all_project_per_client_id,
                    self.client_id
                )
                projects = all_projects.get("response", [])
                project = next((p for p in projects if p.get("project_id") == args["project_id"]), None)
                if project:
                    result = {
                        "success": True,
                        "project_id": args["project_id"],
                        "progress": project
                    }
                else:
                    result = {"error": "Project not found"}
            
            elif name == "monitor_active_operations":
                # Return current active operations from history
                recent_ops = [
                    op for op in self.operation_history
                    if op.get("status") == "in_progress" or
                    (op.get("timestamp") and 
                     (datetime.now() - datetime.fromisoformat(op["timestamp"])).total_seconds() < 300)
                ]
                result = {
                    "active_operations": recent_ops,
                    "total_operations": len(self.operation_history)
                }
            
            elif name == "monitor_system_health":
                result = {
                    "status": "healthy",
                    "connected": self.labellerr_client is not None,
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
                # Get all projects and find the specific one
                all_projects = await asyncio.to_thread(
                    self.labellerr_client.get_all_project_per_client_id,
                    self.client_id
                )
                projects = all_projects.get("response", [])
                project = next((p for p in projects if p.get("project_id") == args["project_id"]), None)
                
                if project:
                    result = {
                        "project_id": args["project_id"],
                        "total_files": project.get("total_files", 0),
                        "annotated_files": project.get("annotated_files", 0),
                        "reviewed_files": project.get("reviewed_files", 0),
                        "accepted_files": project.get("accepted_files", 0),
                        "completion_percentage": project.get("completion_percentage", 0),
                        "project_name": project.get("project_name", ""),
                        "data_type": project.get("data_type", "")
                    }
                else:
                    result = {"error": "Project not found"}
            
            elif name == "query_dataset_info":
                result = await asyncio.to_thread(
                    self.labellerr_client.get_dataset,
                    self.client_id,
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
                all_projects = await asyncio.to_thread(
                    self.labellerr_client.get_all_project_per_client_id,
                    self.client_id
                )
                query = args["query"].lower()
                projects = all_projects.get("response", [])
                result = {
                    "projects": [
                        p for p in projects
                        if query in p.get("project_name", "").lower() or
                           query in p.get("data_type", "").lower()
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
        logger.info("Starting Labellerr MCP Server...")
        logger.info(f"Connected to Labellerr API: {self.labellerr_client is not None}")
        
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

