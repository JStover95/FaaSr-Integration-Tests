from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from framework.faasr_function import FaaSrFunction
from framework.utils.enums import FunctionStatus

if TYPE_CHECKING:
    from framework.s3_client import FaaSrS3Client
else:
    FaaSrS3Client = object


class MockFaaSrFunction(FaaSrFunction):
    """
    A mock implementation of FaaSrFunction for testing.

    This class provides a fluent interface for configuring mock function instances
    in tests. It inherits from FaaSrFunction but uses mocked dependencies to avoid
    actual S3 and logger initialization.

    Example usage:
        ```python
        mock_function = MockFaaSrFunction(
            function_name="test_function",
            workflow_name="test_workflow",
            invocation_folder="test/invocation"
        ).with_status(FunctionStatus.RUNNING).with_invocations({"func1", "func2"})
        ```

    The fluent interface allows chaining configuration methods:
        ```python
        workflow_runner._functions["function_name"].with_status(...).with_invocations(...)
        ```
    """

    def __init__(
        self,
        *,
        function_name: str,
        workflow_name: str,
        invocation_folder: str,
        s3_client: FaaSrS3Client,
        stream_logs: bool = False,
        interval_seconds: int = 3,
        start_logger: bool = False,
    ):
        """
        Initialize a mock FaaSrFunction.

        Args:
            function_name: The name of the function.
            workflow_name: The name of the workflow.
            invocation_folder: The folder where the logs are stored.
            s3_client: Optional S3 client. If None, a MagicMock will be created.
            stream_logs: Whether to stream the logs to the console.
            interval_seconds: The interval in seconds to check for new logs.
            start_logger: Whether to start the logger (default: False for mocks).
        """
        # Initialize parent with mocked dependencies
        super().__init__(
            function_name=function_name,
            workflow_name=workflow_name,
            invocation_folder=invocation_folder,
            s3_client=s3_client,
            stream_logs=stream_logs,
            interval_seconds=interval_seconds,
            start_logger=start_logger,
        )

        # Replace the logger with a mock to avoid actual log monitoring
        self._logger = MagicMock()
        self._logger.logs = []
        self._logger.logs_content = ""
        self._logger.logs_complete = False
        self._logger.logs_started = False
        self._logger.stop = MagicMock()
        self._logger.wait = MagicMock()
        self._logger.stop_requested = False

        # Helped for mocking function_failed and function_complete
        self._function_failed = False
        self._function_complete = False

    def with_status(self, status: FunctionStatus) -> "MockFaaSrFunction":
        """
        Set the function status using a fluent interface.

        Args:
            status: The status to set.

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        self.set_status(status)
        return self

    def with_invocations(self, invocations: set[str] | None) -> "MockFaaSrFunction":
        """
        Set the function invocations using a fluent interface.

        Args:
            invocations: The set of invoked function names, or None if not yet determined.

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        with self._lock:
            self._invocations = invocations.copy() if invocations is not None else None
        return self

    def with_logs(self, logs: list[str]) -> "MockFaaSrFunction":
        """
        Set the function logs using a fluent interface.

        Args:
            logs: The list of log lines.

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        self._logger.logs = logs
        self._logger.logs_content = "\n".join(logs)
        return self

    def with_logs_content(self, logs_content: str) -> "MockFaaSrFunction":
        """
        Set the function logs content using a fluent interface.

        Args:
            logs_content: The logs as a single string.

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        self._logger.logs_content = logs_content
        self._logger.logs = logs_content.split("\n") if logs_content else []
        return self

    def with_logs_complete(self, complete: bool = True) -> "MockFaaSrFunction":
        """
        Set the logs complete flag using a fluent interface.

        Args:
            complete: Whether logs are complete (default: True).

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        self._logger.logs_complete = complete
        return self

    def with_logs_started(self, started: bool = True) -> "MockFaaSrFunction":
        """
        Set the logs started flag using a fluent interface.

        Args:
            started: Whether logs have started (default: True).

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        self._logger.logs_started = started
        return self

    def with_function_complete(self, complete: bool = True) -> "MockFaaSrFunction":
        """
        Set the function completion status by mocking the done file check.

        Args:
            complete: Whether the function is complete (default: True).

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        self.s3_client.object_exists = MagicMock(return_value=complete)
        return self

    def with_function_failed(self, failed: bool = True) -> "MockFaaSrFunction":
        """
        Set the function failure status by adding/removing error logs.

        Args:
            failed: Whether the function has failed (default: True).

        Returns:
            MockFaaSrFunction: Self for method chaining.
        """
        if failed:
            # Add an error log to trigger failure detection
            if (
                not self._logger.logs_content
                or "[ERROR]" not in self._logger.logs_content
            ):
                error_log = "[1.0] [ERROR] Mock function failure"
                current_logs = self._logger.logs if self._logger.logs else []
                self._logger.logs = current_logs + [error_log]
                self._logger.logs_content = (
                    self._logger.logs_content + "\n" + error_log
                    if self._logger.logs_content
                    else error_log
                )
        else:
            # Remove error logs
            if self._logger.logs:
                self._logger.logs = [
                    log for log in self._logger.logs if "[ERROR]" not in log
                ]
            if self._logger.logs_content:
                lines = self._logger.logs_content.split("\n")
                self._logger.logs_content = "\n".join(
                    line for line in lines if "[ERROR]" not in line
                )

        return self
