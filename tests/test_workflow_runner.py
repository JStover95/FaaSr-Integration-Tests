import os
import time
from unittest.mock import MagicMock, patch

import pytest

from framework.faasr_function import FaaSrFunction
from framework.s3_client import FaaSrS3Client
from framework.utils.enums import FunctionStatus, InvocationStatus
from framework.workflow_runner import (
    InitializationError,
    StopMonitoring,
    WorkflowRunner,
)
from tests.conftest import reverse_adj_graph, workflow_data


@pytest.fixture
def s3_client_fixture(with_mock_aws: None):
    """Create a FaaSrS3Client instance for testing"""
    return FaaSrS3Client(
        workflow_data=workflow_data(),
        access_key="test_access_key",
        secret_key="test_secret_key",
    )


@pytest.fixture
def workflow_runner(with_mock_aws: None):
    """Create a WorkflowRunner instance for testing"""
    runner = WorkflowRunner(
        faasr_payload=workflow_data(),
        timeout=60,
        check_interval=1,
        stream_logs=False,
    )
    return runner


class TestWorkflowRunnerInitialization:
    """Tests for WorkflowRunner initialization"""

    def test_init_success(self):
        """Test successful initialization"""
        payload = workflow_data()
        runner = WorkflowRunner(
            faasr_payload=payload,
            timeout=60,
            check_interval=1,
            stream_logs=False,
        )

        assert runner._faasr_payload == payload
        assert runner.timeout == 60
        assert runner.check_interval == 1
        assert runner._stream_logs is False
        # Check that adj_graph was built correctly (returns defaultdict(list))
        assert "func1" in runner.adj_graph
        assert "func2" in runner.adj_graph["func1"]
        assert "func3" in runner.adj_graph["func1"]
        # Check that ranks were calculated
        assert "func1" in runner.ranks
        assert "func2" in runner.ranks
        assert "func3" in runner.ranks
        assert runner.workflow_name == "test_workflow"
        assert runner.workflow_invoke == "func1"
        assert runner.s3_client is not None
        assert isinstance(runner.s3_client, FaaSrS3Client)

    @pytest.mark.parametrize(
        ("missing_var",),
        [
            ("S3_AccessKey",),
            ("S3_SecretKey",),
            ("GH_PAT",),
            ("GITHUB_REPOSITORY",),
            ("GITHUB_REF_NAME",),
        ],
    )
    def test_init_missing_env_var(self, missing_var: str):
        """Test initialization fails with missing environment variables"""
        env_backup = os.environ.get(missing_var)
        try:
            if missing_var in os.environ:
                del os.environ[missing_var]

            with pytest.raises(
                InitializationError,
                match=f"Missing required environment variables.*{missing_var}",
            ):
                WorkflowRunner(
                    faasr_payload=workflow_data(),
                    timeout=60,
                    check_interval=1,
                    stream_logs=False,
                )
        finally:
            if env_backup is not None:
                os.environ[missing_var] = env_backup

    def test_init_builds_reverse_adj_graph(self):
        """Test that reverse adjacency graph is built correctly"""
        runner = WorkflowRunner(
            faasr_payload=workflow_data(),
            timeout=60,
            check_interval=1,
            stream_logs=False,
        )

        assert runner.reverse_adj_graph == reverse_adj_graph()

    def test_init_sets_up_logger(self):
        """Test that logger is set up correctly"""
        runner = WorkflowRunner(
            faasr_payload=workflow_data(),
            timeout=60,
            check_interval=1,
            stream_logs=False,
        )

        assert runner.logger is not None
        assert runner.logger.name == "WorkflowRunner"
        assert runner.timestamp is not None

    def test_init_sets_up_signal_handlers(self):
        """Test that signal handlers are set up"""
        with patch("signal.signal") as mock_signal:
            WorkflowRunner(
                faasr_payload=workflow_data(),
                timeout=60,
                check_interval=1,
                stream_logs=False,
            )

            # Should register SIGINT and SIGTERM handlers
            assert mock_signal.call_count >= 2


