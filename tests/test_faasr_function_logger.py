import threading
import time
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from framework.faasr_function_logger import FaaSrFunctionLogger, LogEvent
from framework.s3_client import FaaSrS3Client, S3ClientError
from tests.conftest import DATASTORE_BUCKET, workflow_data


@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    """Create a FaaSrS3Client instance for testing"""
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )


class TestFaaSrFunctionLoggerInit:
    """Tests for FaaSrFunctionLogger initialization"""

    def test_init(self, s3_client_fixture: FaaSrS3Client):
        """Test basic initialization"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.function_name == "test_function"
        assert logger.workflow_name == "test_workflow"
        assert logger.invocation_folder == "test/invocation"
        assert logger.s3_client == s3_client_fixture
        assert logger.stream_logs is False
        assert logger.interval_seconds == 3
        assert logger.logs == []
        assert logger.logs_started is False
        assert logger.logs_complete is False
        assert logger.stop_requested is False
        assert logger._thread is None

    def test_init_with_custom_params(self, s3_client_fixture: FaaSrS3Client):
        """Test initialization with custom parameters"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            stream_logs=True,
            interval_seconds=5,
        )

        assert logger.stream_logs is True
        assert logger.interval_seconds == 5

    def test_logger_setup(self, s3_client_fixture: FaaSrS3Client):
        """Test that logger is properly set up"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.logger is not None
        assert logger.logger.name == "test_function"
        assert logger.logger.level == 20  # logging.INFO


class TestFaaSrFunctionLoggerProperties:
    """Tests for FaaSrFunctionLogger properties"""

    def test_logs_key(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_key property"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.logs_key == "test/invocation/test_function.txt"

    def test_logs_key_with_backslashes(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_key property converts backslashes"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test\\invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.logs_key == "test/invocation/test_function.txt"

    def test_logs_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs property returns copy"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        logger._update_logs(["log1", "log2"])
        logs = logger.logs
        assert logs == ["log1", "log2"]

        # Modify the returned list - should not affect internal state
        logs.append("log3")
        assert logger.logs == ["log1", "log2"]

    def test_logs_content_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_content property"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        logger._update_logs(["log1", "log2", "log3"])
        assert logger.logs_content == "log1\nlog2\nlog3"

    def test_logs_content_empty(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_content property with empty logs"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.logs_content == ""

    def test_logs_started_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_started property"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.logs_started is False
        logger._set_logs_started()
        assert logger.logs_started is True

    def test_logs_complete_property(self, s3_client_fixture: FaaSrS3Client):
        """Test logs_complete property"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.logs_complete is False
        logger._set_logs_complete()
        assert logger.logs_complete is True

    def test_stop_requested_property(self, s3_client_fixture: FaaSrS3Client):
        """Test stop_requested property"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.stop_requested is False
        logger.stop()
        assert logger.stop_requested is True


class TestFaaSrFunctionLoggerCallbacks:
    """Tests for FaaSrFunctionLogger callback functionality"""

    def test_register_callback(self, s3_client_fixture: FaaSrS3Client):
        """Test callback registration"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        callback_called = []

        def callback(event: LogEvent) -> None:
            callback_called.append(event)

        logger.register_callback(callback)
        logger._call_callbacks(LogEvent.LOG_CREATED)

        assert len(callback_called) == 1
        assert callback_called[0] == LogEvent.LOG_CREATED

    def test_register_multiple_callbacks(self, s3_client_fixture: FaaSrS3Client):
        """Test multiple callback registration"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        callback1_called = []
        callback2_called = []

        def callback1(event: LogEvent) -> None:
            callback1_called.append(event)

        def callback2(event: LogEvent) -> None:
            callback2_called.append(event)

        logger.register_callback(callback1)
        logger.register_callback(callback2)
        logger._call_callbacks(LogEvent.LOG_UPDATED)

        assert len(callback1_called) == 1
        assert callback1_called[0] == LogEvent.LOG_UPDATED
        assert len(callback2_called) == 1
        assert callback2_called[0] == LogEvent.LOG_UPDATED

    def test_callback_exception_handling(self, s3_client_fixture: FaaSrS3Client):
        """Test that callback exceptions are handled gracefully"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        callback_called = []

        def failing_callback(event: LogEvent) -> None:
            raise ValueError("Callback error")

        def working_callback(event: LogEvent) -> None:
            callback_called.append(event)

        logger.register_callback(failing_callback)
        logger.register_callback(working_callback)

        # Should not raise, and working callback should still be called
        logger._call_callbacks(LogEvent.LOG_CREATED)

        assert len(callback_called) == 1
        assert callback_called[0] == LogEvent.LOG_CREATED


