# Test Parameterization

This document describes how to use `pytest.mark.parametrize` to test multiple cases efficiently, reducing code duplication and improving test coverage.

## Using pytest.mark.parametrize

Use `pytest.mark.parametrize` to test multiple cases at once, reducing code duplication and ensuring comprehensive coverage.

### Pattern

```python
@pytest.mark.parametrize(
    ("function_name", "expected_name"),
    [
        ("my_function()", "my_function"),
        ("test_func(arg1, arg2)", "test_func"),
        ("foo(bar)", "foo"),
    ],
)
def test_extract_function_name_with_parentheses(
    self,
    function_name: str,
    expected_name: str,
):
    """Test extracting function name from string with parentheses"""
    assert extract_function_name(function_name) == expected_name
```

### Benefits

- **Comprehensive Coverage**: Test many cases with minimal code
- **Maintainability**: Add new test cases by adding tuples to the list
- **Clarity**: All test cases are visible in one place
- **Efficiency**: pytest runs each case as a separate test
- **Reporting**: Each case appears as a separate test in reports

### Example: Multiple Input/Output Pairs

```python
@pytest.mark.parametrize(
    ("input_value", "expected_output"),
    [
        ("simple", "simple"),
        ("with_parens()", "with_parens"),
        ("complex(arg1, arg2)", "complex"),
        ("nested(inner())", "nested"),
    ],
)
def test_function_name_extraction(input_value: str, expected_output: str):
    """Test function name extraction with various inputs"""
    result = extract_function_name(input_value)
    assert result == expected_output
```

### Example: Testing Different Status Values

```python
@pytest.mark.parametrize(
    ("status", "expected_result"),
    [
        (FunctionStatus.PENDING, True),
        (FunctionStatus.INVOKED, False),
        (FunctionStatus.NOT_INVOKED, False),
        (FunctionStatus.RUNNING, False),
        (FunctionStatus.COMPLETED, False),
        (FunctionStatus.FAILED, False),
        (FunctionStatus.SKIPPED, False),
        (FunctionStatus.TIMEOUT, False),
    ],
)
def test_pending_with_pending_status(
    self, status: FunctionStatus, expected_result: bool
):
    """Test pending() function with all status values"""
    assert pending(status) == expected_result
```

### Example: Path Conversion Tests

```python
@pytest.mark.parametrize(
    ("path", "expected_path"),
    [
        ("path\\to\\file", "path/to/file"),
        ("bucket\\folder\\object", "bucket/folder/object"),
        ("path/to/file", "path/to/file"),
        ("bucket/folder/object", "bucket/folder/object"),
        ("path\\to/file", "path/to/file"),
        ("bucket/folder\\object", "bucket/folder/object"),
        ("path", "path"),
    ],
)
def test_get_s3_path(path: str, expected_path: str):
    """Test converting paths to S3 format"""
    assert get_s3_path(path) == expected_path
```

### Example: Multiple Parameters

```python
@pytest.mark.parametrize(
    ("bucket", "key", "expected_exists"),
    [
        ("test-bucket", "existing-key", True),
        ("test-bucket", "non-existent-key", False),
        ("other-bucket", "key", False),
    ],
)
def test_object_exists(s3_client: S3Client, bucket: str, key: str, expected_exists: bool):
    """Test object_exists with different buckets and keys"""
    s3_client.create_bucket(Bucket=bucket)
    if expected_exists:
        s3_client.put_object(Bucket=bucket, Key=key, Body=b"content")
    
    client = FaaSrS3Client(...)
    assert client.object_exists(key) == expected_exists
```

### Example: Combining with Fixtures

```python
@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    return FaaSrS3Client(...)

@pytest.mark.parametrize(
    ("function_name", "workflow_name", "invocation_folder"),
    [
        ("func1", "workflow1", "invocation/1"),
        ("func2", "workflow2", "invocation/2"),
        ("func3", "workflow3", "invocation/3"),
    ],
)
def test_logger_initialization(
    s3_client_fixture: FaaSrS3Client,
    function_name: str,
    workflow_name: str,
    invocation_folder: str,
):
    """Test logger initialization with different parameters"""
    logger = FaaSrFunctionLogger(
        function_name=function_name,
        workflow_name=workflow_name,
        invocation_folder=invocation_folder,
        s3_client=s3_client_fixture,
    )
    
    assert logger.function_name == function_name
    assert logger.workflow_name == workflow_name
    assert logger.invocation_folder == invocation_folder
```