class TestWorkflowRunnerProperties:
    """Tests for WorkflowRunner properties"""

    def test_invocation_id(self, workflow_runner: WorkflowRunner):
        """Test invocation_id property"""
        assert workflow_runner.invocation_id == "test-invocation-123"

    def test_monitoring_complete_property(self, workflow_runner: WorkflowRunner):
        """Test monitoring_complete property is thread-safe"""
        assert workflow_runner.monitoring_complete is False

        workflow_runner._set_monitoring_complete()
        assert workflow_runner.monitoring_complete is True

    def test_shutdown_requested_property(self, workflow_runner: WorkflowRunner):
        """Test shutdown_requested property is thread-safe"""
        assert workflow_runner.shutdown_requested is False

        workflow_runner._set_shutdown_requested()
        assert workflow_runner.shutdown_requested is True

    def test_failure_detected_property(self, workflow_runner: WorkflowRunner):
        """Test failure_detected property is thread-safe"""
        assert workflow_runner.failure_detected is False

        workflow_runner._set_failure_detected()
        assert workflow_runner.failure_detected is True


class TestWorkflowRunnerThreadSafeMethods:
    """Tests for WorkflowRunner thread-safe methods"""

    def test_get_function_statuses(self, workflow_runner: WorkflowRunner):
        """Test get_function_statuses returns a copy"""
        workflow_runner._functions = {
            "func1": MagicMock(status=FunctionStatus.PENDING),
            "func2": MagicMock(status=FunctionStatus.RUNNING),
        }

        statuses = workflow_runner.get_function_statuses()
        assert statuses == {
            "func1": FunctionStatus.PENDING,
            "func2": FunctionStatus.RUNNING,
        }

        # Modify the returned dict - should not affect internal state
        statuses["func1"] = FunctionStatus.COMPLETED
        assert workflow_runner._functions["func1"].status == FunctionStatus.PENDING

    def test_get_function_logs_content(self, workflow_runner: WorkflowRunner):
        """Test get_function_logs_content returns logs content"""
        mock_function = MagicMock()
        mock_function.logs_content = "log line 1\nlog line 2"
        workflow_runner._functions = {"func1": mock_function}

        logs = workflow_runner.get_function_logs_content("func1")
        assert logs == "log line 1\nlog line 2"


