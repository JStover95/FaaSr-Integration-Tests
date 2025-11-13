# FaaSr-Integration-Tests

The FaaSr Integration Tests repository can be used for running end-to-end tests of changes to the [FaaSr-Backend](https://github.com/FaaSr/FaaSr-Backend) library, [FaaSr-Workflow](https://github.com/FaaSr/FaaSr-workflow) repository, or [FaaSr-Docker](https://github.com/FaaSr/FaaSr-Docker) containers.

## Overview

This repository contains the following main folders:

- **`docker`:** Dockerfiles for custom Docker containers.
- **`faasr_workflow`:** The FaaSr-workflow repository, included as a git subtree.
- **`framework`:** The integration testing framework.
- **`functions`:** Integration test functions.
- **`integration_tests`:** Integration tests written with `pytest`.
- **`workflows`:** Integration test workflows

## Getting Started

To contribute workflows for integration testing, it is recommended to fork this repository and create a pull request with your integration test.

After forking the repository, initialize your Python environment with `uv`:

```bash
uv sync
source .venv/bin/activate
```

Next, make a copy of [`.env.template`](./.env.template) named `.env` and initialize the following variables:

| Variable | Description |
| - | - |
| `GH_PAT` | Your GitHub personal access token. |
| `GITHUB_REPOSITORY` | The name of your forked repository. |
| `GITHUB_REF_NAME` | The branch containing your workflow file. |
| `S3_ACCESSKEY`, `S3_SECRETKEY` | Your S3 credentials. |
| `AWS_AccessKey`, `AWS_SecretKey` | Your AWS credentials, if needed. |
| `OW_APIkey` | Your OpenWhisk credentials, if needed. |
| `GCP_SecretKey` | You Google Cloud Platform credentials, if needed. |
| `SLURM_Token` | Your Slurm credentials, if needed. |

### Optional VSCode Setup

If using VSCode, this repo contains a [`settings.template.json`](./.vscode/settings.template.json) file with some pre-configured settings:

- Automatic Python formatting with Ruff.
- `pytest` configuration that is required to use the VSCode testing UI.
- Additional configuration for Python, the editor, and cSpell.

This repo also includes recommended VSCode extensions:

- **Ruff:** A Python linter and formatter.
- **markdownlint:** A Markdown linter and formatter.
- **cSpell:** A code spell checker.

## Creating an Integration Test

When creating your own integration test, it is recommended to follow this pattern:

1. Commit the Dockerfiles of any custom containers to the `docker` directory.
2. Commit the workflow's functions to the `functions` directory.
3. Commit the workflow's schema to the `workflows` directory.
4. Commit your tests written with `pytest` to the `integration_tests` directory.

When finished, create a pull request. Then, when you contribute your proposed changes, you can link to your pull request on this repo.

## Writing Tests

> ℹ️ Tests are executed in the order they are listed in a file. When possible, it is recommended to write tests for functions in the order you expect the functions to complete.

The testing framework is wrapped in the pytest fixture named `workflow_file`. Use this fixture with a `module` scoped `tester` fixture:

> ⚠️ Using `scope="module"` ensures that the workflow runner is invoked _once_ for the entire test module. Omitting this will result in the workflow runner being re-invoked for every test.

```python
@pytest.fixture(scope="module", autouse=True)
def tester(workflow_file):
    with workflow_file("workflows/IntegrationTestWorkflow.json") as tester:
        yield tester
```

You can now use this tester to make assertions against your workflow.

### Test Data Store Outputs

```py
def test_py_api(tester: WorkflowTester):
    tester.wait_for("test_py_api")

    # Test that input1 does not exist
    tester.assert_object_does_not_exist("input1.txt")

    # Test that input2 exists
    tester.assert_object_exists("input2.txt")

    # Test that input3 matches the expected content
    tester.assert_content_equals("input3.txt", "content")
```

### Test Conditional Function Invocations

```py
# Test that a function was not invoked
def test_dont_run_on_true(tester: WorkflowTester):
    tester.wait_for("dont_run_on_true")
    tester.assert_function_not_invoked("dont_run_on_true")


# Test that a function completed
def test_run_on_true(tester: WorkflowTester):
    tester.wait_for("run_on_true")
    tester.assert_function_completed("run_on_true")
```

### Test Ranked Function Invocations

```py
# Test for a function with rank 1
def test_red_1(tester: WorkflowTester):
    tester.wait_for("test_ranked(1)")
    tester.assert_function_completed("test_ranked(1)")


# Test for a function with rank 2
def test_ranked_2(tester: WorkflowTester):
    tester.wait_for("test_ranked(2)")
    tester.assert_function_completed("test_ranked(2)")
```

## Running Tests

Tests can either be invoked from the VS Code testing UI or from the command line:

```bash
pytest integration_tests/<Path to Your Test File>

# Run tests while capturing input, including function logs:
pytest -s integration_tests/<Path to Your Test File>

# Run tests with verbose output for debugging complex assertions:
pytest [-v|-vv] integration_tests/<Path to Your Test File>
```

## Programmatic Usage

The `WorkflowRunner` class can be used programmatically for more control:

> ℹ️ Note that for the workflow file to be captured by `invoke_workflow.py`, it must be passed as the command line argument `--workflow-file`.

```python
import argparse

from framework.workflow_runner import WorkflowRunner

parser = argparse.ArgumentParser()
parser.add_argument("--workflow-file", type=str, required=True)
args = parser.parse_args()

# Trigger the workflow
runner = WorkflowRunner.trigger_workflow(
    timeout=300,
    check_interval=2,
    stream_logs=True
)

# Monitor status changes
while not runner.is_monitoring_complete():
    statuses = runner.get_function_statuses()
    # Process status updates
    time.sleep(1)

# Cleanup
runner.cleanup()
```

### Function Status States

The workflow runner tracks the following function states:

- **`PENDING`**: Waiting to start
- **`INVOKED`**: Invoked by any function
- **`NOT_INVOKED`**: Not invoked by any function
- **`RUNNING`**: Currently executing
- **`COMPLETED`**: Finished successfully
- **`FAILED`**: Encountered an error
- **`SKIPPED`**: Skipped due to upstream failure
- **`TIMEOUT`**: Was in a non-complete state when the workflow timed out.

### Thread Safety

The Workflow Runner is designed to be thread-safe:

- All status updates and logs are protected by locks
- Safe for concurrent access from multiple threads
- Graceful shutdown handling prevents race conditions
- Clean resource management and cleanup

## Updating the `FaaSr-workflow` Subtree

The `FaaSr-workflow` repository is included as a git submodule. Changes to the upstream repository can be done automatically with `pull_faasr_workflow.sh`.

If you are testing changes that you made to a fork or branch of the `FaaSr-workflow` repository, you will have to pull them manually with the following `git subtree` command:

```bash
git subtree pull \
    --prefix faasr_workflow git@github.com:<Username>/<Repo Name>.git \
    --squash \
    -m "Pull Faasr-workflow subtree" \
    <Branch Name>
```

## Script Reference

### `register_workflow.sh`

Register a workflow on your repository. This calls the FaaSr-workflow `register_workflow.py` script and immediately pull the latest changes to the remote branch.

**Options:**

- **`-f|--workflow-file`:** The file of the workflow to register.
- **`-c|--custom-container`:** Allow custom containers.
- **`-h|--help`:** Show a help message.

**Example usage:**

```bash
./register-workflow.sh -f workflows/IntegrationTestWorkflow.json

# Register a workflow with custom containers enabled
./register-workflow.sh -f workflows/IntegrationTestWorkflow.json -c
```

### `invoke_workflow.sh`

Invoke a workflow and monitor its progress. This calls the testing framework's Workflow Runner directly.

**Options:**

- **`-f|--workflow-file`:** The file of the workflow to invoke.
- **`-h|--help`:** Show a help message.

**Example usage:**

```bash
./invoke-workflow.sh -f workflows/IntegrationTestWorkflow.json
```

### `pull_faasr_workflow.sh`

Pull the latest changes from the upstream FaaSr-workflow repo to the FaaSr-workflow subtree. See [Updating the `FaaSr-workflow` Subtree](#updating-the-faasr-workflow-subtree).

## Framework Reference

### [`WorkflowTester`](./integration_tests/conftest.py)

A tester for a FaaSr workflow.

This class is responsible for:

- Triggering a workflow
- Cleaning up resources
- Asserting that objects exist in S3
- Asserting that objects do not exist in S3
- Asserting that the content of an object in S3 equals the expected content.
- Asserting that a function has completed.
- Asserting that a function has not been invoked.

#### `WorkflowTester.s3_client -> FaaSrS3Client`

Get the workflow runner's S3 client.

#### `WorkflowTester.get_s3_key(self, file_name: str) -> str`

Get the S3 key for a given file name.

**Args:**

- **`file_name`:** The name of the file to get the S3 key for.

**Returns:** The S3 key for the given file name.

#### `WorkflowTester.wait_for(self, function_name: str) -> FunctionStatus`

Wait for a function to complete.

**Args:**

- **`function_name`:** The name of the function to wait for.

**Returns:** The status of the function.

**Raises:**

- **`Exception`:** If the function failed, skipped, timed out, or not invoked.

#### `WorkflowTester.assert_object_exists(self, object_name: str) -> None`

Assert that an object exists in S3.

**Args:**

- **`object_name`:** The name of the object to assert exists.

#### `WorkflowTester.assert_object_does_not_exist(self, object_name: str) -> None`

Assert that an object does not exist in S3.

**Args:**

- **`object_name`:** The name of the object to assert does not exist.

#### `WorkflowTester.assert_content_equals(self, object_name: str, expected_content: str) -> None`

Assert that the content of an object in S3 equals the expected content.

**Args:**

- **`object_name`:** The name of the object to assert the content of.
- **`expected_content`:** The expected content of the object.

#### `WorkflowTester.assert_function_completed(self, function_name: str) -> None`

Assert that a function has completed.

**Args:**

- **`function_name`:** The name of the function to assert has completed.

#### `WorkflowTester.assert_function_not_invoked(self, function_name: str) -> None`

Assert that a function has not been invoked.

**Args:**

- **`function_name`:** The name of the function to assert has not been invoked.

### [`WorkflowRunner`](./framework/workflow_runner.py)

Runs a FaaSr workflow and monitors the execution of the functions.

This class is responsible for:

- Validating the environment
- Setting up the logger
- Building the adjacency graph
- Initializing the function statuses
- Initializing the S3 client
- Setting up the signal handlers
- Starting the monitoring thread
- Shutting down the monitoring thread
- Cleaning up the resources

#### `WorkflowRunner(*, faasr_payload: FaaSrPayload, timeout: int, check_interval: int, stream_logs: bool = False)`

**Args:**

- **`faasr_payload`:** The FaaSr payload.
- **`timeout`:** The timeout for the monitoring thread.
- **`check_interval`:** The interval for the monitoring thread.
- **`stream_logs`:** Whether to stream the logs to the console.

**Raises:**

- **`InitializationError`:** If the environment is not valid.

#### `WorkflowRunner.invocation_id -> str`

Get the invocation ID of the workflow.

#### `WorkflowRunner.monitoring_complete -> bool`

Check if monitoring is complete (thread-safe).

**Returns:** `True` if monitoring is complete, `False` otherwise.

#### `WorkflowRunner.shutdown_requested -> bool`

Check if a shutdown request has been made (thread-safe).

**Returns:** `True` if a shutdown request has been made, `False` otherwise.

#### `WorkflowRunner.get_function_statuses() -> dict[str, FunctionStatus]`

Get a copy of function statuses (thread-safe).

**Returns:** A copy of the function statuses.

#### `WorkflowRunner.shutdown(timeout: float = None) -> bool`

Attempt to gracefully shutdown the monitoring thread.

**Args:**

- **`timeout`:** Maximum time to wait for graceful shutdown (default: `self._cleanup_timeout`)

**Returns:** `True` if shutdown was successful, `False` if timeout occurred

#### `WorkflowRunner.force_shutdown() -> None`

Force shutdown of the monitoring thread.

#### `WorkflowRunner.cleanup() -> None`

Comprehensive cleanup of all resources.

This method should be called when the runner is no longer needed.

#### `WorkflowRunner.trigger_workflow(timeout: int, check_interval: int, stream_logs: bool = False) -> WorkflowRunner`

Trigger a workflow and initialize the workflow runner.

**Args:**

- **`timeout`:** The timeout for the monitoring thread.
- **`check_interval`:** The interval for the monitoring thread.
- **`stream_logs`:** Whether to stream the logs to the console.

**Returns:** The initialized workflow runner.

### [`FaaSrS3Client`](./framework/s3_client.py)

A client for interacting with FaaSr S3 datastores.

This class is responsible for:

- Initializing the S3 client
- Checking if objects exist in S3
- Getting objects from S3

#### `FaaSrS3Client(*, workflow_data: dict[str, Any], access_key: str, secret_key: str)`

**Args:**

- **`workflow_data`:** The workflow data.
- **`access_key`:** The access key.
- **`secret_key`:** The secret key.

**Raises:**

- **`S3ClientInitializationError`:** If the S3 client initialization fails.

#### `FaaSrS3Client.object_exists(key: str) -> bool`

Check if the object exists in S3.

**Args:**

- **`key`:** The key of the object to check.

**Returns:** `True` if the object exists, `False` otherwise.

**Raises:**

- **`S3ClientError`:** If an error occurs.

#### `FaaSrS3Client.get_object(key: str, encoding: str = "utf-8") -> str`

Get the object from S3.

**Args:**

- **`key`:** The key of the object to get.
- **`encoding`:** The encoding to use for the object.

**Returns:** The object content.

**Raises:**

- **`S3ClientError`:** If the object does not exist or an error occurs.

### [`FaaSrFunction`](./framework/faasr_function.py)

Manages the execution status and monitoring of a single FaaSr function.

This class is responsible for:

- Tracking function execution status
- Listening to logger events and updating status reactively
- Tracking invocations from log analysis
- Managing function completion and failure detection

#### `FaaSrFunction.status -> FunctionStatus`

Get the current function status (thread-safe).

**Returns:** The current status of the function.

#### `FaaSrFunction.done_key -> str`

Get the complete `.done` file S3 key.

This replaces ranks with the expected format (e.g. "function(1)" -> "function.1.done").

**Returns:** The S3 key for the done file.

#### `FaaSrFunction.invocations -> set[str] | None`

Get the invocations (thread-safe).

**Returns:** The invocations.

#### `FaaSrFunction.logs -> list[str]`

Get the logs as a list (thread-safe).

#### `FaaSrFunction.logs_content -> str`

Get the logs as a string (thread-safe).

#### `FaaSrFunction.logs_complete -> bool`

Get the logs complete flag (thread-safe).

#### `FaaSrFunction.function_complete -> bool`

Get the function complete flag (thread-safe).

#### `FaaSrFunction.function_failed -> bool`

Get the function failed flag (thread-safe).

#### `FaaSrFunction.set_status(status: FunctionStatus) -> None`

Set the function status (thread-safe).

**Args:**

- **`status`:** The new status to set.

#### `FaaSrFunction.start() -> None`

Start monitoring the function.

### [`FaaSrFunctionLogger`](./framework/faasr_function_logger.py)

Handles log monitoring and fetching for a single FaaSr function.

This class is responsible for:

- Monitoring logs on S3 for a specific function
- Fetching and storing log content
- Providing event-driven callbacks for log updates
- Tracking log completion status

#### `FaaSrFunctionLogger(*, function_name: str, workflow_name: str, invocation_folder: str, s3_client: FaaSrS3Client, stream_logs: bool = False, interval_seconds: int = 3)`

**Args:**

- **`function_name`:** The name of the function.
- **`workflow_name`:** The name of the workflow.
- **`invocation_folder`:** The folder where the logs are stored.
- **`s3_client`:** The S3 client to use.
- **`stream_logs`:** Whether to stream the logs to the console.
- **`interval_seconds`:** The interval in seconds to check for new logs.

#### `FaaSrFunctionLogger.logs -> list[str]`

Get the logs as a list (thread-safe).

**Returns:** The logs.

#### `FaaSrFunctionLogger.logs_content -> str`

Get the logs as a string (thread-safe).

**Returns:** The logs content.

#### `FaaSrFunctionLogger.logs_key -> str`

Get the complete logs S3 key.

**Returns:** The S3 key for the logs.

#### `FaaSrFunctionLogger.logs_started -> bool`

Get the logs started flag (thread-safe).

**Returns:** `True` if logs have started appearing on S3.

#### `FaaSrFunctionLogger.logs_complete -> bool`

Get the logs complete flag (thread-safe).

This is True when the `.done` file exists and no new logs were fetched after a monitoring cycle.

**Returns:** `True` if logs are complete, `False` otherwise.

#### `FaaSrFunctionLogger.stop_requested -> bool`

Get the stop flag (thread-safe).

**Returns:** `True` if the logger's stop flag is set, `False` otherwise.

#### `FaaSrFunctionLogger.register_callback(callback: Callable[[LogEvent], None]) -> None`

Register a callback to be called when log events occur.

**Args**:

- **`callback:`** Function to call with LogEvent parameter

#### `FaaSrFunctionLogger.start() -> None`

Start the FaaSrFunctionLogger.

#### `FaaSrFunctionLogger.stop() -> None`

Stop the FaaSrFunctionLogger.

### [`LogEvent`](./framework/faasr_function_logger.py)

Events that can be triggered by the FaaSrFunctionLogger

**Class attributes:**

- **`LOG_CREATED`:** `log_created`
- **`LOG_UPDATED`:** `log_updated`
- **`LOG_COMPLETE`:** `log_complete`
