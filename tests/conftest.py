import os
import sys
from contextlib import suppress
from typing import Any, Generator

import boto3
import pytest
import requests
from mypy_boto3_s3.client import S3Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATASTORE_ENDPOINT = "http://localhost:5000"
DATASTORE_BUCKET = "testing"
DATASTORE_REGION = "us-east-1"


def datastore_config() -> dict[str, Any]:
    return {
        "Endpoint": DATASTORE_ENDPOINT,
        "Bucket": DATASTORE_BUCKET,
        "Region": DATASTORE_REGION,
    }


def workflow_data() -> dict[str, Any]:
    return {
        "DefaultDataStore": "S3",
        "DataStores": {
            "S3": datastore_config(),
        },
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
