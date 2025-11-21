"""
Tool definitions for the Labellerr MCP Server
"""

# Project Management Tools
PROJECT_TOOLS = [
    {
        "name": "project_create",
        "description": "Create a new annotation project (Step 3 of 3). REQUIRES dataset_id and annotation_template_id. Use this AFTER creating a dataset (dataset_upload_folder/dataset_create) and template (template_create). This enforces an explicit three-step workflow where the AI assistant asks the user for dataset and template details interactively.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Name of the project"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Type of data to annotate"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "ID of the dataset (REQUIRED - must be created first using dataset_upload_folder or dataset_create)"
                },
                "annotation_template_id": {
                    "type": "string",
                    "description": "ID of the annotation template (REQUIRED - must be created first using template_create)"
                },
                "created_by": {
                    "type": "string",
                    "description": "Email of the creator"
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
                    "description": "Enable auto-labeling",
                    "default": False
                }
            },
            "required": ["project_name", "data_type", "dataset_id", "annotation_template_id", "created_by"]
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
        "description": "Create a new dataset with automatic file upload and status polling. Provide folder_path or files to upload data directly. The tool handles the complete workflow: upload files → create dataset → wait for processing → return ready dataset.",
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
                },
                "folder_path": {
                    "type": "string",
                    "description": "Path to folder containing files to upload (optional - for creating dataset with files)"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of file paths to upload (optional - alternative to folder_path)"
                },
                "connection_id": {
                    "type": "string",
                    "description": "Connection ID from previous upload (optional - if files already uploaded)"
                },
                "wait_for_processing": {
                    "type": "boolean",
                    "description": "Wait for dataset processing to complete (default: true)",
                    "default": True
                },
                "processing_timeout": {
                    "type": "number",
                    "description": "Maximum seconds to wait for processing (default: 300)",
                    "default": 300
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
        "name": "template_create",
        "description": "Create an annotation template with questions/guidelines",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of the template"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["image", "video", "audio", "document", "text"],
                    "description": "Type of data for the template"
                },
                "questions": {
                    "type": "array",
                    "description": "Array of annotation questions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_number": {
                                "type": "number",
                                "description": "Order number of the question"
                            },
                            "question": {
                                "type": "string",
                                "description": "The annotation question text"
                            },
                            "question_id": {
                                "type": "string",
                                "description": "Unique identifier for the question (auto-generated if not provided)"
                            },
                            "question_type": {
                                "type": "string",
                                "enum": ["BoundingBox", "polygon", "polyline", "dot", "input", "radio", "boolean", "select", "dropdown", "stt", "imc"],
                                "description": "Type of annotation input"
                            },
                            "required": {
                                "type": "boolean",
                                "description": "Whether this question is required"
                            },
                            "options": {
                                "type": "array",
                                "description": "Available options (required for radio, boolean, select, dropdown, etc)",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "option_name": {
                                            "type": "string"
                                        }
                                    }
                                }
                            },
                            "color": {
                                "type": "string",
                                "description": "Color code (required for BoundingBox, polygon, polyline, dot)"
                            }
                        },
                        "required": ["question_number", "question", "question_type", "required"]
                    }
                }
            },
            "required": ["template_name", "data_type", "questions"]
        }
    },
    {
        "name": "annotation_upload_preannotations",
        "description": "Upload pre-annotations to a project (synchronous) - for pre-labeling existing projects",
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
        "description": "Upload pre-annotations to a project (asynchronous) - for pre-labeling existing projects",
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
