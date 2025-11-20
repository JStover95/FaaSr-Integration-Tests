import os
from typing import Generator

import pytest
from moto import mock_aws


@pytest.fixture(scope="session")
def with_mock_env() -> Generator[None]:
    env = os.environ.copy()

    try:
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

    finally:
        os.environ.clear()
        os.environ.update(env)


@pytest.fixture(scope="session")
def with_mock_aws(with_mock_env: None) -> Generator[None]:
    with mock_aws():
        yield
