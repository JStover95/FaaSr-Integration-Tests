# Dependency Injection in Tests

This document describes how to use pytest fixtures for dependency injection in tests, making tests more maintainable and easier to modify.

## Using Pytest Fixtures for Dependency Injection

Use pytest fixtures for dependency injection in tests rather than creating dependencies directly in test methods.

### Pattern

```python
# conftest.py
@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    """Create a FaaSrS3Client instance for testing"""
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )

# test_file.py
def test_init(self, s3_client_fixture: FaaSrS3Client):
    """Test basic initialization"""
    logger = FaaSrFunctionLogger(
        function_name="test_function",
        workflow_name="test_workflow",
        invocation_folder="test/invocation",
        s3_client=s3_client_fixture,
    )
    
    assert logger.s3_client == s3_client_fixture
```

### Benefits

- **Testability**: Easy to swap implementations for testing
- **Isolation**: Each test gets its own instance (if fixture scope is appropriate)
- **Maintainability**: Change dependency creation in one place
- **Readability**: Test code focuses on behavior, not setup
- **Reusability**: Same fixture can be used across multiple tests

### Example: Multiple Dependencies

```python
# conftest.py
@pytest.fixture
def database_client():
    """Create a database client for testing"""
    return DatabaseClient(connection_string="test://localhost")

@pytest.fixture
def cache_client():
    """Create a cache client for testing"""
    return CacheClient(host="localhost", port=6379)

@pytest.fixture
def service(database_client, cache_client):
    """Create a service with injected dependencies"""
    return MyService(
        database=database_client,
        cache=cache_client
    )

# test_file.py
def test_service_operation(service):
    """Test service with injected dependencies"""
    result = service.perform_operation()
    assert result is not None
```

### Example: Conditional Dependencies

```python
# conftest.py
@pytest.fixture
def s3_client_fixture(with_mock_aws: None, request):
    """Create a FaaSrS3Client instance for testing"""
    # Can access pytest markers or other fixtures
    use_custom_endpoint = request.config.getoption("--custom-endpoint", default=False)
    
    endpoint = "custom://endpoint" if use_custom_endpoint else DATASTORE_ENDPOINT
    
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
        endpoint=endpoint,
    )
```

### Example: Fixture Scopes

```python
# Session scope: Created once per test session
@pytest.fixture(scope="session")
def expensive_setup():
    """Expensive setup that runs once"""
    return ExpensiveResource()

# Module scope: Created once per test module
@pytest.fixture(scope="module")
def shared_state():
    """Shared state for all tests in module"""
    return SharedState()

# Function scope (default): Created for each test
@pytest.fixture
def fresh_instance():
    """New instance for each test"""
    return MyClass()
```

### Anti-Pattern: Direct Instantiation

```python
# DON'T: Create dependencies directly in tests
def test_init(self):
    s3_client = FaaSrS3Client(
        workflow_data={...},
        access_key="test_access_key",
        secret_key="test_secret_key",
    )
    logger = FaaSrFunctionLogger(
        function_name="test_function",
        s3_client=s3_client,
    )
    # Test implementation
```

**Problems:**

- Duplication: Same setup code in every test
- Hard to modify: Must change every test if constructor changes
- No isolation: Can't easily swap implementations
- Hard to mock: Difficult to inject mocks

### Correct Pattern: Fixture Injection

```python
# DO: Use fixtures for dependency injection
@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )

def test_init(self, s3_client_fixture: FaaSrS3Client):
    logger = FaaSrFunctionLogger(
        function_name="test_function",
        s3_client=s3_client_fixture,
    )
    # Test implementation
```

**Benefits:**

- Single source of truth for dependency creation
- Easy to modify: Change fixture, all tests update
- Easy to mock: Replace fixture with mock
- Clear dependencies: Test signature shows what's needed

### Example: Mocking Dependencies

```python
# conftest.py
@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing"""
    return MagicMock(spec=FaaSrS3Client)

# test_file.py
def test_with_mock(self, mock_s3_client):
    """Test with mocked dependency"""
    mock_s3_client.get_object.return_value = "mocked content"
    
    logger = FaaSrFunctionLogger(
        function_name="test_function",
        s3_client=mock_s3_client,
    )
    
    # Test implementation using mock
```

### Example: Parameterized Fixtures

```python
# conftest.py
@pytest.fixture(params=["us-east-1", "us-west-2", "eu-west-1"])
def s3_client_fixture(request, with_mock_aws: None):
    """Create S3 client for different regions"""
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
        region=request.param,
    )

# test_file.py
def test_region_specific_operation(s3_client_fixture):
    """Test runs for each region"""
    # Test implementation
    assert s3_client_fixture.region in ["us-east-1", "us-west-2", "eu-west-1"]
```
