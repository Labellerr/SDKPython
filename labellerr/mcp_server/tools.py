"""
Tool definitions for the Labellerr MCP Server
"""

# Project Management Tools
PROJECT_TOOLS = [
    {
        "name": "project_create",
        "description": "Create a new annotation project with dataset and guidelines",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Name of the project"
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Name of the dataset"
                },
                "dataset_description": {
                    "type": "string",
                    "description": "Description of the dataset"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Type of data to annotate"
                },
                "created_by": {
                    "type": "string",
                    "description": "Email of the creator"
                },
                "annotation_guide": {
                    "type": "array",
                    "description": "Array of annotation questions/guidelines",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The annotation question"
                            },
                            "option_type": {
                                "type": "string",
                                "enum": ["input", "radio", "boolean", "select", "dropdown", "stt", "imc", "BoundingBox", "polygon", "dot", "audio"],
                                "description": "Type of annotation input"
                            },
                            "options": {
                                "type": "array",
                                "description": "Available options for the question"
                            },
                            "required": {
                                "type": "boolean",
                                "description": "Whether this question is required"
                            }
                        },
                        "required": ["question", "option_type"]
                    }
                },
                "rotation_config": {
                    "type": "object",
                    "properties": {
                        "annotation_rotation_count": {
                            "type": "number",
                            "description": "Number of annotation rotations"
                        },
                        "review_rotation_count": {
                            "type": "number",
                            "description": "Number of review rotations (must be 1)"
                        },
                        "client_review_rotation_count": {
                            "type": "number",
                            "description": "Number of client review rotations"
                        }
                    }
                },
                "autolabel": {
                    "type": "boolean",
                    "description": "Enable auto-labeling (required, set to false if not using)",
                    "default": False
                },
                "folder_to_upload": {
                    "type": "string",
                    "description": "Path to folder containing files to upload"
                },
                "files_to_upload": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of file paths to upload"
                }
            },
            "required": ["project_name", "dataset_name", "data_type", "created_by", "annotation_guide"]
        }
    },
    {
        "name": "project_list",
        "description": "List all projects for the client",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "project_get",
        "description": "Get detailed information about a specific project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project to retrieve"
                }
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "project_update_rotation",
        "description": "Update rotation configuration for a project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                },
                "rotation_config": {
                    "type": "object",
                    "properties": {
                        "annotation_rotation_count": {"type": "number"},
                        "review_rotation_count": {"type": "number"},
                        "client_review_rotation_count": {"type": "number"}
                    }
                }
            },
            "required": ["project_id", "rotation_config"]
        }
    }
]

# Dataset Management Tools
DATASET_TOOLS = [
    {
        "name": "dataset_create",
        "description": "Create a new dataset",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_name": {
                    "type": "string",
                    "description": "Name of the dataset"
                },
                "dataset_description": {
                    "type": "string",
                    "description": "Description of the dataset"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Type of data in the dataset"
                }
            },
            "required": ["dataset_name", "data_type"]
        }
    },
    {
        "name": "dataset_upload_files",
        "description": "Upload individual files to a dataset",
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of file paths to upload"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Type of data being uploaded"
                }
            },
            "required": ["files", "data_type"]
        }
    },
    {
        "name": "dataset_upload_folder",
        "description": "Upload all files from a folder to a dataset",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "Path to the folder containing files"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Type of data being uploaded"
                }
            },
            "required": ["folder_path", "data_type"]
        }
    },
    {
        "name": "dataset_list",
        "description": "List all datasets (linked and unlinked)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Filter by data type",
                    "default": "image"
                }
            }
        }
    },
    {
        "name": "dataset_get",
        "description": "Get detailed information about a dataset",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "ID of the dataset"
                }
            },
            "required": ["dataset_id"]
        }
    }
]

# Annotation Tools
ANNOTATION_TOOLS = [
    {
        "name": "annotation_upload_preannotations",
        "description": "Upload pre-annotations to a project (synchronous)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                },
                "annotation_format": {
                    "type": "string",
                    "enum": ["json", "coco_json", "csv", "png"],
                    "description": "Format of the annotation file"
                },
                "annotation_file": {
                    "type": "string",
                    "description": "Path to the annotation file"
                }
            },
            "required": ["project_id", "annotation_format", "annotation_file"]
        }
    },
    {
        "name": "annotation_upload_preannotations_async",
        "description": "Upload pre-annotations to a project (asynchronous)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                },
                "annotation_format": {
                    "type": "string",
                    "enum": ["json", "coco_json", "csv", "png"],
                    "description": "Format of the annotation file"
                },
                "annotation_file": {
                    "type": "string",
                    "description": "Path to the annotation file"
                }
            },
            "required": ["project_id", "annotation_format", "annotation_file"]
        }
    },
    {
        "name": "annotation_export",
        "description": "Create an export of project annotations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                },
                "export_name": {
                    "type": "string",
                    "description": "Name for the export"
                },
                "export_description": {
                    "type": "string",
                    "description": "Description of the export"
                },
                "export_format": {
                    "type": "string",
                    "enum": ["json", "coco_json", "csv", "png"],
                    "description": "Format for the export"
                },
                "statuses": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["review", "r_assigned", "client_review", "cr_assigned", "accepted"]
                    },
                    "description": "Filter annotations by status"
                }
            },
            "required": ["project_id", "export_name", "export_format", "statuses"]
        }
    },
    {
        "name": "annotation_check_export_status",
        "description": "Check the status of export jobs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                },
                "export_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of export IDs to check"
                }
            },
            "required": ["project_id", "export_ids"]
        }
    },
    {
        "name": "annotation_download_export",
        "description": "Get download URL for a completed export",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                },
                "export_id": {
                    "type": "string",
                    "description": "ID of the export"
                }
            },
            "required": ["project_id", "export_id"]
        }
    }
]

# Monitoring Tools
MONITORING_TOOLS = [
    {
        "name": "monitor_job_status",
        "description": "Monitor the status of a background job",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "ID of the job to monitor"
                }
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "monitor_project_progress",
        "description": "Get progress statistics for a project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                }
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "monitor_active_operations",
        "description": "List all active operations and their status",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "monitor_system_health",
        "description": "Check the health and status of the MCP server",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# Query Tools
QUERY_TOOLS = [
    {
        "name": "query_project_statistics",
        "description": "Get detailed statistics for a project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project"
                }
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "query_dataset_info",
        "description": "Get detailed information about a dataset",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "ID of the dataset"
                }
            },
            "required": ["dataset_id"]
        }
    },
    {
        "name": "query_operation_history",
        "description": "Query the history of operations performed",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "number",
                    "description": "Maximum number of operations to return",
                    "default": 10
                },
                "status": {
                    "type": "string",
                    "enum": ["success", "failed", "in_progress"],
                    "description": "Filter by operation status"
                }
            }
        }
    },
    {
        "name": "query_search_projects",
        "description": "Search for projects by name or type",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                }
            },
            "required": ["query"]
        }
    }
]

# All tools combined
ALL_TOOLS = PROJECT_TOOLS + DATASET_TOOLS + ANNOTATION_TOOLS + MONITORING_TOOLS + QUERY_TOOLS


