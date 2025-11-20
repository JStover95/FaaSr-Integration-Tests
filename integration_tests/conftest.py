import argparse
import os
import sys
import time
from contextlib import contextmanager
from unittest import mock

import pytest
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.s3_client import FaaSrS3Client
from framework.utils.enums import FunctionStatus
from framework.workflow_runner import WorkflowRunner

load_dotenv()

TIMEOUT = 180
CHECK_INTERVAL = 1


class WorkflowTester:
    """
    A tester for a FaaSr workflow.

    This class is responsible for:
    - Triggering a workflow
    - Cleaning up resources
    - Asserting that objects exist in S3
    - Asserting that objects do not exist in S3
    - Asserting that the content of an object in S3 equals the expected content.
    - Asserting that a function has completed.
    - Asserting that a function has not been invoked.
    """

    def __init__(self):
        self.runner = WorkflowRunner.trigger_workflow(
            timeout=TIMEOUT,
            check_interval=CHECK_INTERVAL,
            stream_logs=True,
        )

    @property
    def s3_client(self) -> FaaSrS3Client:
        """Get the workflow runner's S3 client."""
        return self.runner.s3_client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def _cleanup(self) -> bool:
        """
        Cleanup resources when exiting the context manager.
        This ensures proper thread cleanup even if an exception occurs.
        """
        try:
            # Attempt graceful shutdown first
            if not self.runner.shutdown(timeout=10):
                # If graceful shutdown fails, force shutdown
                self.runner.force_shutdown()

            # Perform comprehensive cleanup
            self.runner.cleanup()

        except Exception as e:
            # Log cleanup errors but don't raise them to avoid masking original exceptions
            print(f"Warning: Error during cleanup: {e}")

        # Return False to not suppress any exceptions that occurred in the context
        return False

    def get_s3_key(self, file_name: str) -> str:
        """
        Get the S3 key for a given file name.

        Args:
            file_name: The name of the file to get the S3 key for.

        Returns:
            The S3 key for the given file name.
        """
        return f"integration-tests/{self.runner.invocation_id}/{file_name}"

    def wait_for(self, function_name: str, should_fail: bool = False) -> FunctionStatus:
        """
        Wait for a function to complete.

        Args:
            function_name: The name of the function to wait for.

        Returns:
            The status of the function.

        Raises:
            Exception: If the function failed, skipped, timed out, or not invoked.
        """
        status = self.runner.get_function_statuses()[function_name]
        while not (
            status == FunctionStatus.COMPLETED
            or status == FunctionStatus.NOT_INVOKED
            or status == FunctionStatus.FAILED
            or status == FunctionStatus.SKIPPED
            or status == FunctionStatus.TIMEOUT
        ):
            time.sleep(CHECK_INTERVAL)
            status = self.runner.get_function_statuses()[function_name]

        if not should_fail and status == FunctionStatus.FAILED:
            raise Exception(f"Function {function_name} failed")
        elif status == FunctionStatus.SKIPPED:
            raise Exception(f"Function {function_name} skipped")
        elif status == FunctionStatus.TIMEOUT:
            raise Exception(f"Function {function_name} timed out")

        return status

    def assert_object_exists(self, object_name: str) -> None:
        """
        Assert that an object exists in S3.

        Args:
            object_name: The name of the object to assert exists.
        """
        key = self.get_s3_key(object_name)
        assert self.s3_client.object_exists(key)

    def assert_object_does_not_exist(self, object_name: str) -> None:
        """
        Assert that an object does not exist in S3.

        Args:
            object_name: The name of the object to assert does not exist.
        """
        key = self.get_s3_key(object_name)
        assert not self.s3_client.object_exists(key)

    def assert_content_equals(self, object_name: str, expected_content: str) -> None:
        """
        Assert that the content of an object in S3 equals the expected content.

        Args:
            object_name: The name of the object to assert the content of.
            expected_content: The expected content of the object.
        """
        key = self.get_s3_key(object_name)
        assert self.s3_client.get_object(key) == expected_content

    def assert_function_completed(self, function_name: str) -> None:
        """
        Assert that a function has completed.

        Args:
            function_name: The name of the function to assert has completed.
        """
        assert (
            self.runner.get_function_statuses()[function_name]
            == FunctionStatus.COMPLETED
        )

    def assert_function_not_invoked(self, function_name: str) -> None:
        """
        Assert that a function has not been invoked.

        Args:
            function_name: The name of the function to assert has not been invoked.
        """
        assert (
            self.runner.get_function_statuses()[function_name]
            == FunctionStatus.NOT_INVOKED
        )


@pytest.fixture(scope="session")
def workflow_file():
    @contextmanager
    def wrapper(workflow_file: str):
        with mock.patch(
            "faasr_workflow.scripts.invoke_workflow.argparse.ArgumentParser.parse_args"
        ) as mock_parse_args:
            mock_parse_args.return_value = argparse.Namespace(
                workflow_file=workflow_file
            )
            with WorkflowTester() as tester:
                yield tester

    return wrapper
