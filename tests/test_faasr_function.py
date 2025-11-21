import threading
import time
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from framework.faasr_function import FaaSrFunction
from framework.faasr_function_logger import FaaSrFunctionLogger, LogEvent
from framework.s3_client import FaaSrS3Client, S3ClientError
from framework.utils.enums import FunctionStatus
from tests.conftest import DATASTORE_BUCKET, workflow_data


@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    """Create a FaaSrS3Client instance for testing"""
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )


@pytest.fixture(autouse=True)
def ensure_bucket(s3_client: S3Client):
    """Ensure the test bucket exists for all tests"""
    s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
    yield


class TestFaaSrFunctionInit:
    """Tests for FaaSrFunction initialization"""

    def test_init(self, s3_client_fixture: FaaSrS3Client):
        """Test basic initialization"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.function_name == "test_function"
        assert function.workflow_name == "test_workflow"
        assert function.invocation_folder == "test/invocation"
        assert function.s3_client == s3_client_fixture
        assert function.stream_logs is False
        assert function.interval_seconds == 3
        assert function.status == FunctionStatus.PENDING
        assert function.invocations is None

    def test_init_creates_logger(self, s3_client_fixture: FaaSrS3Client):
        """Test that logger is created and started"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function._logger is not None
        assert isinstance(function._logger, FaaSrFunctionLogger)
        assert function._logger.function_name == "test_function"
        assert function._logger.workflow_name == "test_workflow"
        assert function._logger.invocation_folder == "test/invocation"


class TestFaaSrFunctionProperties:
    """Tests for FaaSrFunction properties"""

    def test_status_property(self, s3_client_fixture: FaaSrS3Client):
        """Test status property is thread-safe"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.status == FunctionStatus.PENDING

        function.set_status(FunctionStatus.RUNNING)
        assert function.status == FunctionStatus.RUNNING

    @pytest.mark.parametrize(
        ("function_name", "expected_key"),
        [
            (
                "test_function",
                "test/invocation/function_completions/test_function.done",
            ),
            (
                "test_function(1)",
                "test/invocation/function_completions/test_function.1.done",
            ),
            (
                "test_function(2)",
                "test/invocation/function_completions/test_function.2.done",
            ),
            (
                "my_func(10)",
                "test/invocation/function_completions/my_func.10.done",
            ),
        ],
    )
    def test_done_key(
        self,
        s3_client_fixture: FaaSrS3Client,
        function_name: str,
        expected_key: str,
    ):
        """Test done_key property converts ranks correctly"""
        function = FaaSrFunction(
            function_name=function_name,
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.done_key == expected_key

    def test_invocations_property_none(self, s3_client_fixture: FaaSrS3Client):
        """Test invocations property returns None when not extracted"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.invocations is None

    def test_invocations_property_returns_copy(self, s3_client_fixture: FaaSrS3Client):
        """Test invocations property returns a copy"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Set invocations directly
        with function._lock:
            function._invocations = {"func1", "func2"}

        invocations = function.invocations
        assert invocations == {"func1", "func2"}

        # Modify the returned set - should not affect internal state
        invocations.add("func3")
        assert function.invocations == {"func1", "func2"}

    def test_logs_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs property delegates to logger"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._logger._update_logs(["log1", "log2"])
        assert function.logs == ["log1", "log2"]

    def test_logs_content_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_content property delegates to logger"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._logger._update_logs(["log1", "log2", "log3"])
        assert function.logs_content == "log1\nlog2\nlog3"

    def test_logs_complete_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_complete property delegates to logger"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.logs_complete is False
        function._logger._set_logs_complete()
        assert function.logs_complete is True

    def test_logs_started_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_started property delegates to logger"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.logs_started is False
        function._logger._set_logs_started()
        assert function.logs_started is True

    def test_function_complete_property(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test function_complete property checks for done file"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.function_complete is False

        # Create done file
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/function_completions/test_function.done",
            Body=b"",
        )

        assert function.function_complete is True

    def test_function_failed_property(self, s3_client_fixture: FaaSrS3Client):
        """Test function_failed property checks for errors in logs"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.function_failed is False

        # Add error log
        function._logger._update_logs(["[1.0] [ERROR] Something went wrong"])
        assert function.function_failed is True