### Example: Testing Edge Cases

```python
@pytest.mark.parametrize(
    ("input_value", "expected_output"),
    [
        ("", ""),  # Empty string
        ("()", ""),  # Only parentheses
        ("a", "a"),  # Single character
        ("a()", "a"),  # Single character with parentheses
        ("very_long_function_name()", "very_long_function_name"),
        ("func(with, many, params)", "func"),
    ],
)
def test_edge_cases(input_value: str, expected_output: str):
    """Test edge cases and boundary conditions"""
    result = extract_function_name(input_value)
    assert result == expected_output
```

### Example: Testing Error Conditions

```python
@pytest.mark.parametrize(
    ("error_code", "error_message", "expected_match"),
    [
        ("404", "Not Found", "Object does not exist"),
        ("403", "Forbidden", "boto3 client error"),
        ("500", "Internal Error", "boto3 client error"),
    ],
)
def test_error_handling(error_code: str, error_message: str, expected_match: str):
    """Test error handling for different error codes"""
    client = FaaSrS3Client(...)
    
    mock_error = ClientError(
        {"Error": {"Code": error_code, "Message": error_message}}, "GetObject"
    )
    client._client = MagicMock()
    client._client.get_object.side_effect = mock_error
    
    with pytest.raises(S3ClientError, match=expected_match):
        client.get_object("test_key")
```

### Anti-Pattern: Repeated Test Methods

```python
# DON'T: Write separate test methods for each case
def test_extract_function_name_simple(self):
    assert extract_function_name("my_function()") == "my_function"

def test_extract_function_name_with_args(self):
    assert extract_function_name("test_func(arg1, arg2)") == "test_func"

def test_extract_function_name_nested(self):
    assert extract_function_name("foo(bar)") == "foo"
```

**Problems:**

- Code duplication
- Hard to add new cases
- Inconsistent test structure
- More maintenance overhead

### Correct Pattern: Parametrized Tests

```python
# DO: Use parametrize for multiple cases
@pytest.mark.parametrize(
    ("function_name", "expected_name"),
    [
        ("my_function()", "my_function"),
        ("test_func(arg1, arg2)", "test_func"),
        ("foo(bar)", "foo"),
    ],
)
def test_extract_function_name(function_name: str, expected_name: str):
    assert extract_function_name(function_name) == expected_name
```

**Benefits:**

- Single test method
- Easy to add cases
- Consistent structure
- Better test reports

### Example: Parametrized Class Methods

```python
class TestStatusFunctions:
    """Tests for status functions"""

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.PENDING, True),
            (FunctionStatus.INVOKED, False),
            # ... more cases
        ],
    )
    def test_pending(self, status: FunctionStatus, expected_result: bool):
        assert pending(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.RUNNING, True),
            (FunctionStatus.PENDING, False),
            # ... more cases
        ],
    )
    def test_running(self, status: FunctionStatus, expected_result: bool):
        assert running(status) == expected_result
```

### Example: Nested Parametrization

```python
@pytest.mark.parametrize("region", ["us-east-1", "us-west-2"])
@pytest.mark.parametrize("bucket", ["bucket1", "bucket2"])
def test_multi_region_bucket(region: str, bucket: str):
    """Test runs for each combination of region and bucket"""
    # This creates 4 test cases:
    # - us-east-1, bucket1
    # - us-east-1, bucket2
    # - us-west-2, bucket1
    # - us-west-2, bucket2
    client = create_client(region=region, bucket=bucket)
    assert client.region == region
    assert client.bucket == bucket
```

### Example: Conditional Parametrization

```python
import pytest

# Only run certain tests if condition is met
@pytest.mark.parametrize(
    ("input_value", "expected_output"),
    [
        ("normal_case", "normal_output"),
        pytest.param(
            "special_case",
            "special_output",
            marks=pytest.mark.skipif(
                not os.getenv("ENABLE_SPECIAL_TESTS"),
                reason="Requires ENABLE_SPECIAL_TESTS env var"
            ),
        ),
    ],
)
def test_with_conditional(input_value: str, expected_output: str):
    """Test with conditional parametrization"""
    result = process(input_value)
    assert result == expected_output
```
