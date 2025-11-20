import os
from contextlib import suppress
from typing import Any, Generator

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3.client import S3Client

DATASTORE_ENDPOINT = "https://s3.us-east-1.amazonaws.com"
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
    with mock_aws():
        yield


@pytest.fixture()
def s3_client(with_mock_aws: None) -> S3Client:
    return boto3.client("s3", endpoint_url=DATASTORE_ENDPOINT)