class TestFaaSrFunctionLoggerS3Operations:
    """Tests for FaaSrFunctionLogger S3 operations"""

    def test_check_for_logs_exists(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _check_for_logs when logs exist"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=b"test log content",
        )

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger._check_for_logs() is True

    def test_check_for_logs_not_exists(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _check_for_logs when logs don't exist"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger._check_for_logs() is False

    def test_get_logs(self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client):
        """Test _get_logs parses log entries correctly"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        log_content = (
            "[1.0] First log entry\n[2.0] Second log entry\n[3.0] Third log entry"
        )
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=log_content.encode("utf-8"),
        )

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        logs = logger._get_logs()
        assert len(logs) == 3
        assert "[1.0] First log entry" in logs[0]
        assert "[2.0] Second log entry" in logs[1]
        assert "[3.0] Third log entry" in logs[2]

    def test_get_logs_with_multiline_entries(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test _get_logs with multiline log entries"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        log_content = "[1.0] First log entry\nwith multiple lines\n[2.0] Second entry"
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=log_content.encode("utf-8"),
        )

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        logs = logger._get_logs()
        assert len(logs) == 2
        assert "First log entry" in logs[0]
        assert "with multiple lines" in logs[0]
        assert "Second entry" in logs[1]

    def test_get_logs_with_s3_error(self, s3_client_fixture: FaaSrS3Client):
        """Test _get_logs raises S3ClientError on S3 error"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        # Mock s3_client to raise an error
        mock_error = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
        )
        s3_client_fixture._client = MagicMock()
        s3_client_fixture._client.get_object.side_effect = mock_error

        with pytest.raises(S3ClientError, match="boto3 client error getting object"):
            logger._get_logs()


class TestFaaSrFunctionLoggerThreadManagement:
    """Tests for FaaSrFunctionLogger thread management"""

    def test_start(self, s3_client_fixture: FaaSrS3Client):
        """Test start method creates and starts thread"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            interval_seconds=0.1,
        )

        assert logger._thread is None
        logger.start()
        assert logger._thread is not None
        assert logger._thread.is_alive()
        assert logger._thread.daemon is True

        logger.stop()
        time.sleep(0.2)  # Wait for thread to stop

    def test_stop(self, s3_client_fixture: FaaSrS3Client):
        """Test stop method sets stop flag"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        assert logger.stop_requested is False
        logger.stop()
        assert logger.stop_requested is True


class TestFaaSrFunctionLoggerRunLoop:
    """Tests for FaaSrFunctionLogger run loop behavior"""

    def test_run_detects_logs_started(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test run loop detects when logs start"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            interval_seconds=0.1,
        )

        callback_events = []

        def callback(event: LogEvent) -> None:
            callback_events.append(event)

        logger.register_callback(callback)
        logger.start()

        # Wait a bit, then create logs
        time.sleep(0.2)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=b"[1.0] First log",
        )

        # Wait for detection
        time.sleep(0.3)

        logger.stop()
        time.sleep(0.2)

        assert logger.logs_started is True
        assert LogEvent.LOG_CREATED in callback_events

    def test_run_fetches_new_logs(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test run loop fetches and updates logs"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=b"[1.0] First log",
        )

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            interval_seconds=0.1,
        )

        callback_events = []

        def callback(event: LogEvent) -> None:
            callback_events.append(event)

        logger.register_callback(callback)
        logger.start()

        # Wait for initial fetch
        time.sleep(0.2)

        # Add more logs
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=b"[1.0] First log\n[2.0] Second log",
        )

        # Wait for update
        time.sleep(0.3)

        logger.stop()
        time.sleep(0.2)

        assert len(logger.logs) >= 1
        assert LogEvent.LOG_UPDATED in callback_events

    def test_run_completes_when_stopped(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client
    ):
        """Test run loop completes when stop is requested"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=b"[1.0] First log",
        )

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            interval_seconds=0.1,
        )

        callback_events = []

        def callback(event: LogEvent) -> None:
            callback_events.append(event)

        logger.register_callback(callback)
        logger.start()

        # Wait for logs to be fetched
        time.sleep(0.3)

        # Stop and wait for completion
        logger.stop()
        time.sleep(0.3)

        assert logger.logs_complete is True
        assert LogEvent.LOG_COMPLETE in callback_events

    def test_run_with_stream_logs(
        self, s3_client: S3Client, s3_client_fixture: FaaSrS3Client, caplog
    ):
        """Test run loop streams logs when enabled"""
        s3_client.create_bucket(Bucket=DATASTORE_BUCKET)
        s3_client.put_object(
            Bucket=DATASTORE_BUCKET,
            Key="test/invocation/test_function.txt",
            Body=b"[1.0] First log\n[2.0] Second log",
        )

        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
            stream_logs=True,
            interval_seconds=0.1,
        )

        logger.start()
        time.sleep(0.3)
        logger.stop()
        time.sleep(0.2)

        # Check that logs were streamed (via logger)
        assert len(logger.logs) > 0

    def test_update_logs_thread_safe(self, s3_client_fixture: FaaSrS3Client):
        """Test _update_logs is thread-safe"""
        logger = FaaSrFunctionLogger(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation",
            s3_client=s3_client_fixture,
        )

        def update_logs():
            for i in range(10):
                logger._update_logs([f"log_{i}"])

        threads = [threading.Thread(target=update_logs) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have 50 logs total (5 threads * 10 logs each)
        assert len(logger.logs) == 50