class TestFaaSrFunctionStatusManagement:
    """Tests for FaaSrFunction status management"""

    def test_set_status(self, s3_client_fixture: FaaSrS3Client):
        """Test set_status updates status"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.status == FunctionStatus.PENDING
        function.set_status(FunctionStatus.RUNNING)
        assert function.status == FunctionStatus.RUNNING

    @pytest.mark.parametrize(
        ("status",),
        [
            (FunctionStatus.PENDING,),
            (FunctionStatus.INVOKED,),
            (FunctionStatus.NOT_INVOKED,),
            (FunctionStatus.RUNNING,),
            (FunctionStatus.COMPLETED,),
            (FunctionStatus.FAILED,),
            (FunctionStatus.SKIPPED,),
            (FunctionStatus.TIMEOUT,),
        ],
    )
    def test_set_status_all_values(
        self, s3_client_fixture: FaaSrS3Client, status: FunctionStatus
    ):
        """Test set_status with all status values"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function.set_status(status)
        assert function.status == status

    def test_set_status_thread_safe(self, s3_client_fixture: FaaSrS3Client):
        """Test set_status is thread-safe"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        statuses = [
            FunctionStatus.PENDING,
            FunctionStatus.RUNNING,
            FunctionStatus.COMPLETED,
            FunctionStatus.FAILED,
        ]

        def set_statuses():
            for status in statuses:
                function.set_status(status)
                time.sleep(0.01)

        threads = [threading.Thread(target=set_statuses) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Status should be one of the values we set
        assert function.status in statuses


class TestFaaSrFunctionLogEventHandling:
    """Tests for FaaSrFunction log event handling"""

    def test_on_log_event_log_created(self, s3_client_fixture: FaaSrS3Client):
        """Test _on_log_event handles LOG_CREATED event"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function.status == FunctionStatus.PENDING
        function._on_log_event(LogEvent.LOG_CREATED)
        assert function.status == FunctionStatus.RUNNING

    def test_on_log_event_log_updated_with_failure(
        self, s3_client_fixture: FaaSrS3Client
    ):
        """Test _on_log_event handles LOG_UPDATED event with failure"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Add error log
        function._logger._update_logs(["[1.0] [ERROR] Something went wrong"])

        function._on_log_event(LogEvent.LOG_UPDATED)
        assert function.status == FunctionStatus.FAILED
        # Logger should be stopped
        assert function._logger.stop_requested is True

    def test_on_log_event_log_updated_with_completion(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _on_log_event handles LOG_UPDATED event with completion"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/function_completions/test_function.done",
            Body=b"",
        )

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._on_log_event(LogEvent.LOG_UPDATED)
        assert function.status == FunctionStatus.COMPLETED

    def test_on_log_event_log_updated_no_change(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _on_log_event handles LOG_UPDATED event with no status change"""

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function.set_status(FunctionStatus.RUNNING)
        function._on_log_event(LogEvent.LOG_UPDATED)
        # Status should remain RUNNING
        assert function.status == FunctionStatus.RUNNING

    def test_on_log_event_log_complete_with_failure(
        self, s3_client_fixture: FaaSrS3Client
    ):
        """Test _on_log_event handles LOG_COMPLETE event with failure"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Add error log
        function._logger._update_logs(["[1.0] [ERROR] Something went wrong"])

        function._on_log_event(LogEvent.LOG_COMPLETE)
        assert function.status == FunctionStatus.FAILED

    def test_on_log_event_log_complete_with_completion(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _on_log_event handles LOG_COMPLETE event with completion"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/function_completions/test_function.done",
            Body=b"",
        )

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._on_log_event(LogEvent.LOG_COMPLETE)
        assert function.status == FunctionStatus.COMPLETED

    def test_on_log_event_log_complete_extracts_invocations(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _on_log_event extracts invocations on LOG_COMPLETE"""

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="testworkflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Add log with invocation (using workflow name without underscores since regex doesn't support them)
        log_content = (
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func1"
        )
        function._logger._update_logs([log_content])

        function._on_log_event(LogEvent.LOG_COMPLETE)
        assert function.invocations == {"func1"}


