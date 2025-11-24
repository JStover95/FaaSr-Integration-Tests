import os
import time
from unittest.mock import MagicMock, patch

import pytest

from framework.s3_client import FaaSrS3Client
from framework.utils.enums import FunctionStatus, InvocationStatus
from framework.workflow_runner import (
    REQUIRED_ENV_VARS,
    InitializationError,
    StopMonitoring,
    WorkflowRunner,
)
from tests.conftest import workflow_data
from tests.tests_utils.mock_faasr_function import MockFaaSrFunction


@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    """Create a FaaSrS3Client instance for testing"""
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )


@pytest.fixture(scope="module", autouse=True)
def with_patched_function_class():
    """Patch the FaaSrFunction class with a mock class"""
    with patch("framework.workflow_runner.FaaSrFunction", MockFaaSrFunction):
        yield


@pytest.fixture
def mock_workflow_runner(s3_client_fixture: FaaSrS3Client):
    """Create a mock WorkflowRunner instance for testing"""
    runner = WorkflowRunner(
        faasr_payload=workflow_data(),
        timeout=120,
        check_interval=1,
        stream_logs=False,
    )
    runner.s3_client = s3_client_fixture
    return runner


class TestWorkflowRunnerInit:
    """Tests for WorkflowRunner initialization"""

    def test_init_success(self, with_mock_env: None):
        """Test successful initialization"""
        runner = WorkflowRunner(
            faasr_payload=workflow_data(),
            timeout=120,
            check_interval=1,
            stream_logs=False,
        )

        assert runner._faasr_payload == workflow_data()
        assert runner.timeout == 120
        assert runner.check_interval == 1
        assert runner.workflow_name == "test_workflow"
        assert runner.workflow_invoke == "func1"
        assert runner.invocation_id == "test-invocation-123"
        assert runner.logger is not None
        assert runner.s3_client is not None
        assert runner._functions == {}
        assert runner._prev_statuses == {}
        assert runner._failure_detected is False

    @pytest.parametrize("env_var", REQUIRED_ENV_VARS)
    def test_init_missing_env_vars(self, env_var: str, with_mock_env: None):
        """Test initialization fails with missing environment variables"""
        # Save original env
        original_env = os.environ.copy()

        try:
            # Clear required env var
            del os.environ[env_var]

            with pytest.raises(
                InitializationError,
                match=f"Missing required environment variables: {env_var}",
            ):
                WorkflowRunner(
                    faasr_payload=workflow_data(),
                    timeout=120,
                    check_interval=1,
                )
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_init_builds_adjacency_graph(self, with_mock_env: None):
        """Test that adjacency graph is built during initialization"""
        runner = WorkflowRunner(
            faasr_payload=workflow_data(),
            timeout=120,
            check_interval=1,
        )

        assert runner.adj_graph is not None
        assert runner.reverse_adj_graph is not None
        assert runner.ranks is not None

    def test_invocation_id_property(self, with_mock_env: None):
        """Test invocation_id property"""
        runner = WorkflowRunner(
            faasr_payload=workflow_data(),
            timeout=120,
            check_interval=1,
        )

        assert runner.invocation_id == "test-invocation-123"


class TestWorkflowRunnerFunctionBuilding:
    """Tests for WorkflowRunner function building"""

    def test_build_functions(self, mock_workflow_runner: WorkflowRunner):
        """Test building functions from workflow payload"""
        functions = mock_workflow_runner._build_functions(stream_logs=False)

        # Should have functions for func1, func2, func3
        assert len(functions) == 3
        assert "func1" in functions
        assert "func2" in functions
        assert "func3" in functions

        # func1 should be INVOKED
        assert functions["func1"].status == FunctionStatus.INVOKED

        # func2 and func3 should be PENDING
        assert functions["func2"].status == FunctionStatus.PENDING
        assert functions["func3"].status == FunctionStatus.PENDING

    def test_build_functions_with_ranks(self, s3_client_fixture: FaaSrS3Client):
        """Test building functions with ranks"""
        # Create payload with ranked function
        payload = workflow_data()
        payload["ActionList"]["ranked_func"] = {
            "FaaSServer": "GH",
            "FunctionName": "ranked_func",
            "Type": "Python",
            "Rank": 3,
        }

        runner = WorkflowRunner(
            faasr_payload=payload,
            timeout=120,
            check_interval=1,
        )
        runner.s3_client = s3_client_fixture

        functions = runner._build_functions(stream_logs=False)

        # Should have ranked functions
        assert "ranked_func(1)" in functions
        assert "ranked_func(2)" in functions
        assert "ranked_func(3)" in functions


