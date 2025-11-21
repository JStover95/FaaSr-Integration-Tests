# Error Assertion Patterns

This document describes best practices for asserting error conditions in tests, ensuring error messages are properly validated.

## Always Use `match` to Assert Error Messages

Always use `match` to assert the error message when testing exception handling. This ensures the correct error is raised and provides better test documentation.

### Pattern

```python
with pytest.raises(S3ClientError, match="Error checking object existence"):
    client.object_exists("test_key")
```

### Benefits

- **Precision**: Ensures the correct error is raised, not just any error
- **Documentation**: Test clearly shows what error message is expected
- **Maintainability**: Tests fail if error messages change (which may indicate breaking changes)
- **Debugging**: Easier to identify which error path was taken

### Example: Basic Error Assertion

```python
def test_object_not_found(s3_client: S3Client):
    """Test that appropriate error is raised when object doesn't exist"""
    client = FaaSrS3Client(...)
    
    with pytest.raises(S3ClientError, match="Object does not exist"):
        client.get_object("non_existent_key")
```

### Example: Multiple Error Types

```python
def test_error_handling(client):
    """Test different error conditions"""
    # Test 404 error
    mock_404 = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
    )
    client._client.get_object.side_effect = mock_404
    
    with pytest.raises(S3ClientError, match="Object does not exist"):
        client.get_object("test_key")

    # Test 403 error
    mock_403 = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
    )
    client._client.get_object.side_effect = mock_403
    
    with pytest.raises(S3ClientError, match="boto3 client error getting object"):
        client.get_object("test_key")

    # Test generic error
    client._client.get_object.side_effect = ValueError("Unexpected error")
    
    with pytest.raises(S3ClientError, match="Unhandled error getting object"):
        client.get_object("test_key")
```

### Example: Partial Message Matching

The `match` parameter uses regex, so you can match partial messages:

```python
# Match exact message
with pytest.raises(S3ClientError, match="Object does not exist"):
    client.get_object("key")

# Match partial message (useful for dynamic content)
with pytest.raises(S3ClientError, match="Error checking object"):
    client.object_exists("key")

# Match with regex patterns
with pytest.raises(S3ClientError, match=r"Error \d+ occurred"):
    client.operation()
```

### Example: Asserting Error Attributes

You can also assert on error attributes in addition to the message:

```python
def test_error_with_attributes(client):
    """Test error with specific attributes"""
    with pytest.raises(S3ClientError) as exc_info:
        client.get_object("test_key")
    
    error = exc_info.value
    assert error.status_code == 404
    assert "Object does not exist" in str(error)
    assert error.operation == "GetObject"
```

### Example: Testing Error Context

```python
def test_error_includes_context(client):
    """Test that error includes relevant context"""
    with pytest.raises(S3ClientError) as exc_info:
        client.get_object("test_key", bucket="test-bucket")
    
    error = exc_info.value
    assert "test_key" in str(error)  # Key should be in error message
    assert "test-bucket" in str(error)  # Bucket should be in error message
    assert match="Object does not exist"  # Main error message
```

### Anti-Pattern: Not Asserting Error Message

```python
# DON'T: Just check that an error is raised
def test_error_case(client):
    with pytest.raises(S3ClientError):  # No match parameter!
        client.get_object("test_key")
```

**Problems:**

- Doesn't verify the correct error was raised
- Test might pass even if wrong error is raised
- Less informative when test fails
- Doesn't document expected error message

### Correct Pattern: Assert Error Message

```python
# DO: Always use match to assert error message
def test_error_case(client):
    with pytest.raises(S3ClientError, match="Object does not exist"):
        client.get_object("test_key")
```

**Benefits:**

- Verifies correct error is raised
- Documents expected error message
- More informative test failures
- Better test documentation

### Example: Testing Exception Chains

```python
def test_exception_chain(client):
    """Test that exceptions are properly wrapped"""
    original_error = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
    )
    client._client.get_object.side_effect = original_error
    
    with pytest.raises(S3ClientError, match="boto3 client error") as exc_info:
        client.get_object("test_key")
    
    # Verify the original error is preserved
    assert exc_info.value.__cause__ == original_error
```

### Example: Testing Multiple Error Scenarios

```python
@pytest.mark.parametrize(
    ("error_code", "error_message", "expected_match"),
    [
        ("404", "Not Found", "Object does not exist"),
        ("403", "Forbidden", "boto3 client error"),
        ("500", "Internal Error", "boto3 client error"),
        ("503", "Service Unavailable", "boto3 client error"),
    ],
)
def test_various_errors(client, error_code: str, error_message: str, expected_match: str):
    """Test various error conditions with proper message assertion"""
    mock_error = ClientError(
        {"Error": {"Code": error_code, "Message": error_message}}, "GetObject"
    )
    client._client.get_object.side_effect = mock_error
    
    with pytest.raises(S3ClientError, match=expected_match):
        client.get_object("test_key")
```

### Example: Testing Error Recovery

```python
def test_error_recovery(client):
    """Test that errors are properly handled and don't crash"""
    # First call fails
    mock_error = ClientError(
        {"Error": {"Code": "503", "Message": "Service Unavailable"}}, "GetObject"
    )
    client._client.get_object.side_effect = [mock_error, {"Body": BytesIO(b"success")}]
    
    # Should handle error gracefully
    with pytest.raises(S3ClientError, match="boto3 client error"):
        client.get_object("test_key", retry=False)
    
    # With retry, should eventually succeed
    result = client.get_object("test_key", retry=True)
    assert result == "success"
```

### Example: Testing Custom Exception Types

```python
def test_custom_exception(client):
    """Test custom exception types with message assertion"""
    # Test initialization error
    with pytest.raises(S3ClientInitializationError, match="Key error"):
        FaaSrS3Client(
            workflow_data={},  # Missing required keys
            access_key="test",
            secret_key="test",
        )
    
    # Test client error
    with pytest.raises(S3ClientError, match="Error checking object existence"):
        client.object_exists("test_key")
```

### Best Practices Summary

1. **Always use `match`**: Never use `pytest.raises()` without `match` parameter
2. **Be specific**: Match the most specific part of the error message
3. **Use regex wisely**: Use regex patterns for dynamic content, but keep them simple
4. **Test error attributes**: When relevant, also assert on error object attributes
5. **Document expectations**: The `match` parameter serves as documentation
6. **Test error context**: Ensure error messages include relevant context (keys, buckets, etc.)