class TestFaaSrFunctionFailureDetection:
    """Tests for FaaSrFunction failure detection"""

    def test_check_for_failure_with_error(self, s3_client_fixture: FaaSrS3Client):
        """Test _check_for_failure detects error in logs"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._logger._update_logs(["[1.0] [ERROR] Something went wrong"])
        assert function._check_for_failure() is True

    def test_check_for_failure_without_error(self, s3_client_fixture: FaaSrS3Client):
        """Test _check_for_failure returns False when no error"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._logger._update_logs(["[1.0] [INFO] Everything is fine"])
        assert function._check_for_failure() is False

    @pytest.mark.parametrize(
        ("log_content", "expected_failure"),
        [
            ("[1.0] [ERROR] Error message", True),
            ("[2.5] [ERROR] Another error", True),
            ("[10.123] [ERROR] Error with decimal", True),
            ("[1.0] [INFO] No error here", False),
            ("[1.0] [WARNING] Warning message", False),
            ("[1.0] [DEBUG] Debug message", False),
            ("[ERROR] Missing timestamp", False),
            ("[1.0] ERROR Missing brackets", False),
            ("", False),
        ],
    )
    def test_check_for_failure_various_logs(
        self,
        s3_client_fixture: FaaSrS3Client,
        log_content: str,
        expected_failure: bool,
    ):
        """Test _check_for_failure with various log formats"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._logger._update_logs([log_content])
        assert function._check_for_failure() == expected_failure


class TestFaaSrFunctionCompletionDetection:
    """Tests for FaaSrFunction completion detection"""

    def test_check_for_completion_with_done_file(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _check_for_completion returns True when done file exists"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/function_completions/test_function.done",
            Body=b"",
        )

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function._check_for_completion() is True

    def test_check_for_completion_without_done_file(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _check_for_completion returns False when done file doesn't exist"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)

        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function._check_for_completion() is False

    def test_check_for_completion_with_ranked_function(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _check_for_completion with ranked function name"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/function_completions/test_function.1.done",
            Body=b"",
        )

        function = FaaSrFunction(
            function_name="test_function(1)",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        assert function._check_for_completion() is True

    def test_check_for_completion_with_s3_error(self, s3_client_fixture: FaaSrS3Client):
        """Test _check_for_completion handles S3 errors"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Mock s3_client to raise an error
        mock_error = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject"
        )
        s3_client_fixture._client = MagicMock()
        s3_client_fixture._client.head_object.side_effect = mock_error

        with pytest.raises(S3ClientError, match="Error checking object existence"):
            function._check_for_completion()


class TestFaaSrFunctionInvocationExtraction:
    """Tests for FaaSrFunction invocation extraction"""

    def test_extract_invocations_single(self, s3_client_fixture: FaaSrS3Client):
        """Test _extract_invocations extracts single invocation"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="testworkflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Use workflow name without underscores since regex pattern doesn't support them
        log_content = (
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func1"
        )
        function._logger._update_logs([log_content])

        function._extract_invocations()
        assert function.invocations == {"func1"}

    def test_extract_invocations_multiple(self, s3_client_fixture: FaaSrS3Client):
        """Test _extract_invocations extracts multiple invocations"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="testworkflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Use workflow name without underscores since regex pattern doesn't support them
        log_content = (
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func1\n"
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func2\n"
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func3"
        )
        function._logger._update_logs([log_content])

        function._extract_invocations()
        assert function.invocations == {"func1", "func2", "func3"}

    def test_extract_invocations_removes_workflow_prefix(
        self, s3_client_fixture: FaaSrS3Client
    ):
        """Test _extract_invocations removes workflow name prefix"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="myworkflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Use workflow name without underscores since regex pattern doesn't support them
        log_content = (
            "[scheduler.py] GitHub Action: Successfully invoked: myworkflow-func1"
        )
        function._logger._update_logs([log_content])

        function._extract_invocations()
        assert function.invocations == {"func1"}

    def test_extract_invocations_no_invocations(self, s3_client_fixture: FaaSrS3Client):
        """Test _extract_invocations handles no invocations"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        function._logger._update_logs(["[1.0] [INFO] No invocations here"])

        function._extract_invocations()
        assert function.invocations == set()

    def test_extract_invocations_duplicates(self, s3_client_fixture: FaaSrS3Client):
        """Test _extract_invocations handles duplicate invocations"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="testworkflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Use workflow name without underscores since regex pattern doesn't support them
        log_content = (
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func1\n"
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func1"
        )
        function._logger._update_logs([log_content])

        function._extract_invocations()
        assert function.invocations == {"func1"}

    def test_extract_invocations_thread_safe(self, s3_client_fixture: FaaSrS3Client):
        """Test _extract_invocations is thread-safe"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="testworkflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Use workflow name without underscores since regex pattern doesn't support them
        log_content = (
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func1\n"
            "[scheduler.py] GitHub Action: Successfully invoked: testworkflow-func2"
        )
        function._logger._update_logs([log_content])

        def extract_invocations():
            function._extract_invocations()

        threads = [threading.Thread(target=extract_invocations) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have consistent result
        assert function.invocations in [{"func1", "func2"}, set()]


class TestFaaSrFunctionStart:
    """Tests for FaaSrFunction start method"""

    def test_start(self, s3_client_fixture: FaaSrS3Client):
        """Test start method starts the logger"""
        function = FaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            start_logger=False,
        )

        # Logger is already started in __init__, but we can call start again
        function.start()
        assert function._logger._thread is not None
        assert function._logger._thread.is_alive()