class TestWorkflowRunnerStatusManagement:
    """Tests for WorkflowRunner status management"""

    def test_get_function_statuses(self, mock_workflow_runner: WorkflowRunner):
        """Test getting function statuses"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1 status
        mock_workflow_runner._functions["func1"].with_status(FunctionStatus.RUNNING)

        statuses = mock_workflow_runner.get_function_statuses()

        assert statuses["func1"] == FunctionStatus.RUNNING
        assert statuses["func2"] == FunctionStatus.PENDING

    def test_get_function_logs_content(self, mock_workflow_runner: WorkflowRunner):
        """Test getting function logs content"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1 logs
        mock_workflow_runner._functions["func1"].with_logs_content(
            "log line 1\nlog line 2"
        )

        logs = mock_workflow_runner.get_function_logs_content("func1")
        assert logs == "log line 1\nlog line 2"

    def test_monitoring_complete_property(self, mock_workflow_runner: WorkflowRunner):
        """Test monitoring_complete property"""
        assert mock_workflow_runner.monitoring_complete is False
        mock_workflow_runner._set_monitoring_complete()
        assert mock_workflow_runner.monitoring_complete is True

    def test_shutdown_requested_property(self, mock_workflow_runner: WorkflowRunner):
        """Test shutdown_requested property"""
        assert mock_workflow_runner.shutdown_requested is False
        mock_workflow_runner._set_shutdown_requested()
        assert mock_workflow_runner.shutdown_requested is True

    def test_failure_detected_property(self, mock_workflow_runner: WorkflowRunner):
        """Test failure_detected property"""
        assert mock_workflow_runner.failure_detected is False
        mock_workflow_runner._set_failure_detected()
        assert mock_workflow_runner.failure_detected is True


class TestWorkflowRunnerInvocationChecking:
    """Tests for WorkflowRunner invocation checking"""

    def test_get_invocation_status_invoked(self, mock_workflow_runner: WorkflowRunner):
        """Test _get_invocation_status returns INVOKED when function was invoked"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        functions = mock_workflow_runner._build_functions(stream_logs=False)
        # Modify func1 to have invocations
        invoker = functions["func1"].with_invocations({"func2"})
        function = functions["func2"]

        status = mock_workflow_runner._get_invocation_status(invoker, function)
        assert status == InvocationStatus.INVOKED

    def test_get_invocation_status_not_invoked(
        self, mock_workflow_runner: WorkflowRunner
    ):
        """Test _get_invocation_status returns NOT_INVOKED when function was not invoked"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        functions = mock_workflow_runner._build_functions(stream_logs=False)
        # Modify func1 to invoke func3 (not func2)
        invoker = functions["func1"].with_invocations({"func3"})
        function = functions["func2"]

        status = mock_workflow_runner._get_invocation_status(invoker, function)
        assert status == InvocationStatus.NOT_INVOKED

    def test_get_invocation_status_pending(self, mock_workflow_runner: WorkflowRunner):
        """Test _get_invocation_status returns PENDING when invocations not yet determined"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        functions = mock_workflow_runner._build_functions(stream_logs=False)
        # Modify func1 to have no invocations determined yet
        invoker = functions["func1"].with_invocations(None)
        function = functions["func2"]

        status = mock_workflow_runner._get_invocation_status(invoker, function)
        assert status == InvocationStatus.PENDING

    def test_check_invocation_status(self, mock_workflow_runner: WorkflowRunner):
        """Test _check_invocation_status using reverse adjacency graph"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1 to have invocations
        mock_workflow_runner._functions["func1"].with_invocations({"func2"})

        func2 = mock_workflow_runner._functions["func2"]
        status = mock_workflow_runner._check_invocation_status(func2)
        assert status == InvocationStatus.INVOKED