class TestWorkflowRunnerHelperMethods:
    """Tests for WorkflowRunner helper methods"""

    @pytest.mark.parametrize(
        ("function_name", "rank", "expected"),
        [
            ("func1", 1, ["func1"]),
            ("func3", 2, ["func3(1)", "func3(2)"]),
            ("func2", 1, ["func2"]),
        ],
    )
    def test_iter_ranks(
        self, workflow_runner: WorkflowRunner, function_name, rank, expected
    ):
        """Test _iter_ranks generates correct rank names"""
        workflow_runner.ranks = {function_name: rank}
        ranks = list(workflow_runner._iter_ranks(function_name))
        assert ranks == expected

    def test_check_invocation_status_invoked(self, workflow_runner: WorkflowRunner):
        """Test _check_invocation_status returns INVOKED when function is invoked"""
        # Create mock functions
        invoker = MagicMock(spec=FaaSrFunction)
        invoker.function_name = "func1"
        invoker.invocations = {"func2"}

        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func2"

        workflow_runner._functions = {"func1": invoker}
        workflow_runner.reverse_adj_graph = {"func2": {"func1"}}
        workflow_runner.ranks = {"func1": 1}

        status = workflow_runner._check_invocation_status(function)
        assert status == InvocationStatus.INVOKED

    def test_check_invocation_status_not_invoked(self, workflow_runner: WorkflowRunner):
        """Test _check_invocation_status returns NOT_INVOKED when function is not invoked"""
        # Create mock functions
        invoker = MagicMock(spec=FaaSrFunction)
        invoker.function_name = "func1"
        invoker.invocations = {"func3"}  # func2 not in invocations

        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func2"

        workflow_runner._functions = {"func1": invoker}
        workflow_runner.reverse_adj_graph = {"func2": {"func1"}}
        workflow_runner.ranks = {"func1": 1}

        status = workflow_runner._check_invocation_status(function)
        assert status == InvocationStatus.NOT_INVOKED

    def test_check_invocation_status_pending(self, workflow_runner: WorkflowRunner):
        """Test _check_invocation_status returns PENDING when invoker hasn't completed"""
        # Create mock functions
        invoker = MagicMock(spec=FaaSrFunction)
        invoker.function_name = "func1"
        invoker.invocations = None  # Not yet extracted

        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func2"

        workflow_runner._functions = {"func1": invoker}
        workflow_runner.reverse_adj_graph = {"func2": {"func1"}}
        workflow_runner.ranks = {"func1": 1}

        status = workflow_runner._check_invocation_status(function)
        assert status == InvocationStatus.PENDING

    def test_get_invocation_status_invoked(self, workflow_runner: WorkflowRunner):
        """Test _get_invocation_status returns INVOKED when function is in invocations"""
        invoker = MagicMock(spec=FaaSrFunction)
        invoker.invocations = {"func2"}

        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func2"

        status = workflow_runner._get_invocation_status(invoker, function)
        assert status == InvocationStatus.INVOKED

    def test_get_invocation_status_not_invoked(self, workflow_runner: WorkflowRunner):
        """Test _get_invocation_status returns NOT_INVOKED when function is not in invocations"""
        invoker = MagicMock(spec=FaaSrFunction)
        invoker.invocations = {"func3"}

        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func2"

        status = workflow_runner._get_invocation_status(invoker, function)
        assert status == InvocationStatus.NOT_INVOKED

    def test_get_invocation_status_pending(self, workflow_runner: WorkflowRunner):
        """Test _get_invocation_status returns PENDING when invocations is None"""
        invoker = MagicMock(spec=FaaSrFunction)
        invoker.invocations = None

        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func2"

        status = workflow_runner._get_invocation_status(invoker, function)
        assert status == InvocationStatus.PENDING

    def test_build_functions(self, workflow_runner: WorkflowRunner):
        """Test _build_functions creates function instances correctly"""
        with patch("framework.workflow_runner.FaaSrFunction") as mock_function_class:
            mock_function = MagicMock(spec=FaaSrFunction)
            mock_function.function_name = "func1"
            mock_function.status = FunctionStatus.PENDING
            mock_function_class.return_value = mock_function

            # Set ranks to test ranked functions
            workflow_runner.ranks = {"func1": 1, "func3": 2}
            workflow_runner.function_names = ["func1", "func3"]
            workflow_runner.workflow_invoke = "func1"

            functions = workflow_runner._build_functions(stream_logs=False)

            # Should create func1 and func3(1), func3(2)
            assert len(functions) == 3
            assert "func1" in functions
            assert "func3(1)" in functions
            assert "func3(2)" in functions

            # func1 should be set to INVOKED (it's the workflow invoke function)
            assert functions["func1"].set_status.called
            functions["func1"].set_status.assert_called_with(FunctionStatus.INVOKED)

    def test_handle_pending_invoked(self, workflow_runner: WorkflowRunner):
        """Test _handle_pending sets status to INVOKED when function is invoked"""
        function = MagicMock(spec=FaaSrFunction)
        function.status = FunctionStatus.PENDING

        with patch.object(workflow_runner, "_check_invocation_status") as mock_check:
            mock_check.return_value = InvocationStatus.INVOKED

            workflow_runner._handle_pending(function)

            function.set_status.assert_called_with(FunctionStatus.INVOKED)
            assert workflow_runner.last_change_time > 0

    def test_handle_pending_not_invoked(self, workflow_runner: WorkflowRunner):
        """Test _handle_pending sets status to NOT_INVOKED when function is not invoked"""
        function = MagicMock(spec=FaaSrFunction)
        function.status = FunctionStatus.PENDING

        with patch.object(workflow_runner, "_check_invocation_status") as mock_check:
            mock_check.return_value = InvocationStatus.NOT_INVOKED

            workflow_runner._handle_pending(function)

            function.set_status.assert_called_with(FunctionStatus.NOT_INVOKED)
            assert workflow_runner.last_change_time > 0

    def test_all_functions_completed_true(self, workflow_runner: WorkflowRunner):
        """Test _all_functions_completed returns True when all functions completed"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.COMPLETED
        func2 = MagicMock(spec=FaaSrFunction)
        func2.status = FunctionStatus.NOT_INVOKED

        workflow_runner._functions = {"func1": func1, "func2": func2}

        assert workflow_runner._all_functions_completed() is True

    def test_all_functions_completed_false(self, workflow_runner: WorkflowRunner):
        """Test _all_functions_completed returns False when some functions not completed"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.COMPLETED
        func2 = MagicMock(spec=FaaSrFunction)
        func2.status = FunctionStatus.RUNNING

        workflow_runner._functions = {"func1": func1, "func2": func2}

        assert workflow_runner._all_functions_completed() is False

    def test_get_active_functions(self, workflow_runner: WorkflowRunner):
        """Test _get_active_functions returns functions with active loggers"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.logs_complete = False
        func1.status = FunctionStatus.RUNNING

        func2 = MagicMock(spec=FaaSrFunction)
        func2.logs_complete = True
        func2.status = FunctionStatus.RUNNING

        func3 = MagicMock(spec=FaaSrFunction)
        func3.logs_complete = False
        func3.status = FunctionStatus.COMPLETED  # Final state

        workflow_runner._functions = {
            "func1": func1,
            "func2": func2,
            "func3": func3,
        }

        active = workflow_runner._get_active_functions()
        assert len(active) == 1
        assert active[0] == func1

    def test_cascade_failure(self, workflow_runner: WorkflowRunner):
        """Test _cascade_failure sets all non-final functions to SKIPPED"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.FAILED

        func2 = MagicMock(spec=FaaSrFunction)
        func2.status = FunctionStatus.PENDING

        func3 = MagicMock(spec=FaaSrFunction)
        func3.status = FunctionStatus.COMPLETED

        workflow_runner._functions = {
            "func1": func1,
            "func2": func2,
            "func3": func3,
        }

        workflow_runner._cascade_failure()

        # func2 should be set to SKIPPED (not final state)
        func2.set_status.assert_called_with(FunctionStatus.SKIPPED)
        # func1 and func3 should not be changed (already final state)
        assert func1.set_status.call_count == 0
        assert func3.set_status.call_count == 0


