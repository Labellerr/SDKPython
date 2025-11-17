import logging
import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.datasets import LabellerrDataset, create_dataset
from labellerr.core.connectors import LabellerrS3Connection, LabellerrConnection
from labellerr.core.files import LabellerrFile
from labellerr.core.projects import (
    LabellerrProject,
    LabellerrVideoProject,
    create_annotation_guideline,
    create_project,
)
from labellerr.core.schemas import (
    DatasetConfig,
    KeyFrame,
    TrainingRequest,
    Hyperparameters,
    AWSConnectionParams,
    AWSConnectionTestParams,
    DatasetDataType,
    CreateExportParams,
)
from labellerr.core.autolabel import LabellerrAutoLabel


# if os.getenv("CREATE_DATASET", "").lower() == "true":
#     from labellerr import schemas
#     from labellerr.core.datasets import create_dataset

#     folder_to_upload = os.getenv("FOLDER_TO_UPLOAD", "images")
#     dataset_name = os.getenv("DATASET_NAME", "Dataset new Ximi")

#     print(f"\n=== Creating Dataset: {dataset_name} ===")
#     response = create_dataset(
#         client=client,
#         dataset_config=schemas.DatasetConfig(
#             client_id=CLIENT_ID,
#             dataset_name=dataset_name,
#             data_type="image",
#         ),
#         folder_to_upload=folder_to_upload,
#     )
#     print(f"Dataset created: {response.dataset_data}")

# DATASET_ID = os.getenv("DATASET_ID")
# if DATASET_ID:
#     print(f"\n=== Working with Dataset: {DATASET_ID} ===")
#     dataset = LabellerrDataset(client=client, dataset_id=DATASET_ID)
#     print(f"Dataset loaded: {dataset.data_type}")

# if os.getenv("CREATE_PROJECT", "").lower() == "true":
#     project = create_project(
#         client=client,
#         payload={
#             "project_name": project_name,
#             "data_type": "image",
#             "folder_to_upload": folder_to_upload,
#             "annotation_template_id": annotation_template_id,
#             "rotations": {
#                 "annotation_rotation_count": 1,
#                 "review_rotation_count": 1,
#                 "client_review_rotation_count": 1,
#             },
#             "use_ai": False,
#             "created_by": os.getenv("CREATED_BY", "dev@labellerr.com"),
#             "autolabel": False,
#         },
#     )
#     print(f"Project created: {project.project_data}")

# if os.getenv("SYNC_AWS", "").lower() == "true":
#     aws_connection_id = os.getenv("AWS_CONNECTION_ID")
#     aws_project_id = os.getenv("AWS_PROJECT_ID")
#     aws_dataset_id = os.getenv("AWS_DATASET_ID", DATASET_ID)
#     aws_s3_path = os.getenv("AWS_S3_PATH")
#     aws_data_type = os.getenv("AWS_DATA_TYPE", "image")
#     aws_email = os.getenv("AWS_EMAIL", "dev@labellerr.com")

#     if not all([aws_connection_id, aws_project_id, aws_dataset_id, aws_s3_path]):
#         raise ValueError(
#             "AWS_CONNECTION_ID, AWS_PROJECT_ID, AWS_DATASET_ID, and AWS_S3_PATH "
#             "must be set when SYNC_AWS=true"
#         )

#     if not aws_dataset_id:
#         raise ValueError("DATASET_ID or AWS_DATASET_ID must be set when SYNC_AWS=true")

#     print(f"\n=== Syncing Dataset from AWS S3: {aws_s3_path} ===")
#     dataset = LabellerrDataset(client=client, dataset_id=aws_dataset_id)
#     response = dataset.sync_datasets(
#         project_id=aws_project_id,
#         path=aws_s3_path,
#         data_type=aws_data_type,
#         email_id=aws_email,
#         connection_id=aws_connection_id,
#     )
#     print(f"AWS S3 Sync Response: {response}")

