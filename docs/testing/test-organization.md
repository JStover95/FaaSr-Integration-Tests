# Test Organization Patterns

This document describes patterns for organizing test code, including shared test infrastructure, constants, and helper functions.

## Shared Constants in conftest.py

Define shared constants for testing in `conftest.py` to ensure consistency across all test files.

### Shared Constants in conftest.py - Pattern

```python
# conftest.py
DATASTORE_ENDPOINT = "https://s3.us-east-1.amazonaws.com"
DATASTORE_BUCKET = "testing"
DATASTORE_REGION = "us-east-1"
```

### Shared Constants in conftest.py - Benefits

- **Consistency**: All tests use the same test values
- **Maintainability**: Update values in one place
- **Clarity**: Test constants are clearly separated from test logic

### Example Usage

```python
def test_s3_operation(s3_client):
    s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
    s3_client.put_object(
        Bucket=DATASTORE_BUCKET,
        Key="test_key",
        Body=b"test content"
    )
```

## Shared Mutable Data Types

Define functions that return shared mutable datatypes for testing in `conftest.py`. This prevents test isolation issues when tests modify shared data structures.

### Shared Mutable Data Types - Pattern

```python
# conftest.py
# @@ Define functions shared mutable datatypes for testing in conftest.py
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
```

### Why Functions Instead of Direct Dictionaries?

When tests modify dictionaries or other mutable types, they can affect other tests if the same object is shared. By using functions that return new instances, each test gets its own copy.

### Anti-Pattern

```python
# DON'T: Shared mutable object
WORKFLOW_DATA = {
    "DefaultDataStore": "S3",
    "DataStores": {"S3": {...}}
}

def test_one():
    WORKFLOW_DATA["DefaultDataStore"] = "Custom"  # Affects other tests!

def test_two():
    # May see modified value from test_one
    assert WORKFLOW_DATA["DefaultDataStore"] == "S3"  # Fails!
```

### Correct Pattern

```python
# DO: Function returning new instance
def workflow_data() -> dict[str, Any]:
    return {
        "DefaultDataStore": "S3",
        "DataStores": {"S3": {...}}
    }

def test_one():
    wf_data = workflow_data()
    wf_data["DefaultDataStore"] = "Custom"  # Only affects this test

def test_two():
    wf_data = workflow_data()
    assert wf_data["DefaultDataStore"] == "S3"  # Passes!
```

## Grouping Related Tests

Group related tests with a class to improve organization and readability.

### Grouping Related Tests - Pattern

```python
# @@ Group related tests with a class
class TestExtractFunctionName:
    """Tests for extract_function_name function"""

    def test_extract_function_name_with_parentheses(self):
        """Test extracting function name from string with parentheses"""
        assert extract_function_name("my_function()") == "my_function"

    def test_extract_function_name_without_parentheses(self):
        """Test extracting function name from string without parentheses"""
        assert extract_function_name("my_function") == "my_function"
```

### Grouping Related Tests - Benefits

- **Organization**: Related tests are grouped together
- **Readability**: Clear structure shows what functionality is being tested
- **IDE Support**: Easier navigation and test discovery
- **Documentation**: Class docstring describes the test suite

### Example Structure

```python
class TestFaaSrFunctionLoggerInit:
    """Tests for FaaSrFunctionLogger initialization"""

    def test_init(self, s3_client_fixture):
        """Test basic initialization"""
        # Test implementation

    def test_init_with_custom_params(self, s3_client_fixture):
        """Test initialization with custom parameters"""
        # Test implementation

class TestFaaSrFunctionLoggerProperties:
    """Tests for FaaSrFunctionLogger properties"""

    def test_logs_key(self, s3_client_fixture):
        """Test logs_key property"""
        # Test implementation
```

## Environment Variable Mocking

When working with mocked AWS services, mock environment variables with testing credentials to ensure consistent behavior.

### Environment Variable Mocking - Pattern

```python
# conftest.py
@pytest.fixture()
def with_mock_env() -> Generator[None]:
    env = os.environ.copy()

    try:
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["GH_PAT"] = "testing"
        # ... other environment variables

        with suppress(KeyError):
            del os.environ["AWS_PROFILE"]

    finally:
        os.environ.clear()
        os.environ.update(env)
```

### Environment Variable Mocking - Benefits

- **Isolation**: Tests don't depend on actual credentials
- **Reproducibility**: Tests behave consistently across environments
- **Safety**: Prevents accidental use of real credentials
- **Cleanup**: Environment is restored after tests

### Environment Variable Mocking - Usage

```python
def test_with_mocked_aws(with_mock_env):
    # Environment variables are set to test values
    client = create_client()  # Uses mocked credentials
    # Test implementation
```

## Wrapping Context Managers as Fixtures

Wrap context managers (like `moto.mock_aws()`) with pytest fixtures for cleaner test code.

### Wrapping Context Managers as Fixtures - Pattern

```python
# conftest.py
@pytest.fixture()
def with_mock_aws(with_mock_env: None) -> Generator[None]:
    with mock_aws():
        yield
```

### Wrapping Context Managers as Fixtures - Benefits

- **Cleaner Tests**: No need to use context managers in every test
- **Automatic Cleanup**: Fixture handles cleanup automatically
- **Composability**: Can combine with other fixtures
- **Consistency**: All tests use the same mocking setup

### Wrapping Context Managers as Fixtures - Usage

```python
def test_s3_operation(with_mock_aws, s3_client):
    # AWS is mocked automatically
    s3_client.create_bucket(Bucket="test-bucket")
    # Test implementation
```

## Separate Fixtures for Clients

Define a separate fixture for clients (like S3 client) to make them easily available to tests.

### Separate Fixtures for Clients - Pattern

```python
# conftest.py
@pytest.fixture()
def s3_client(with_mock_aws: None) -> S3Client:
    return boto3.client("s3", endpoint_url=DATASTORE_ENDPOINT)
```

### Separate Fixtures for Clients - Benefits

- **Reusability**: Same client fixture used across multiple tests
- **Consistency**: All tests use the same client configuration
- **Dependency Management**: Fixture dependencies are clear
- **Type Hints**: IDE can provide better autocomplete

### Separate Fixtures for Clients - Usage

```python
def test_object_exists(s3_client: S3Client):
    s3_client.create_bucket(Bucket="test-bucket")
    s3_client.put_object(
        Bucket="test-bucket",
        Key="test_key",
        Body=b"content"
    )
    # Test implementation
```
