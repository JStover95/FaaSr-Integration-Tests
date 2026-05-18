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
from framework.utils import failed, has_final_state, skipped, timed_out
from framework.utils.enums import FunctionStatus
from framework.workflow_runner import WorkflowRunner

load_dotenv()

TIMEOUT = 180
CHECK_INTERVAL = 1


class WorkflowTester:
    """
    A tester for a FaaSr workflow.

    This class is responsible for:
    - Triggering and re-triggering a workflow across multiple invocations
    - Waiting for workflow and function completion
    - Cleaning up resources
    - Asserting that objects exist in S3
    - Asserting that objects do not exist in S3
    - Asserting that the content of an object in S3 equals the expected content.
    - Asserting that a function has completed.
    - Asserting that a function has not been invoked.
    """

    def __init__(
        self,
        test_invocation_id: str | None = None,
        num_invocations: int | None = None,
    ):
        self._test_invocation_id = test_invocation_id
        self._requires_invocation_num = num_invocations is not None
        self._num_invocations = num_invocations if num_invocations is not None else 1

        if self._num_invocations < 1:
            raise ValueError("num_invocations must be at least 1")

        self._current_invocation = 0
        self._is_complete = True
        self.runner: WorkflowRunner
        self._trigger_workflow()

    def _trigger_workflow(self) -> None:
        """Trigger (or re-trigger) the workflow."""
        if not self._is_complete:
            raise RuntimeError("Cannot trigger workflow: a run is still in progress.")

        if getattr(self, "runner", None) is not None:
            self._cleanup_runner()

        self._is_complete = False
        self.runner = WorkflowRunner.trigger_workflow(
            timeout=TIMEOUT,
            check_interval=CHECK_INTERVAL,
            stream_logs=True,
            test_invocation_id=self._test_invocation_id,
        )
        self._current_invocation += 1

    def _wait_for_all(self) -> None:
        """
        Wait for all functions in the workflow to finish.

        Raises:
            RuntimeError: If any function failed, was skipped, or timed out.
        """
        statuses = self.runner.get_function_statuses()
        while not all(has_final_state(status) for status in statuses.values()):
            time.sleep(CHECK_INTERVAL)
            statuses = self.runner.get_function_statuses()

        for function_name, status in statuses.items():
            if failed(status):
                raise RuntimeError(f"Function {function_name} failed")
            if skipped(status):
                raise RuntimeError(f"Function {function_name} skipped")
            if timed_out(status):
                raise RuntimeError(f"Function {function_name} timed out")

        self._is_complete = True

    def _ensure_invocation(self, invocation_num: int) -> None:
        """Advance workflow invocations until the current one matches invocation_num."""
        while self._current_invocation < invocation_num:
            self._wait_for_all()
            if self._current_invocation >= self._num_invocations:
                raise RuntimeError(
                    f"Cannot advance to invocation {invocation_num}: "
                    f"only {self._num_invocations} invocation(s) configured"
                )
            self._trigger_workflow()

        if self._current_invocation > invocation_num:
            raise RuntimeError(
                f"Cannot wait for invocation {invocation_num}: "
                f"already at invocation {self._current_invocation}"
            )

    @property
    def s3_client(self) -> FaaSrS3Client:
        """Get the workflow runner's S3 client."""
        return self.runner.s3_client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._is_complete:
            try:
                self._wait_for_all()
            except Exception:
                pass
        self._cleanup()

    def _cleanup_runner(self) -> None:
        """Shut down and clean up the current workflow runner."""
        try:
            if not self.runner.shutdown(timeout=10):
                self.runner.force_shutdown()
            self.runner.cleanup()
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")

    def _cleanup(self) -> bool:
        """
        Cleanup resources when exiting the context manager.
        This ensures proper thread cleanup even if an exception occurs.
        """
        if getattr(self, "runner", None) is not None:
            self._cleanup_runner()

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

    def wait_for(
        self,
        function_name: str,
        should_fail: bool = False,
        invocation_num: int | None = None,
    ) -> FunctionStatus:
        """
        Wait for a function to complete.

        When num_invocations was set on the tester, invocation_num is required and
        must be in [1, num_invocations]. The tester advances through workflow
        invocations automatically until the requested invocation is active.

        Args:
            function_name: The name of the function to wait for.
            should_fail: When True, do not raise if the function failed.
            invocation_num: The workflow invocation to wait on (required when
                num_invocations was set on the tester).

        Returns:
            The status of the function.

        Raises:
            ValueError: If invocation_num is missing or out of range.
            RuntimeError: If the function failed, was skipped, or timed out.
        """
        if self._requires_invocation_num:
            if invocation_num is None:
                raise ValueError(
                    "invocation_num is required when num_invocations is set on the tester"
                )
        else:
            invocation_num = invocation_num or self._current_invocation

        if not 1 <= invocation_num <= self._num_invocations:
            raise ValueError(
                f"invocation_num must be between 1 and {self._num_invocations}, "
                f"got {invocation_num}"
            )

        self._ensure_invocation(invocation_num)

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
            raise RuntimeError(f"Function {function_name} failed")
        elif status == FunctionStatus.SKIPPED:
            raise RuntimeError(f"Function {function_name} skipped")
        elif status == FunctionStatus.TIMEOUT:
            raise RuntimeError(f"Function {function_name} timed out")

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

    def assert_logs_contain(self, function_name: str, expected_content: str) -> None:
        """
        Assert that the logs of a function contain the expected content.

        Args:
            function_name: The name of the function to assert the logs of.
            expected_content: The expected content of the logs.
        """
        assert expected_content in self.runner.get_function_logs_content(function_name)

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

    def assert_function_failed(self, function_name: str) -> None:
        """
        Assert that a function has failed.

        Args:
            function_name: The name of the function to assert has failed.
        """
        assert (
            self.runner.get_function_statuses()[function_name] == FunctionStatus.FAILED
        )


@pytest.fixture(scope="session")
def workflow_file():
    @contextmanager
    def wrapper(
        workflow_file: str,
        test_invocation_id: str | None = None,
        num_invocations: int | None = None,
    ):
        with mock.patch(
            "faasr_workflow.scripts.invoke_workflow.argparse.ArgumentParser.parse_args"
        ) as mock_parse_args:
            mock_parse_args.return_value = argparse.Namespace(
                workflow_file=workflow_file
            )
            with WorkflowTester(
                test_invocation_id=test_invocation_id,
                num_invocations=num_invocations,
            ) as tester:
                yield tester

    return wrapper