class TestWorkflowRunnerMonitoring:
    """Tests for WorkflowRunner monitoring logic"""

    def test_handle_pending_invoked(self, mock_workflow_runner: WorkflowRunner):
        """Test _handle_pending sets status to INVOKED when function was invoked"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1 to have invocations
        mock_workflow_runner._functions["func1"].with_invocations({"func2"})

        func2 = mock_workflow_runner._functions["func2"]
        mock_workflow_runner._handle_pending(func2)

        assert func2.status == FunctionStatus.INVOKED

    def test_handle_pending_not_invoked(self, mock_workflow_runner: WorkflowRunner):
        """Test _handle_pending sets status to NOT_INVOKED when function was not invoked"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1 to invoke func3 (not func2)
        mock_workflow_runner._functions["func1"].with_invocations({"func3"})

        func2 = mock_workflow_runner._functions["func2"]
        mock_workflow_runner._handle_pending(func2)

        assert func2.status == FunctionStatus.NOT_INVOKED

    def test_all_functions_completed(self, mock_workflow_runner: WorkflowRunner):
        """Test _all_functions_completed returns True when all functions completed"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify statuses
        mock_workflow_runner._functions["func1"].with_status(FunctionStatus.COMPLETED)
        mock_workflow_runner._functions["func2"].with_status(FunctionStatus.NOT_INVOKED)
        mock_workflow_runner._functions["func3"].with_status(FunctionStatus.COMPLETED)

        assert mock_workflow_runner._all_functions_completed() is True

    def test_all_functions_completed_false(self, mock_workflow_runner: WorkflowRunner):
        """Test _all_functions_completed returns False when not all functions completed"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify statuses
        mock_workflow_runner._functions["func1"].with_status(FunctionStatus.COMPLETED)
        mock_workflow_runner._functions["func2"].with_status(
            FunctionStatus.RUNNING
        )  # Not completed

        assert mock_workflow_runner._all_functions_completed() is False

    def test_get_active_functions(self, mock_workflow_runner: WorkflowRunner):
        """Test _get_active_functions returns functions with logs started but not complete"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1: running with logs started but not complete
        mock_workflow_runner._functions["func1"].with_status(
            FunctionStatus.RUNNING
        ).with_logs_started(True).with_logs_complete(False)
        # Modify func2: running with logs complete (not active)
        mock_workflow_runner._functions["func2"].with_status(
            FunctionStatus.RUNNING
        ).with_logs_started(True).with_logs_complete(True)
        # Modify func3: completed (final state, not active)
        mock_workflow_runner._functions["func3"].with_status(FunctionStatus.COMPLETED)

        active = mock_workflow_runner._get_active_functions()
        assert len(active) == 1
        assert active[0].function_name == "func1"

    def test_cascade_failure(self, mock_workflow_runner: WorkflowRunner):
        """Test _cascade_failure sets all non-final functions to SKIPPED"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify statuses
        mock_workflow_runner._functions["func1"].with_status(
            FunctionStatus.FAILED
        )  # Already failed
        # func2 is already PENDING (should be skipped)
        mock_workflow_runner._functions["func3"].with_status(
            FunctionStatus.COMPLETED
        )  # Already completed, should not change

        mock_workflow_runner._cascade_failure()

        assert mock_workflow_runner._functions["func1"].status == FunctionStatus.FAILED
        assert mock_workflow_runner._functions["func2"].status == FunctionStatus.SKIPPED
        assert (
            mock_workflow_runner._functions["func3"].status == FunctionStatus.COMPLETED
        )

    def test_monitor_workflow_execution_all_completed(
        self, mock_workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution raises StopMonitoring when all completed"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify statuses
        mock_workflow_runner._functions["func1"].with_status(FunctionStatus.COMPLETED)
        mock_workflow_runner._functions["func2"].with_status(FunctionStatus.NOT_INVOKED)
        mock_workflow_runner._functions["func3"].with_status(FunctionStatus.COMPLETED)
        mock_workflow_runner._prev_statuses = (
            mock_workflow_runner.get_function_statuses()
        )

        with pytest.raises(StopMonitoring, match="All functions completed"):
            mock_workflow_runner._monitor_workflow_execution()

    def test_monitor_workflow_execution_failure_detected(
        self, mock_workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution handles failure detection"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1: failed with logs complete
        mock_workflow_runner._functions["func1"].with_status(
            FunctionStatus.FAILED
        ).with_logs_complete(True)
        # func2 is already PENDING
        mock_workflow_runner._prev_statuses = (
            mock_workflow_runner.get_function_statuses()
        )

        # First call should set failure_detected
        try:
            mock_workflow_runner._monitor_workflow_execution()
        except StopMonitoring:
            pass

        assert mock_workflow_runner.failure_detected is True

    def test_monitor_workflow_execution_failure_cascade(
        self, mock_workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution cascades failure when all loggers complete"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1: failed with logs complete
        mock_workflow_runner._functions["func1"].with_status(
            FunctionStatus.FAILED
        ).with_logs_complete(True)
        # func2 is already PENDING
        mock_workflow_runner._prev_statuses = (
            mock_workflow_runner.get_function_statuses()
        )
        mock_workflow_runner._set_failure_detected()

        with pytest.raises(
            StopMonitoring, match="Failure detected and all active loggers completed"
        ):
            mock_workflow_runner._monitor_workflow_execution()

        # func2 should be skipped
        assert mock_workflow_runner._functions["func2"].status == FunctionStatus.SKIPPED


class TestWorkflowRunnerTimeout:
    """Tests for WorkflowRunner timeout handling"""

    def test_reset_timer(self, mock_workflow_runner: WorkflowRunner):
        """Test _reset_timer resets the timer"""
        mock_workflow_runner.seconds_since_last_change = 50.0
        mock_workflow_runner._reset_timer()

        assert mock_workflow_runner.seconds_since_last_change == 0.0
        assert mock_workflow_runner.last_change_time > 0

    def test_increment_timer(self, mock_workflow_runner: WorkflowRunner):
        """Test _increment_timer increments the timer"""
        mock_workflow_runner._reset_timer()
        time.sleep(0.1)
        mock_workflow_runner._increment_timer()

        assert mock_workflow_runner.seconds_since_last_change > 0

    def test_did_timeout_true(self, with_mock_env: None):
        """Test _did_timeout returns True when timeout exceeded"""
        runner = WorkflowRunner(
            faasr_payload=workflow_data(),
            timeout=1,
            check_interval=1,
        )

        runner.seconds_since_last_change = 2.0
        assert runner._did_timeout() is True

    def test_did_timeout_false(self, mock_workflow_runner: WorkflowRunner):
        """Test _did_timeout returns False when timeout not exceeded"""
        mock_workflow_runner.seconds_since_last_change = 10.0
        assert mock_workflow_runner._did_timeout() is False

    def test_finish_monitoring_timeout(self, mock_workflow_runner: WorkflowRunner):
        """Test _finish_monitoring sets TIMEOUT for incomplete functions"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1: running (not final state)
        mock_workflow_runner._functions["func1"].with_status(FunctionStatus.RUNNING)
        # Modify func2: completed (final state, should not change)
        mock_workflow_runner._functions["func2"].with_status(FunctionStatus.COMPLETED)

        mock_workflow_runner._finish_monitoring()

        assert mock_workflow_runner._functions["func1"].status == FunctionStatus.TIMEOUT
        assert (
            mock_workflow_runner._functions["func2"].status == FunctionStatus.COMPLETED
        )
        assert mock_workflow_runner.monitoring_complete is True

    def test_finish_monitoring_shutdown(self, mock_workflow_runner: WorkflowRunner):
        """Test _finish_monitoring sets SKIPPED when shutdown requested"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        mock_workflow_runner._functions = mock_workflow_runner._build_functions(
            stream_logs=False
        )
        # Modify func1: running
        mock_workflow_runner._functions["func1"].with_status(FunctionStatus.RUNNING)

        mock_workflow_runner._set_shutdown_requested()
        mock_workflow_runner._finish_monitoring()

        assert mock_workflow_runner._functions["func1"].status == FunctionStatus.SKIPPED
        assert mock_workflow_runner.monitoring_complete is True


class TestWorkflowRunnerThreadManagement:
    """Tests for WorkflowRunner thread management"""

    def test_shutdown_no_thread(self, mock_workflow_runner: WorkflowRunner):
        """Test shutdown returns True when no monitoring thread"""
        assert mock_workflow_runner.shutdown() is True

    def test_shutdown_thread_alive(self, mock_workflow_runner: WorkflowRunner):
        """Test shutdown gracefully shuts down monitoring thread"""
        # Create a mock thread that will finish quickly
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        mock_workflow_runner._monitoring_thread = mock_thread

        result = mock_workflow_runner.shutdown(timeout=1.0)
        assert result is True
        assert mock_workflow_runner.shutdown_requested is True

    def test_force_shutdown(self, mock_workflow_runner: WorkflowRunner):
        """Test force_shutdown sets shutdown and monitoring complete"""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_workflow_runner._monitoring_thread = mock_thread

        mock_workflow_runner.force_shutdown()

        assert mock_workflow_runner.shutdown_requested is True
        assert mock_workflow_runner.monitoring_complete is True

    def test_cleanup(self, mock_workflow_runner: WorkflowRunner):
        """Test cleanup performs graceful shutdown"""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        mock_workflow_runner._monitoring_thread = mock_thread

        mock_workflow_runner.cleanup()

        assert mock_workflow_runner.shutdown_requested is True


class TestWorkflowRunnerHelpers:
    """Tests for WorkflowRunner helper methods"""

    def test_iter_ranks_single(self, mock_workflow_runner: WorkflowRunner):
        """Test _iter_ranks yields single function name when rank <= 1"""
        ranks = list(mock_workflow_runner._iter_ranks("func1"))
        assert ranks == ["func1"]

    def test_iter_ranks_multiple(self, mock_workflow_runner: WorkflowRunner):
        """Test _iter_ranks yields multiple ranks when rank > 1"""
        # Mock ranks to have a function with rank 3
        mock_workflow_runner.ranks = {"ranked_func": 3}

        ranks = list(mock_workflow_runner._iter_ranks("ranked_func"))
        assert ranks == ["ranked_func(1)", "ranked_func(2)", "ranked_func(3)"]

    def test_log_status_change(self, mock_workflow_runner: WorkflowRunner):
        """Test _log_status_change logs status changes"""
        # Build functions from workflow data (already MockFaaSrFunction due to patch)
        functions = mock_workflow_runner._build_functions(stream_logs=False)
        # Modify func1 status
        function = functions["func1"].with_status(FunctionStatus.RUNNING)

        # Should not raise
        mock_workflow_runner._log_status_change(function)