class TestWorkflowRunnerTimeoutHandling:
    """Tests for WorkflowRunner timeout handling"""

    def test_reset_timer(self, workflow_runner: WorkflowRunner):
        """Test _reset_timer resets the timer"""
        workflow_runner.last_change_time = 100.0
        workflow_runner.seconds_since_last_change = 50.0

        workflow_runner._reset_timer()

        assert workflow_runner.seconds_since_last_change == 0.0
        assert workflow_runner.last_change_time > 0

    def test_increment_timer(self, workflow_runner: WorkflowRunner):
        """Test _increment_timer updates seconds_since_last_change"""
        workflow_runner.last_change_time = time.time() - 5.0

        workflow_runner._increment_timer()

        assert workflow_runner.seconds_since_last_change >= 5.0

    def test_did_timeout_true(self, workflow_runner: WorkflowRunner):
        """Test _did_timeout returns True when timeout exceeded"""
        workflow_runner.timeout = 10
        workflow_runner.seconds_since_last_change = 15.0

        assert workflow_runner._did_timeout() is True

    def test_did_timeout_false(self, workflow_runner: WorkflowRunner):
        """Test _did_timeout returns False when timeout not exceeded"""
        workflow_runner.timeout = 10
        workflow_runner.seconds_since_last_change = 5.0

        assert workflow_runner._did_timeout() is False


