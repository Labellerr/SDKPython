## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Getting Started](#getting-started)
   - [Obtaining API Keys and Client ID](#obtaining-api_keys-and-client_id)
   - [Example](#example)
4. [Creating a New Project](#creating-a-new-project)
   - [Limitations](#limitations)
   - [Acceptable Values](#acceptable-value)
   - [Data Types and Supported Formats](#data-types-and-supported-formats)
   - [Example Usage](#example-usage)
5. [Uploading Pre-annotations](#uploading-pre-annotations)
   - [Example Usage (Synchronous)](#example-usage-synchronous)
   - [Example Usage (Asynchronous)](#example-usage-asynchronous)
6. [Local Export](#local-export)
   - [Acceptable Values](#acceptable-values)
   - [Example Usage](#example-usage-1)
7. [Retrieving All Projects for a Client](#retrieving-all-projects-for-a-client)
   - [Example Usage](#example-usage-2)
8. [Retrieving All Datasets](#retrieving-all-datasets)
   - [Example Usage](#example-usage-3)
9. [Error Handling](#error-handling)
10. [Automatic Logging and Error Handling](#automatic-logging-and-error-handling)
11. [Support](#support)

---

## Introduction

The **Labellerr SDK** is a Python library designed to make interacting with the Labellerr platform simple and efficient. With this SDK, you can manage data annotations, projects, and exports seamlessly in your applications.

This documentation will guide you through installing the SDK, understanding its core functionalities, and handling common errors.

---

## Installation

To install the Labellerr SDK, use the following command:

```bash
pip install https://github.com/Labellerr/SDKPython/releases/download/prod/labellerr_sdk-1.0.0.tar.gz
```

---

## Getting Started

#### Obtaining `api_keys` and `client_id`:

**To obtain your api_keys and client_id, Pro and Enterprise plan users can contact Labellerr support. If you are on a free plan, you can request them by emailing `support@tensormatics.com`.**

Once installed, you can start by importing and initializing the `LabellerrClient` and `LabellerrError`. This client will handle all communication with the Labellerr platform.

### Example Client initiation:

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError

# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')
```

Replace `'your_api_key'`, `'your_api_secret'` and `'your_client_id'` with the credentials and client ID provided by Labellerr. `client_id` is required: every request carries it, and a missing or blank one raises `LabellerrError` when the client is created.

---

### Sign in with an API key or a user token

The client authenticates in one of two ways. Use the API key and secret shown above, or a user access token to act as a signed-in Labellerr user:

```python
from labellerr import LabellerrClient

client = LabellerrClient.from_access_token(
    "<user access token>",
    client_id="<client id>",
    email_id="user@example.com",
)
```

Pass exactly one of `api_key` and `api_secret`, `access_token`, or `credentials=`. The `credentials=` argument takes an `ApiKeyCredentials(api_key, api_secret)` or a `BearerTokenCredentials(token)` object. Missing or empty credentials, or more than one kind, raise `AuthenticationError` when the client is created.

`access_token` may also be a zero-argument function that returns the token. The client calls it for every request, so a long-running program can return a refreshed token. The function must be a normal function, not `async def`; an async function raises `AuthenticationError`.

The function must be thread-safe. The SDK calls it from its own worker threads (`list_projects`, folder uploads, background pre-annotation polling). Those threads run in a copy of the caller's `contextvars` context, so a function that reads a `ContextVar` sees the caller's value.

A token given as `"Bearer <token>"` is sent once as `Bearer <token>`, not `Bearer Bearer <token>`. Keys, secrets and tokens must be ASCII; anything else raises `AuthenticationError` when the client is created (or, for a function, when it returns the token).

`client.api_key`, `client.api_secret` and `client.access_token` are read-only views of `client.credentials`. To log safely, scrub `client.credentials.secret_values()` from the text: it returns the key and secret, or the token, without calling a token function.

#### Settings and the default origin

Pass a `Settings` object as `settings=` to set `base_url`, `origin`, `source` (default `sdk`) or `user_agent`:

```python
from labellerr import LabellerrClient, Settings

settings = Settings(base_url="https://api.labellerr.com", origin="https://sdk.labellerr.com")
client = LabellerrClient.from_access_token("<user access token>", client_id="<client id>", settings=settings)
```

`base_url` must be an `https://` URL with a host; `http://` is accepted only for `localhost`, `127.0.0.1` and `::1`, so credentials are never sent in plain text. Anything else raises `ValueError` when the `Settings` is created.

A `Settings` you build is used as given. With no `settings=`, the client reads these variables when it is created, not at import time:

- `LABELLERR_BASE_URL`: the API base URL (default `https://api.labellerr.com`).
- `LABELLERR_ORIGIN`: the `origin` header. An empty value is ignored. When set, it applies to both kinds of client.

With no origin set, an API-key client sends `https://pro.labellerr.com`, the web app's origin. A token client sends `https://sdk.labellerr.com`. The gateway keeps one session per email and origin, so a token client that sent the web app's origin would sign the user out of the web app.

#### Errors

Failed API calls raise a subclass of `LabellerrError`, chosen by HTTP status:

| Exception | Status | Raised for |
| --- | --- | --- |
| `AuthenticationError` | 401 | Credentials are missing or invalid, or rejected before the request is sent |
| `PermissionDeniedError` | 403 | The caller may not perform this action |
| `NotFoundError` | 404 | The resource does not exist |
| `RateLimitError` | 429 | Too many requests |
| `ServerError` | 5xx | The API failed to handle the request |

Each error has `status_code`, `error_code` (the gateway's code, such as `TOKEN_INVALID`), `request_id` and `response_body` (the parsed JSON, or the text). They are `None` for errors raised in the client. `RateLimitError` also has `retry_after`, the seconds from the `Retry-After` header, or `None`.

Every request carries an `x-correlation-id` header: the `request_id` you pass, or a generated one. The error's `request_id` is that same value, so it can be found in the gateway's logs.

A failed pre-annotation job raises `JobFailedError` (with `job_id`); a job that does not finish in time raises `JobTimeoutError`.

The SDK logs through named loggers under `labellerr` (for example `labellerr.core.projects.base`) and never configures logging itself. To see its messages, configure logging in your application, e.g. `logging.getLogger("labellerr").setLevel(logging.INFO)`.

```python
import time
from labellerr import LabellerrError, RateLimitError

url = f"{client.base_url}/<path>"
try:
    result = client.make_request("GET", url, params={"client_id": "<client id>"})
except RateLimitError as e:
    time.sleep(e.retry_after or 5)
except LabellerrError as e:
    print(e.status_code, e.error_code, e.request_id)
```

#### Retries

The sync client retries on its own session, which it creates when connection pooling is on. It retries up to 3 times on 429, 500, 502, 503 and 504 responses, waiting 1 s, then 2 s, then 4 s (at most 10 s), plus up to 50% random jitter. A `Retry-After` of up to 10 s is waited for instead; with a longer one the client does not retry, and the `RateLimitError` carries `retry_after`. Only GET, HEAD, PUT, DELETE and OPTIONS are retried on those responses. POST is not, so a create call cannot run twice. Connection-establishment failures are retried for every method. When retries run out, the last response becomes the error above.

The async client does not retry. A session passed with `session=` gets no retry policy.

#### Sharing a connection pool

Pass your own `requests.Session` as `session=` to share a pool with other code:

```python
import requests

session = requests.Session()
client = LabellerrClient("your_api_key", "your_api_secret", "your_client_id", session=session)

client.close()   # leaves the session open
session.close()  # you close it
```

The client uses the session as given. It mounts no retry adapters on it and never closes it.

#### Async client

`AsyncLabellerrClient` takes the same `api_key`, `api_secret`, `access_token`, `credentials=` and `settings=` arguments. It has no `client_id` or `email_id` argument; its methods take the client ID as a parameter. A token provider must also be a normal function.

```python
from labellerr import AsyncLabellerrClient

async with AsyncLabellerrClient.from_access_token("<user access token>") as client:
    ...
```

---

### Creating a New Project

---

A **project** in Labellerr organizes your datasets and their annotations. Use the following method to create a project:

To know more about what is a project in Labellerr, [click here](https://labellerrknowbase.notion.site/How-to-Create-a-New-project-37bed9e50bc84d848dc997c33eb9955ahttps:/)

#### Limitations:

- Maximum of **2,500 files** per folder.
- Total folder size should not exceed **2.5 GB**.

#### Acceptable value:

* **option_type**
  * `'input'`, `'radio'`, `'boolean'`, `'select'`, `'dropdown'`, `'stt'`, `'imc'`, `'BoundingBox'`, `'polygon'`, `'dot'`, `'audio'`

#### Data Types and Supported Formats

The Labellerr SDK supports various data types and file formats for your annotation projects:

### Supported Data Types and Extensions


| Data Type  | Description                           | Supported Extensions                     |
| ------------ | --------------------------------------- | ------------------------------------------ |
| `image`    | Image files for visual annotation     | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff` |
| `video`    | Video content for temporal annotation | `.mp4`                                   |
| `audio`    | Audio files for sound annotation      | `.mp3`, `.wav`                           |
| `document` | Document files for text analysis      | `.pdf`                                   |
| `text`     | Plain text files for text annotation  | `.txt`                                   |

When using the SDK methods, specify the data type as one of: `'image'`, `'video'`, `'audio'`, `'document'`, or `'text'`.

#### Example Usage:

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')


project_payload = {
    'client_id': '12345',
    'dataset_name': 'Sample Dataset',
    'dataset_description': 'A sample dataset for image classification',
    'data_type': 'image',
    'created_by': 'user@example.com',
    'project_name': 'Image Classification Project',
    'annotation_guide': [
        {
            "question_number": 1,
            "question": "What is the main object in the image?",
            "question_id": "533bb0c8-fb2b-4394-a8e1-5042a944802f",
            "option_type": "dropdown",
            "required": True,
            "options": [
                {"option_name": "Car"},
                {"option_name": "Building"},
                {"option_name": "Person"}
            ]
        }
    ],
    'rotation_config': {
        'annotation_rotation_count': 0,
        'review_rotation_count': 1,
        'client_review_rotation_count': 0
    },
    'autolabel': False,
    'folder_to_upload': '/path/to/image/folder'
}

try:
    result = client.initiate_create_project(project_payload)
    print(f"Project created successfully. Project ID: {result['project_id']}")
except LabellerrError as e:
    print(f"Project creation failed: {e}")
```

---

## Uploading Pre-annotations

**Pre-annotations are labels which can be pre-loaded to a project which can speed up manual annotation**

#### Example Usage (Synchronous):

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')

project_id = 'project_123'
client_id = '12345'
annotation_format = 'coco'
annotation_file = '/path/to/annotations.json'

try:
    # Upload and wait for processing to complete
    result = client.upload_preannotation_by_project_id(project_id, client_id, annotation_format, annotation_file)

    # Check the final status
    if result['response']['status'] == 'completed':
        print("Pre-annotations processed successfully")
        # Access additional metadata if needed
        metadata = result['response'].get('metadata', {})
        print("metadata",metadata)
except LabellerrError as e:
    print(f"Pre-annotation upload failed: {e}")
```

#### Example Usage (Asynchronous):

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')


project_id = 'project_123'
client_id = '12345'
annotation_format = 'coco'
annotation_file = '/path/to/annotations.json'

try:
    # Start the async upload - returns immediately
    future = client.upload_preannotation_by_project_id_async(project_id, client_id, annotation_format, annotation_file)

    print("Upload started, you can do other work here...")

    # When you need the result, wait for completion
    try:
        result = future.result(timeout=300)  # 5 minutes timeout
        if result['response']['status'] == 'completed':
            print("Pre-annotations processed successfully")
            metadata = result['response'].get('metadata', {})
            print("metadata",metadata)
    except TimeoutError:
        print("Processing took too long")
    except Exception as e:
        print(f"Error in processing: {e}")
except LabellerrError as e:
    print(f"Failed to start upload: {e}")
```

#### Starting an upload and following the job yourself

`project.upload_preannotations(...)` uploads and waits (or, with `_async=True`, returns a `Future`). To upload and get the job ID back at once, then check the job when you choose, use `start_preannotation_upload` with `preannotation_job_status` (one request) or `wait_for_preannotation_job` (polls):

```python
from labellerr import JobFailedError
from labellerr.core.projects import LabellerrProject

project = LabellerrProject(client, "project_123")
job_id = project.start_preannotation_upload("coco_json", "/path/to/annotations.json")

status = project.preannotation_job_status(job_id)["response"]["status"]
# ... later
try:
    project.wait_for_preannotation_job(job_id, timeout=600, interval=5)
except JobFailedError as e:
    print(f"Job {e.job_id} failed")
```

`interval` must be at least 0.5 seconds and `timeout` must be `None` (wait forever) or a number of seconds >= 0; other values raise `LabellerrError` before anything is uploaded.

#### Choosing Between Sync and Async

1. **Synchronous Method**:

   - Simpler to use - just call and wait for result
   - Blocks until processing is complete
   - Good for scripts and sequential processing
2. **Asynchronous Method**:

   - Returns immediately with a Future object
   - Allows you to do other work while processing
   - Can set timeouts and handle long-running uploads
   - Better for applications that need to stay responsive

Both methods will:

1. Upload your annotation file
2. Monitor the processing status
3. Return the final result with complete status information

**Note**: The processing time depends on the size of your annotation file and the number of annotations. For the sync method, this means waiting time. For the async method, you can do other work during this time.

---

### Local Export

---

The SDK provides functionality to export project data locally. This feature allows you to export annotations in various formats for further analysis or backup purposes.

**The export created will be available in the exports section of Labellerr dashboard. To know more where you can find the export, [click here](https://labellerrknowbase.notion.site/How-to-create-an-Export-on-Labellerr-4ebeac49c29d44e8a294c5ab694267e8https:/)**

#### Acceptable values:

* statuses:
  * `'review'`, `'r_assigned'`,`'client_review'`, `'cr_assigned'`,`'accepted'`
* export_format:
  * `'json'`, `'coco_json'`, `'csv'`, `'png'`

#### Example Usage:

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')


project_id = 'project_123'
client_id = '12345'
export_config = {
    "export_name": "Weekly Export",
    "export_description": "Export of all accepted annotations",
    "export_format": "json",
    "statuses": ["accepted"]
}

try:
    result = client.create_local_export(project_id, client_id, export_config)
    print(f"Local export created successfully. Export ID: {result['export_id']}")
except LabellerrError as e:
    print(f"Local export creation failed: {e}")
```

**Note**: The export process creates a local copy of your project's annotations based on the specified status filters. This is useful for backup purposes or when you need to process the annotations offline.

---

### Retrieving All Projects for a Client

---

You can retrieve all projects associated with a specific client ID using the following method:

#### Example Usage:

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')

client_id = '12345'

try:
    result = client.get_all_project_per_client_id(client_id)

    # Check if projects were retrieved successfully
    if result and 'response' in result:
        projects = result['response']
        print(f"Found {len(projects)} projects:")
        for project in projects:
            print(f"- Project ID: {project.get('project_id')}")
            print(f"  Name: {project.get('project_name')}")
            print(f"  Type: {project.get('data_type')}")
except LabellerrError as e:
    print(f"Failed to retrieve projects: {e}")
```

This method is useful when you need to:

- List all projects for a client
- Find specific project IDs
- Check project statuses
- Get an overview of client's work

The response includes detailed information about each project, including its ID, name, data type, and other relevant metadata.

---

### Retrieving All Datasets

---

You can retrieve both linked and unlinked datasets associated with a client using the following method:

#### Example Usage:

```python
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError

# Initialize the client with your API credentials
client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')

client_id = '12345'
data_type = 'image'

try:
    result = client.get_all_datasets(client_id, data_type)

    # Process linked datasets
    linked_datasets = result['linked']
    print(f"Found {len(linked_datasets)} linked datasets:")
    for dataset in linked_datasets:
        print(f"- Dataset ID: {dataset.get('dataset_id')}")
        print(f"  Name: {dataset.get('dataset_name')}")
        print(f"  Description: {dataset.get('dataset_description')}")

    # Process unlinked datasets
    unlinked_datasets = result['unlinked']
    print(f"\nFound {len(unlinked_datasets)} unlinked datasets:")
    for dataset in unlinked_datasets:
        print(f"- Dataset ID: {dataset.get('dataset_id')}")
        print(f"  Name: {dataset.get('dataset_name')}")
        print(f"  Description: {dataset.get('dataset_description')}")

except LabellerrError as e:
    print(f"Failed to retrieve datasets: {e}")
```

This method is useful when you need to:

- Get an overview of all available datasets
- Find datasets that are linked to projects
- Identify unlinked datasets that can be associated with new projects
- Manage dataset organization and project associations

The response includes two lists:

- `linked`: Datasets that are already associated with projects
- `unlinked`: Datasets that are not yet associated with any project

Each dataset object contains detailed information including its ID, name, description, and other metadata.

---

## Error Handling

The Labellerr SDK uses a custom exception class, `LabellerrError`, to indicate issues during API interactions. Always wrap your function calls in `try-except` blocks to gracefully handle errors.

#### Example:

```python
from labellerr.exceptions import LabellerrError

try:
    result = client.create_project(payload)
except LabellerrError as e:
    print(f"An error occurred: {e}")
```

---

## Automatic Logging and Error Handling

The Labellerr SDK uses **class-level decorators** to automatically apply logging and error handling to all public methods in both `LabellerrClient` and `AsyncLabellerrClient`. This means every method call is automatically:

1. **Logged** when the method is called
2. **Logged** when the method completes successfully
3. **Logged** with error details if the method fails
4. **Wrapped** with standardized error handling

### Benefits

**No Boilerplate**: You don't need to add logging or error handling code in every method
**Consistency**: All methods follow the same logging pattern
**Maintainability**: Changes to logging or error handling are centralized
**Debugging**: Comprehensive logs help troubleshoot issues quickly

### How It Works

The SDK uses two decorators:
- `@auto_log_and_handle_errors` for synchronous methods
- `@auto_log_and_handle_errors_async` for asynchronous methods

These decorators are applied at the class level, so all public methods (methods not starting with `_`) automatically inherit them.

### Example Log Output

When you call a method, you'll see debug logs like:

```
DEBUG - Calling create_gcs_connection
DEBUG - create_gcs_connection completed successfully
```

Or if an error occurs:

```
DEBUG - Calling create_gcs_connection
ERROR - create_gcs_connection failed: Connection refused
```

### Enabling Debug Logging

To see the automatic logging in action, configure Python's logging:

```python
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from labellerr.client import LabellerrClient

client = LabellerrClient('your_api_key', 'your_api_secret', 'your_client_id')

# Now all method calls will be automatically logged
client.create_dataset(dataset_config, files_to_upload=['file1.jpg'])
```

### Excluded Methods

Some methods are excluded from automatic decoration:
- Private methods (starting with `_`)
- Utility methods like `close()`, `validate_rotation_config()`
- Session management methods

### Custom Implementation

If you're building your own client or extending the SDK, you can use the same decorators:

```python
from labellerr.validators import auto_log_and_handle_errors

@auto_log_and_handle_errors(
    include_params=False,  # Don't log sensitive parameters
    exclude_methods=['close', 'cleanup']  # Skip these methods
)
class MyCustomClient:
    def my_method(self):
        # This method automatically gets logging and error handling
        pass

    def close(self):
        # This method is excluded from decoration
        pass
```

---

## Support

If you encounter issues or have questions, feel free to contact the Labellerr support team:

- **Email**: support@labellerr.com
- **Documentation**: [Labellerr Documentation](https://docs.labellerr.com)
