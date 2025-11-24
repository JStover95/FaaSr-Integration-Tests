import os
import sys
from contextlib import suppress
from typing import Any, Generator

import boto3
import pytest
import requests
from dotenv import load_dotenv
from mypy_boto3_s3.client import S3Client

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WORKFLOW_NAME = "test_workflow"
FUNCTION_INVOKE = "func1"
INVOCATION_ID = "test-invocation-123"
INVOCATION_TIMESTAMP = "2024-01-01T00:00:00Z"
DEFAULT_DATASTORE = "S3"
FAASR_LOG = "faasr-logs"
DATASTORE_ENDPOINT = "http://localhost:5000"
DATASTORE_BUCKET = "testing"
DATASTORE_REGION = "us-east-1"


def datastore_config() -> dict[str, Any]:
    return {
        "Endpoint": DATASTORE_ENDPOINT,
        "Bucket": DATASTORE_BUCKET,
        "Region": DATASTORE_REGION,
    }


def action_list() -> dict[str, Any]:
    return {
        "func1": {
            "FaaSServer": "GH",
            "FunctionName": "func1",
            "Type": "Python",
            "InvokeNext": ["func2", "func3"],
        },
        "func2": {
            "FaaSServer": "GH",
            "FunctionName": "func2",
            "Type": "Python",
            "InvokeNext": ["func4"],
        },
        "func3": {
            "FaaSServer": "GH",
            "FunctionName": "func3",
            "Type": "Python",
            "InvokeNext": ["func4"],
        },
        "func4": {
            "FaaSServer": "GH",
            "FunctionName": "func4",
            "Type": "Python",
            "InvokeNext": ["func5(3)"],
        },
        "func5": {
            "FaaSServer": "GH",
            "FunctionName": "func5",
            "Type": "Python",
        },
    }


def compute_servers() -> dict[str, Any]:
    return {
        "GH": {
            "FaaSType": "GitHubActions",
            "UserName": "test_user",
            "ActionRepoName": "test_repo",
        },
    }


def workflow_data() -> dict[str, Any]:
    """
    Create a FaaSr payload dictionary for testing.
    Returns a new instance each time to avoid test isolation issues.
    """
    return {
        "WorkflowName": WORKFLOW_NAME,
        "FunctionInvoke": FUNCTION_INVOKE,
        "InvocationID": INVOCATION_ID,
        "InvocationTimestamp": INVOCATION_TIMESTAMP,
        "FaaSrLog": FAASR_LOG,
        "DefaultDataStore": DEFAULT_DATASTORE,
        "ActionList": action_list(),
        "ComputeServers": compute_servers(),
        "DataStores": {
            "S3": datastore_config(),
        },
    }


def reverse_adj_graph() -> dict[str, set[str]]:
    return {
        "func1": {"func2", "func3"},
        "func2": set(),
        "func3": set(),
    }


@pytest.fixture()
def with_mock_env() -> Generator[None]:
    env = os.environ.copy()

    try:
        os.environ["AWS_ENDPOINT_URL"] = DATASTORE_ENDPOINT
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["GH_PAT"] = "testing"
        os.environ["GITHUB_REPOSITORY"] = "testing"
        os.environ["GITHUB_REF_NAME"] = "testing"
        os.environ["S3_AccessKey"] = "testing"
        os.environ["S3_SecretKey"] = "testing"
        os.environ["AWS_AccessKey"] = "testing"
        os.environ["AWS_SecretKey"] = "testing"
        os.environ["OW_APIkey"] = "testing"
        os.environ["GCP_SecretKey"] = "testing"
        os.environ["SLURM_Token"] = "testing"

        with suppress(KeyError):
            del os.environ["AWS_PROFILE"]

    finally:
        os.environ.clear()
        os.environ.update(env)


@pytest.fixture()
def with_mock_aws(with_mock_env: None) -> Generator[None]:
    try:
        yield
    finally:
        requests.post(f"{DATASTORE_ENDPOINT}/moto-api/reset")


@pytest.fixture()
def s3_client(with_mock_aws: None) -> S3Client:
    return boto3.client("s3", endpoint_url=DATASTORE_ENDPOINT)
