import cred
from Create_Project import (
    create_project_all_option_type,
    create_project_boundingbox_dropdown_input,
    create_project_input_select_radio,
    create_project_polygon_boundingbox_project,
    create_project_polygon_input,
    create_project_radio_dropdown,
    create_project_select_dropdown_radio,
)
from Export_project import export_project
from Pre_annotation_uploading import pre_annotation_uploading

api_key = cred.API_KEY
api_secret = cred.API_SECRET
client_id = cred.CLIENT_ID
project_id = cred.PROJECT_ID
email = cred.EMAIL_ID


def test_create_project(path_to_images):

    print("CREATING PROJECTS WITH DIFFERENT OPTION TYPE")
    print("\n 1:project with all option type")
    create_project_all_option_type(
        api_key, api_secret, client_id, email, path_to_images
    )

    print("\n 2:project with polygon and bounding box")
    create_project_polygon_boundingbox_project(
        api_key, api_secret, client_id, email, path_to_images
    )

    print("\n 3:project with select, dropdown and radio")
    create_project_select_dropdown_radio(
        api_key, api_secret, client_id, email, path_to_images
    )

    print("\n 4:project with polygon and input")
    create_project_polygon_input(api_key, api_secret, client_id, email, path_to_images)

    print("\n 5:project with input, select and radio")
    create_project_input_select_radio(
        api_key, api_secret, client_id, email, path_to_images
    )

    print("\n 6:project with bounding box, dropdown and input")
    create_project_boundingbox_dropdown_input(
        api_key, api_secret, client_id, email, path_to_images
    )

    print("\n 7:project with radio and dropdown")
    create_project_radio_dropdown(api_key, api_secret, client_id, email, path_to_images)

    print("\n Project creation completed.")


def test_export_project(project_id):
    print("\n EXPORTING PROJECT")
    export_project(api_key, api_secret, client_id, project_id)
    print("\n Project export completed.")


def test_pre_annotation_uploading(project_id, annotation_format, annotation_file):
    print("\n PRE-ANNOTATION UPLOADING")
    pre_annotation_uploading(
        api_key, api_secret, client_id, project_id, annotation_format, annotation_file
    )
    print("\n Pre-annotation uploading completed.")


if __name__ == "__main__":

    test_dataset_path = (
        r"D:\professional\LABELLERR\Task\LABIMP-7059-SDK-Testing\test_img_6"
    )
    test_create_project(test_dataset_path)

    test_export_project(project_id)

    json_annotation_file = r"D:\professional\LABELLERR\Task\LABIMP-7059-SDK-Testing\test_img_6_annotations.json"
    test_pre_annotation_uploading(project_id, "coco_json", json_annotation_file)
