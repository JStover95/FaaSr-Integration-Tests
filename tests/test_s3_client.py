from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from framework.s3_client import (
    FaaSrS3Client,
    S3ClientError,
    S3ClientInitializationError,
)
from tests.conftest import DATASTORE_BUCKET, datastore_config, workflow_data


class TestFaaSrS3ClientInit:
    """Tests for FaaSrS3Client initialization"""

    def test_init_with_endpoint(self):
        """Test initialization with endpoint URL"""
        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )
        assert client._bucket_name == DATASTORE_BUCKET
        assert client._client is not None
        assert client._timeout == 20
        assert client._queue.qsize() == 10

    def test_init_without_endpoint(self):
        """Test initialization without endpoint URL"""
        wf_data = {
            "DefaultDataStore": "S3",
            "DataStores": {
                "S3": {
                    "Bucket": DATASTORE_BUCKET,
                    "Region": "us-east-1",
                },
            },
        }
        client = FaaSrS3Client(
            workflow_data=wf_data,
            access_key="test_access_key",
            secret_key="test_secret_key",
        )
        assert client._bucket_name == DATASTORE_BUCKET
        assert client._client is not None

    def test_init_with_custom_default_datastore(self):
        """Test initialization with custom default datastore"""
        wf_data = {
            "DefaultDataStore": "CustomS3",
            "DataStores": {
                "CustomS3": datastore_config(),
            },
        }
        client = FaaSrS3Client(
            workflow_data=wf_data,
            access_key="test_access_key",
            secret_key="test_secret_key",
        )
        assert client._bucket_name == DATASTORE_BUCKET

    def test_init_with_missing_datastore_key(self):
        """Test initialization raises error when datastore key is missing"""
        wf_data = {
            "DefaultDataStore": "S3",
            "DataStores": {},
        }
        with pytest.raises(S3ClientInitializationError, match="Key error"):
            FaaSrS3Client(
                workflow_data=wf_data,
                access_key="test_access_key",
                secret_key="test_secret_key",
            )

    def test_init_with_missing_datastores_key(self):
        """Test initialization raises error when DataStores key is missing"""
        wf_data = {
            "DefaultDataStore": "S3",
        }
        with pytest.raises(S3ClientInitializationError, match="Key error"):
            FaaSrS3Client(
                workflow_data=wf_data,
                access_key="test_access_key",
                secret_key="test_secret_key",
            )


class TestFaaSrS3ClientObjectExists:
    """Tests for FaaSrS3Client.object_exists method"""

    def test_object_exists_true(self, s3_client: S3Client):
        """Test object_exists returns True when object exists"""
        # Create test data using mock S3 client
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET, Key="test_key", Body=b"test content"
        )

        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        assert client.object_exists("test_key") is True

    def test_object_exists_false(self, s3_client: S3Client):
        """Test object_exists returns False when object does not exist"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)

        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        assert client.object_exists("non_existent_key") is False

    def test_object_exists_with_client_error(self):
        """Test object_exists raises S3ClientError on non-404 ClientError"""
        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        # Mock _client to raise a non-404 ClientError
        mock_error = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject"
        )
        client._client = MagicMock()
        client._client.head_object.side_effect = mock_error

        with pytest.raises(S3ClientError, match="Error checking object existence"):
            client.object_exists("test_key")


class TestFaaSrS3ClientGetObject:
    """Tests for FaaSrS3Client.get_object method"""

    def test_get_object_success(self, s3_client: S3Client):
        """Test get_object returns content when object exists"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET, Key="test_key", Body=b"test content"
        )

        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        result = client.get_object("test_key")
        assert result == "test content"

    def test_get_object_with_custom_encoding(self, s3_client: S3Client):
        """Test get_object with custom encoding"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        # Use latin-1 encoding for test
        content = "test content with émojis".encode("latin-1")
        s3_client.put_object(Bucket=DATASTORE_BUCKET, Key="test_key", Body=content)

        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        result = client.get_object("test_key", encoding="latin-1")
        assert result == "test content with émojis"

    def test_get_object_not_found(self, s3_client: S3Client):
        """Test get_object raises S3ClientError when object does not exist"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)

        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        with pytest.raises(S3ClientError, match="Object does not exist"):
            client.get_object("non_existent_key")

    def test_get_object_with_client_error_404(self):
        """Test get_object raises S3ClientError on 404 ClientError"""
        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        # Mock _client to raise a 404 ClientError
        mock_error = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )
        client._client = MagicMock()
        client._client.get_object.side_effect = mock_error

        with pytest.raises(S3ClientError, match="Object does not exist"):
            client.get_object("test_key")

    def test_get_object_with_client_error_non_404(self):
        """Test get_object raises S3ClientError on non-404 ClientError"""
        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        # Mock _client to raise a non-404 ClientError
        mock_error = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
        )
        client._client = MagicMock()
        client._client.get_object.side_effect = mock_error

        with pytest.raises(S3ClientError, match="boto3 client error getting object"):
            client.get_object("test_key")

    def test_get_object_with_unhandled_exception(self):
        """Test get_object raises S3ClientError on unhandled exception"""
        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        # Mock _client to raise a generic exception
        client._client = MagicMock()
        client._client.get_object.side_effect = ValueError("Unexpected error")

        with pytest.raises(S3ClientError, match="Unhandled error getting object"):
            client.get_object("test_key")


class TestFaaSrS3ClientCall:
    """Tests for FaaSrS3Client._call method (queue management)"""

    def test_call_manages_queue_token(self, s3_client: S3Client):
        """Test _call properly manages queue tokens"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET, Key="test_key", Body=b"test content"
        )

        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        # Initial queue size should be 10
        assert client._queue.qsize() == 10

        # Call should work and return token to queue
        result = client.get_object("test_key")
        assert result == "test content"
        assert client._queue.qsize() == 10

    def test_call_handles_exception_and_returns_token(self):
        """Test _call returns token to queue even when exception occurs"""
        client = FaaSrS3Client(
            workflow_data=workflow_data(),
            access_key="test_access_key",
            secret_key="test_secret_key",
        )

        # Mock _client to raise an exception
        mock_error = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject"
        )
        client._client = MagicMock()
        client._client.get_object.side_effect = mock_error

        initial_queue_size = client._queue.qsize()

        # Call should raise exception but return token to queue
        with pytest.raises(S3ClientError, match="Not Found"):
            client.get_object("test_key")

        # Queue size should be restored
        assert client._queue.qsize() == initial_queue_size
