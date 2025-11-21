# Mocking Strategies

This document describes strategies for mocking external services and error states in tests.

## Using External AWS Service Mocking

Use an externally hosted mocked AWS service (moto) at `localhost:5000` to create test buckets and data. This provides a realistic AWS-like interface without actual AWS calls. The mock service is automatically reset after each test to ensure test isolation.

### External AWS Service Mocking - Pattern

```python
# conftest.py
DATASTORE_ENDPOINT = "http://localhost:5000"

@pytest.fixture()
def with_mock_aws(with_mock_env: None) -> Generator[None]:
    """Reset external mock AWS service after each test"""
    try:
        yield
    finally:
        requests.post(f"{DATASTORE_ENDPOINT}/moto-api/reset")

@pytest.fixture()
def s3_client(with_mock_aws: None) -> S3Client:
    """S3 client pointing to external mock service"""
    return boto3.client("s3", endpoint_url=DATASTORE_ENDPOINT)

# test_file.py
def test_object_exists_true(self, s3_client: S3Client):
    """Test object_exists returns True when object exists"""
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
```

### External AWS Service Mocking - Benefits

- **Realistic**: Uses actual boto3 client interface
- **Fast**: No network calls to real AWS, all handled by local mock service
- **Isolated**: Tests don't affect real AWS resources, and each test starts with a clean state
- **Comprehensive**: Supports most AWS S3 operations
- **Automatic Cleanup**: Resources are automatically reset after each test via the `with_mock_aws` fixture

### Example: Complete S3 Workflow

```python
def test_s3_workflow(s3_client: S3Client):
    """Test complete S3 workflow with external mock service"""
    # Create bucket
    s3_client.create_bucket(Bucket="test-bucket")
    
    # Upload object
    s3_client.put_object(
        Bucket="test-bucket",
        Key="path/to/object.txt",
        Body=b"content"
    )
    
    # List objects
    response = s3_client.list_objects_v2(Bucket="test-bucket")
    assert len(response["Contents"]) == 1
    
    # Get object
    response = s3_client.get_object(
        Bucket="test-bucket",
        Key="path/to/object.txt"
    )
    assert response["Body"].read() == b"content"
    
    # Delete object
    s3_client.delete_object(
        Bucket="test-bucket",
        Key="path/to/object.txt"
    )
```

## Mocking Error States Directly

Mock error states directly with `side_effect` rather than trying to configure complex error conditions through normal API calls.

### Mocking Error States Directly - Pattern

```python
def test_object_exists_with_client_error(self):
    """Test object_exists raises S3ClientError on non-404 ClientError"""
    client = FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )

    # @@ Mock error states directly with `side_effect`
    mock_error = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject"
    )
    client._client = MagicMock()
    client._client.head_object.side_effect = mock_error

    with pytest.raises(S3ClientError, match="Error checking object existence"):
        client.object_exists("test_key")
```

### Mocking Error States Directly - Benefits

- **Precision**: Test specific error conditions exactly
- **Control**: Can test error paths that are hard to trigger naturally
- **Speed**: No need to set up complex conditions
- **Coverage**: Test error handling code paths

### Example: Different Error Types

```python
def test_get_object_with_various_errors(self):
    """Test get_object handles different error types"""
    client = FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )

    # Test 404 error
    mock_404 = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
    )
    client._client = MagicMock()
    client._client.get_object.side_effect = mock_404
    
    with pytest.raises(S3ClientError, match="Object does not exist"):
        client.get_object("test_key")

    # Test 403 error
    mock_403 = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
    )
    client._client.get_object.side_effect = mock_403
    
    with pytest.raises(S3ClientError, match="boto3 client error"):
        client.get_object("test_key")

    # Test generic exception
    client._client.get_object.side_effect = ValueError("Unexpected error")
    
    with pytest.raises(S3ClientError, match="Unhandled error"):
        client.get_object("test_key")
```

### Example: Sequential Side Effects

```python
def test_retry_mechanism(self):
    """Test retry mechanism with side_effect"""
    client = FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )

    # First call fails, second succeeds
    mock_error = ClientError(
        {"Error": {"Code": "503", "Message": "Service Unavailable"}}, "GetObject"
    )
    client._client = MagicMock()
    client._client.get_object.side_effect = [
        mock_error,  # First call fails
        {"Body": BytesIO(b"success")}  # Second call succeeds
    ]

    result = client.get_object("test_key", retry=True)
    assert result == "success"
    assert client._client.get_object.call_count == 2
```

### Example: Conditional Side Effects

```python
def test_conditional_error(self):
    """Test error based on input"""
    client = FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )

    def conditional_error(key):
        if key.startswith("forbidden/"):
            raise ClientError(
                {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
            )
        return {"Body": BytesIO(b"content")}

    client._client = MagicMock()
    client._client.get_object.side_effect = conditional_error

    # Should succeed
    result = client.get_object("allowed/key")
    assert result == "content"

    # Should fail
    with pytest.raises(S3ClientError):
        client.get_object("forbidden/key")
```

### Anti-Pattern: Complex Setup for Errors

```python
# DON'T: Try to trigger errors through complex setup
def test_error_case(self, s3_client: S3Client):
    """Trying to trigger 403 error naturally"""
    # This is hard, unreliable, and slow
    # Might not even be possible to trigger 403 this way
    s3_client.create_bucket(Bucket="test-bucket")
    # ... complex setup that might not work ...
    # ... still might not get the error you want ...
```

### Correct Pattern: Direct Mocking

```python
# DO: Mock the error directly
def test_error_case(self):
    """Test error handling with direct mocking"""
    client = FaaSrS3Client(...)
    
    mock_error = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
    )
    client._client = MagicMock()
    client._client.get_object.side_effect = mock_error
    
    with pytest.raises(S3ClientError):
        client.get_object("test_key")
```

## Combining External Mocking and Direct Mocking

You can combine the external mock AWS service for normal operations and direct mocking for error cases.

### Pattern

```python
def test_normal_and_error_paths(self, s3_client: S3Client):
    """Test both normal and error paths"""
    # Use external mock service for normal operations
    s3_client.create_bucket(Bucket="test-bucket")
    s3_client.put_object(
        Bucket="test-bucket",
        Key="test_key",
        Body=b"content"
    )
    
    client = FaaSrS3Client(...)
    
    # Normal path works
    assert client.object_exists("test_key") is True
    assert client.get_object("test_key") == "content"
    
    # Use direct mocking for error paths
    mock_error = ClientError(
        {"Error": {"Code": "500", "Message": "Internal Error"}}, "GetObject"
    )
    client._client.get_object.side_effect = mock_error
    
    # Error path works
    with pytest.raises(S3ClientError):
        client.get_object("test_key")
```
