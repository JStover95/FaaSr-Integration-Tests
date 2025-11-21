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

After creating your workflow, use the `register-workflow.sh` script to register it with GitHub Actions. For example:

> ℹ️ `-c|--custom-container` is required to register the workflow with custom Docker containers.

```bash
./register-workflow.sh --workflow-file <Path to Your Workflow File> -c
```

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

### Waiting for Function Completion

The `tester.wait_for` function will wait until your function either reaches a **Not Invoked** or **Completed** state. For cases when it is necessary to test some behavior on function failure, you can optionally pass `should_fail=True` to wait for your function to reach a **Failed** state.

### Assertion Functions

The `tester` fixture has the following assertion functions that you can use to test the function's state or output:

- **`assert_object_exists(object_name: str)`:** Assert that an object exists in S3.

- **`assert_object_does_not_exist(object_name: str)`:** Assert that an object does not exist in S3.

- **`assert_content_equals(object_name: str, expected_content: str)`:** Assert that the content of an object in S3 equals the expected content.

- **`assert_logs_contain(function_name: str, expected_content: str)`:** Assert that the logs of a function contain the expected content.

- **`assert_function_completed(function_name: str)`:** Assert that a function has completed.

- **`assert_function_not_invoked(function_name: str)`:** Assert that a function has not been invoked.

- **`assert_function_failed(function_name: str)`:** Assert that a function has failed.

### Test Examples

#### Test Data Store Outputs

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

#### Test Log Outputs

```python
# Test that some text exists in the function logs
def test_log_outputs(tester: WorkflowTester):
    tester.wait_for("test_logs_function")
    tester.assert_logs_contain("test_logs_function", "Test log output")
```

#### Test Conditional Function Invocations

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

#### Test Ranked Function Invocations

```py
# Test for a function with rank 1
def test_ranked_1(tester: WorkflowTester):
    tester.wait_for("test_ranked(1)")
    tester.assert_function_completed("test_ranked(1)")


# Test for a function with rank 2
def test_ranked_2(tester: WorkflowTester):
    tester.wait_for("test_ranked(2)")
    tester.assert_function_completed("test_ranked(2)")
```

#### Test Failure States

```py
# Test any expected behavior on function failure
def test_failure(tester: WorkflowTester):
    tester.wait_for("test_failure_function", should_fail=True)
    tester.assert_logs_contain("test_failure_function", "Custom exception")
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

## Design Documentation

This repository includes [design documentation](./docs/design-docs.md) that is intended to be a single source of truth for design patterns. The design documentation should be amended regularly to document design choices that should be observed in future contributions.

## Unit Tests

This repo includes unit tests for the testing framework that are written in [`tests/`](./tests/). Running unit tests requires [moto](https://docs.getmoto.org/en/latest/index.html) to be run in server mode, either using Docker or Homebrew. See the [moto documentation](https://docs.getmoto.org/en/latest/docs/server_mode.html#run-using-docker) for more details.

For details on how moto is used for unit tests, refer to the [Mocking Strategies](./docs/testing/mocking-strategies.md) design doc.