# if os.getenv("SYNC_GCS", "").lower() == "true":
#     gcs_connection_id = os.getenv("GCS_CONNECTION_ID")
#     gcs_project_id = os.getenv("GCS_PROJECT_ID")
#     gcs_dataset_id = os.getenv("GCS_DATASET_ID", DATASET_ID)
#     gcs_path = os.getenv("GCS_PATH")
#     gcs_data_type = os.getenv("GCS_DATA_TYPE", "image")
#     gcs_email = os.getenv("GCS_EMAIL", "dev@labellerr.com")

#     if not all([gcs_connection_id, gcs_project_id, gcs_dataset_id, gcs_path]):
#         raise ValueError(
#             "GCS_CONNECTION_ID, GCS_PROJECT_ID, GCS_DATASET_ID, and GCS_PATH "
#             "must be set when SYNC_GCS=true"
#         )

#     if not gcs_dataset_id:
#         raise ValueError("DATASET_ID or GCS_DATASET_ID must be set when SYNC_GCS=true")

#     print(f"\n=== Syncing Dataset from GCS: {gcs_path} ===")
#     dataset = LabellerrDataset(client=client, dataset_id=gcs_dataset_id)
#     response = dataset.sync_datasets(
#         project_id=gcs_project_id,
#         path=gcs_path,
#         data_type=gcs_data_type,
#         email_id=gcs_email,
#         connection_id=gcs_connection_id,
#     )
#     print(f"GCS Sync Response: {response}")


# autolabel = LabellerrAutoLabel(client=client)
# print(LabellerrS3Connection.create_connection(client=client,
# params=AWSConnectionParams(
#     aws_access_key=os.getenv("AWS_KEY"),
#     aws_secrets_key=os.getenv("AWS_SECRET"),
#     s3_path="", # format - s3://bucket_name/path/to/folder/
#     # (this is required to test the connection on the desired path) this path wont be associated with the connection.
#     # you can dynamically change the export path while using this connection
#     connection_type="export",
#     name="Amazon S3 Export Test",
#     description="Amazon S3 Export Test",
# )))
# project = LabellerrProject(client=client, project_id="")

# export = project.create_export(
#     export_config=CreateExportParams(
#         export_name="Amazon S3 Export Test",
#         export_description="Amazon S3 Export Test",
#         export_format="json",
#         statuses=["review"],
#         connection_id=os.getenv("AWS_EXPORT_CONNECTION_ID"),
#         export_destination="s3",
#         export_folder_path="",  # pattern - bucket_name/path/to/folder/ - the last slash is important
#     )
# )

# print(f"Export created: {export.report_id}")
# print(f"Current status: {export._status}")
# Uncomment to poll until completion:
# final_status = export.status()
# print(f"Final status: {final_status}")
# print(autolabel.train(training_request=TrainingRequest(model_id="yolov11", hyperparameters=Hyperparameters(epochs=10), slice_id='', min_samples_per_class=100, job_name="Yolo V11 Training")))

# dataset = LabellerrDataset(client=client, dataset_id="")
# print (dataset.fetch_files())

# Create dataset using aws and gcs

# Bulk assign files to a new status
# project = LabellerrProject()
# project.bulk_assign_files(client_id=client.client_id, project_id=project.project_id, file_ids=file_ids, new_status="completed")

# project = LabellerrProject(client=client, project_id="")
# print(project.attached_datasets)
# print(project.attach_dataset_to_project(dataset_id="137a7b2f-942f-478d"))

# dataset = LabellerrDataset(client=client, dataset_id="")
# print(dataset.enable_multimodal_indexing(is_multimodal=False))

# file = LabellerrFile(client=client, dataset_id='', file_id="")
# print(file.file_data)

# project = LabellerrProject(client=client, project_id="")
# res = project.upload_preannotation(
#     annotation_format="coco_json", annotation_file="horses_coco.json"
# ).result()
# print(res)

# print(LabellerrProject.list_all_projects(client=client))

# project: LabellerrVideoProject = LabellerrProject(client=client, project_id="pam_rear_worm_89383")
# print(project.add_keyframes(file_id="", keyframes=[KeyFrame(frame_number=1, is_manual=True, method="manual", source="manual")]))

# datasets = LabellerrDataset.get_all_datasets(
#     client=client, datatype="image", scope="project", page_size=-1
# )
# for dataset in datasets:
#     print('name', dataset.get("name"), 'id', dataset.get("dataset_id"))
