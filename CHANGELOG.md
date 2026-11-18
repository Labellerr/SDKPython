# Changelog

## 1.4.0

Sign in as a Labellerr user with an access token, alongside the API key and secret.

### New

- `LabellerrClient.from_access_token(token, client_id, email_id=None)` and
  `AsyncLabellerrClient.from_access_token(token)`. The token may be a string or a
  zero-argument function that returns the current token (called for every request).
- `credentials=` with `ApiKeyCredentials(api_key, api_secret)` or
  `BearerTokenCredentials(token)`. `Credentials.secret_values()` returns the secrets
  for log scrubbing without calling a token function.
- `settings=Settings(base_url=..., origin=..., source=..., user_agent=...)`. Without
  it, `LABELLERR_BASE_URL` and `LABELLERR_ORIGIN` are read when the client is created.
- `session=` to pass your own `requests.Session`.
- Typed errors, all subclasses of `LabellerrError`: `AuthenticationError` (401),
  `PermissionDeniedError` (403), `NotFoundError` (404), `RateLimitError` (429, with
  `retry_after`), `ServerError` (5xx), `JobTimeoutError`, `JobFailedError` (with
  `job_id`). Each carries `status_code`, `error_code`, `request_id` and
  `response_body`.
- `APIConnectionError` (the connection failed or dropped) and its subclass
  `APITimeoutError`, both `LabellerrError`s. `make_request` and the async client raise
  them instead of `requests` / `aiohttp` exceptions; the original exception is the
  `__cause__`.
- `project.start_preannotation_upload(...)` returns the job ID without waiting;
  `project.preannotation_job_status(job_id)` checks a job with one request;
  `project.wait_for_preannotation_job(job_id, timeout, interval)` polls.
- `client.caller_identity`.

### Behaviour changes

Check these before upgrading.

- **`client_id` is required.** `LabellerrClient(...)` and `from_access_token(...)`
  raise `LabellerrError` when it is missing or blank (it was required positionally in
  1.3; the token work had briefly made it optional). It is stored as a string.
- **POST is no longer retried automatically.** Retries (3, on 429/500/502/503/504)
  apply only to GET, HEAD, PUT, DELETE and OPTIONS. Connection-establishment errors are
  still retried for every method.
- **Retry backoff changed.** The first retry now waits 1 s (it used to retry at once),
  doubling up to 10 s, plus up to 50% jitter. A `Retry-After` of up to 10 s is waited
  for; a longer one is not retried and the `RateLimitError` carries `retry_after`.
- **`upload_preannotations` stops after 3600 s by default** (it used to wait forever)
  and raises `JobTimeoutError`. Pass `timeout=None` to wait forever.
- **`upload_preannotations(_async=True)` returns immediately** with a
  `concurrent.futures.Future`; it used to block until the job finished.
- **Polling arguments are validated.** `interval` must be at least 0.5 s and
  `timeout` `None` or >= 0, in `upload_preannotations`, `wait_for_preannotation_job`
  and `preannotation_job_status_async`; otherwise `LabellerrError` is raised before
  the upload.
- **`status()` raises errors instead of hiding them.** `dataset.status()`,
  `project.status()` and `Export.status()` retry only transient errors (5xx, 429,
  connection problems). Any other error, such as a 401 from an expired token or a
  404, is raised on the first request. Before, these were logged and polling went on
  forever, or returned `None` when a timeout was set. When the timeout passes before
  any status was received, `JobTimeoutError` is raised (chained from the last error)
  instead of returning `None`. `labellerr.core.utils.poll()` behaves the same way.
- **`status()` stops after 3600 s by default** and returns the last status received.
  Pass `timeout=None` to poll until done. `project.status()` now also takes
  `interval`, `timeout` and `max_retries`, and all three validate `interval` and
  `timeout` like the pre-annotation methods. The 0.5 s floor is now
  `labellerr.core.utils.MIN_POLL_INTERVAL`; `MIN_PREANNOTATION_POLL_INTERVAL` is an
  alias kept for compatibility.
- **Network errors are `APIConnectionError` / `APITimeoutError`.** Code that caught
  `requests.exceptions.ConnectionError`, `requests.exceptions.Timeout` or
  `aiohttp.ClientError` from SDK calls must catch these (or `LabellerrError`) instead.
- **`create_export` raises when the response has no report ID**, instead of
  returning an `Export` with `report_id=None`.
- **A failed pre-annotation job raises `JobFailedError`** (a `LabellerrError`; the
  message still starts with `Failed to get preannotation job status:`). Other errors
  while polling are no longer re-wrapped in a plain `LabellerrError`.
- **`Invalid*Error` classes now subclass `LabellerrError`** (`InvalidDatasetError`,
  `InvalidProjectError`, `InvalidDatasetIDError`, `InvalidConnectionError`,
  `InvalidAnnotationTemplateError`), so `except LabellerrError` catches them.
- **`list_projects` raises on a server error.** It skips only projects that answer
  404 or have an unknown type (and logs how many it skipped). A 5xx, 401, 403 or 429
  is raised instead of returning a shorter (or empty) list.
- **Folder uploads stop on caller errors.** `AuthenticationError`,
  `PermissionDeniedError` and `RateLimitError` from a batch are raised at once instead
  of ending as "All file uploads failed".
- **Token clients send `origin: https://sdk.labellerr.com`** by default (API-key
  clients still send `https://pro.labellerr.com`). Set `Settings(origin=...)` or
  `LABELLERR_ORIGIN` to change it.
- **`base_url` is validated:** `https://` with a host, or `http://` only for
  localhost. Other values raise `ValueError` when the client is created.
- **Credentials are checked when the client is created:** a leading `Bearer ` is
  removed from tokens, and non-ASCII keys, secrets or tokens raise
  `AuthenticationError`.
- **`client.api_key`, `client.api_secret` and `client.access_token` are read-only**
  (they never changed authentication; assigning to them now raises `AttributeError`).
- **`Credentials` is an abstract base class** with abstract `auth_headers()` and
  `secret_values()`.
- **Every request sends `x-correlation-id`**: the `request_id` passed, or a generated
  one. The error's `request_id` is the same value.
- **Unexpected non-error statuses** (e.g. a 202 or 204 the call did not expect) are no
  longer reported as "internal server error"; the error says "unexpected response".
- **Header values**: numbers and UUIDs are sent as strings; other non-string values
  raise `TypeError` before the request is sent.
- **Logging**: the SDK logs through named loggers (`logging.getLogger(__name__)`,
  under `labellerr`) and no longer calls the root logger, which could configure the
  application's logging.
- **`labellerr.core.constants.BASE_URL` and `ALLOWED_ORIGINS` are deprecated** and
  warn (`DeprecationWarning`) when read; use `client.base_url` / `client.settings`.
- **`client_utils.build_headers` has a new signature**
  (`credentials, settings, client_id=None, extra_headers=None, source=None`), and
  `client_utils.request` was removed; use `client.make_request`.

### Fixed

- `AsyncLabellerrClient.create_dataset` always raised `AttributeError`
  (`constants.DATA_TYPES` does not exist); it now validates against
  `DatasetDataType`. The unused `validate_data_type` decorators that used the same
  missing name were removed.
- `get_direct_upload_url` now sends its `client_id`, `purpose` and `file_name` query
  parameters.
- `project.import_users` and `AsyncLabellerrClient.get_dataset` sent a `uuid` query
  parameter that differed from the `x-correlation-id` header; both now use one ID.