class TestWorkflowRunnerMonitoring:
    """Tests for WorkflowRunner monitoring logic"""

    def test_log_status_change_failed(self, workflow_runner: WorkflowRunner):
        """Test _log_status_change logs failure correctly"""
        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func1"
        function.status = FunctionStatus.FAILED

        workflow_runner._log_status_change(function)

        workflow_runner.logger.info.assert_called_with("Function func1 failed")

    @pytest.mark.parametrize(
        ("status", "expected_message"),
        [
            (FunctionStatus.NOT_INVOKED, "Function func1 not invoked"),
            (FunctionStatus.INVOKED, "Function func1 invoked"),
            (FunctionStatus.RUNNING, "Function func1 running"),
            (FunctionStatus.COMPLETED, "Function func1 completed"),
        ],
    )
    def test_log_status_change(
        self, workflow_runner: WorkflowRunner, status, expected_message
    ):
        """Test _log_status_change logs different statuses correctly"""
        function = MagicMock(spec=FaaSrFunction)
        function.function_name = "func1"
        function.status = status

        workflow_runner._log_status_change(function)

        workflow_runner.logger.info.assert_called_with(expected_message)

    def test_monitor_workflow_execution_all_completed(
        self, workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution raises StopMonitoring when all completed"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.COMPLETED
        func1.function_name = "func1"

        workflow_runner._functions = {"func1": func1}
        workflow_runner._prev_statuses = {"func1": FunctionStatus.COMPLETED}

        with patch.object(
            workflow_runner, "_all_functions_completed"
        ) as mock_all_completed:
            mock_all_completed.return_value = True

            with pytest.raises(StopMonitoring, match="All functions completed"):
                workflow_runner._monitor_workflow_execution()

    def test_monitor_workflow_execution_failure_detected(
        self, workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution handles failure detection"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.FAILED
        func1.function_name = "func1"
        func1.logs_complete = True

        workflow_runner._functions = {"func1": func1}
        workflow_runner._prev_statuses = {"func1": FunctionStatus.RUNNING}

        with (
            patch.object(
                workflow_runner, "_all_functions_completed"
            ) as mock_all_completed,
            patch.object(workflow_runner, "_get_active_functions") as mock_get_active,
        ):
            mock_all_completed.return_value = False
            mock_get_active.return_value = []

            workflow_runner._monitor_workflow_execution()

            assert workflow_runner.failure_detected is True
            workflow_runner.logger.info.assert_any_call(
                "Failure detected in function func1. "
                "Waiting for active loggers to complete..."
            )

    def test_monitor_workflow_execution_failure_cascades_when_loggers_complete(
        self, workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution cascades failure when loggers complete"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.FAILED
        func1.function_name = "func1"
        func1.logs_complete = True

        workflow_runner._functions = {"func1": func1}
        workflow_runner._prev_statuses = {"func1": FunctionStatus.RUNNING}
        workflow_runner._set_failure_detected()

        with (
            patch.object(
                workflow_runner, "_all_functions_completed"
            ) as mock_all_completed,
            patch.object(workflow_runner, "_get_active_functions") as mock_get_active,
            patch.object(workflow_runner, "_cascade_failure") as mock_cascade,
        ):
            mock_all_completed.return_value = False
            mock_get_active.return_value = []

            with pytest.raises(
                StopMonitoring,
                match="Failure detected and all active loggers completed",
            ):
                workflow_runner._monitor_workflow_execution()

            mock_cascade.assert_called_once()

    def test_monitor_workflow_execution_waits_for_loggers(
        self, workflow_runner: WorkflowRunner
    ):
        """Test _monitor_workflow_execution waits when loggers are still active"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.FAILED
        func1.function_name = "func1"
        func1.logs_complete = False

        active_func = MagicMock(spec=FaaSrFunction)
        active_func.function_name = "func2"

        workflow_runner._functions = {"func1": func1}
        workflow_runner._prev_statuses = {"func1": FunctionStatus.RUNNING}
        workflow_runner._set_failure_detected()

        with (
            patch.object(
                workflow_runner, "_all_functions_completed"
            ) as mock_all_completed,
            patch.object(workflow_runner, "_get_active_functions") as mock_get_active,
        ):
            mock_all_completed.return_value = False
            mock_get_active.return_value = [active_func]

            # Should not raise StopMonitoring
            workflow_runner._monitor_workflow_execution()

            workflow_runner.logger.debug.assert_called()
            assert "Waiting for loggers to complete" in str(
                workflow_runner.logger.debug.call_args
            )

    def test_finish_monitoring_timeout(self, workflow_runner: WorkflowRunner):
        """Test _finish_monitoring sets TIMEOUT for incomplete functions"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.RUNNING

        func2 = MagicMock(spec=FaaSrFunction)
        func2.status = FunctionStatus.COMPLETED

        workflow_runner._functions = {"func1": func1, "func2": func2}

        workflow_runner._finish_monitoring()

        func1.set_status.assert_called_with(FunctionStatus.TIMEOUT)
        func2.set_status.assert_not_called()

    def test_finish_monitoring_shutdown(self, workflow_runner: WorkflowRunner):
        """Test _finish_monitoring sets SKIPPED for incomplete functions on shutdown"""
        func1 = MagicMock(spec=FaaSrFunction)
        func1.status = FunctionStatus.RUNNING

        workflow_runner._functions = {"func1": func1}
        workflow_runner._set_shutdown_requested()

        workflow_runner._finish_monitoring()

        func1.set_status.assert_called_with(FunctionStatus.SKIPPED)
        workflow_runner.logger.info.assert_any_call(
            "Function func1 skipped due to shutdown"
        )


class TestWorkflowRunnerShutdown:
    """Tests for WorkflowRunner shutdown and cleanup"""

    def test_shutdown_no_thread(self, workflow_runner: WorkflowRunner):
        """Test shutdown returns True when no monitoring thread exists"""
        workflow_runner._monitoring_thread = None

        result = workflow_runner.shutdown()
        assert result is True

    def test_shutdown_thread_not_alive(self, workflow_runner: WorkflowRunner):
        """Test shutdown returns True when thread is not alive"""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        workflow_runner._monitoring_thread = mock_thread

        result = workflow_runner.shutdown()
        assert result is True

    def test_shutdown_graceful(self, workflow_runner: WorkflowRunner):
        """Test shutdown waits for thread to complete gracefully"""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread.join.return_value = None
        workflow_runner._monitoring_thread = mock_thread

        result = workflow_runner.shutdown(timeout=1.0)

        assert result is True
        mock_thread.join.assert_called_once_with(timeout=1.0)
        assert workflow_runner.shutdown_requested is True

    def test_shutdown_timeout(self, workflow_runner: WorkflowRunner):
        """Test shutdown returns False when thread doesn't complete in time"""
        mock_thread = MagicMock()
        mock_thread.is_alive.side_effect = [True, True]  # Still alive after join
        mock_thread.join.return_value = None
        workflow_runner._monitoring_thread = mock_thread

        result = workflow_runner.shutdown(timeout=0.1)

        assert result is False
        workflow_runner.logger.warning.assert_called()

    def test_force_shutdown(self, workflow_runner: WorkflowRunner):
        """Test force_shutdown sets shutdown flags"""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        workflow_runner._monitoring_thread = mock_thread

        workflow_runner.force_shutdown()

        assert workflow_runner.shutdown_requested is True
        assert workflow_runner.monitoring_complete is True
        workflow_runner.logger.warning.assert_called()

    def test_cleanup_graceful(self, workflow_runner: WorkflowRunner):
        """Test cleanup performs graceful shutdown"""
        with patch.object(workflow_runner, "shutdown") as mock_shutdown:
            mock_shutdown.return_value = True

            workflow_runner.cleanup()

            mock_shutdown.assert_called_once()
            workflow_runner.logger.info.assert_any_call("Cleanup completed")

    def test_cleanup_force_on_failure(self, workflow_runner: WorkflowRunner):
        """Test cleanup forces shutdown if graceful shutdown fails"""
        with (
            patch.object(workflow_runner, "shutdown") as mock_shutdown,
            patch.object(workflow_runner, "force_shutdown") as mock_force,
        ):
            mock_shutdown.return_value = False

            workflow_runner.cleanup()

            mock_shutdown.assert_called_once()
            mock_force.assert_called_once()
            workflow_runner.logger.warning.assert_any_call(
                "Graceful shutdown failed, forcing shutdown..."
            )


class TestWorkflowRunnerStart:
    """Tests for WorkflowRunner start method"""

    def test_start_builds_functions(self):
        """Test _start builds functions and starts monitoring thread"""
        with (
            patch("framework.workflow_runner.FaaSrFunction") as mock_function_class,
            patch("threading.Thread") as mock_thread_class,
        ):
            mock_function = MagicMock(spec=FaaSrFunction)
            mock_function.function_name = "func1"
            mock_function.status = FunctionStatus.PENDING
            mock_function_class.return_value = mock_function
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread

            runner = WorkflowRunner(
                faasr_payload=workflow_data(),
                timeout=60,
                check_interval=1,
                stream_logs=False,
            )

            runner._start()

            assert len(runner._functions) > 0
            mock_thread.start.assert_called_once()

    def test_trigger_workflow(self):
        """Test trigger_workflow class method"""
        with (
            patch("framework.workflow_runner.main") as mock_main,
            patch("framework.workflow_runner.FaaSrFunction") as mock_function_class,
            patch("threading.Thread") as mock_thread_class,
        ):
            payload = workflow_data()
            mock_main.return_value = payload
            mock_function = MagicMock(spec=FaaSrFunction)
            mock_function.function_name = "func1"
            mock_function.status = FunctionStatus.PENDING
            mock_function_class.return_value = mock_function
            mock_thread = MagicMock()
            mock_thread_class.return_value = mock_thread

            runner = WorkflowRunner.trigger_workflow(
                timeout=60, check_interval=1, stream_logs=False
            )

            assert runner is not None
            assert isinstance(runner, WorkflowRunner)
            mock_main.assert_called_once_with(testing=True)
            mock_thread.start.assert_called_once()
