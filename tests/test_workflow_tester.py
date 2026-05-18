from unittest.mock import MagicMock, patch

import pytest

from framework.utils.enums import FunctionStatus
from integration_tests.conftest import CHECK_INTERVAL, TIMEOUT, WorkflowTester


@patch("integration_tests.conftest.WorkflowRunner.trigger_workflow")
class TestWorkflowTesterLifecycle:
    def test_init_triggers_workflow_and_stores_invocation_id(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester(test_invocation_id="fixed-id")

        mock_trigger.assert_called_once_with(
            timeout=TIMEOUT,
            check_interval=CHECK_INTERVAL,
            stream_logs=True,
            test_invocation_id="fixed-id",
        )
        assert tester._test_invocation_id == "fixed-id"
        assert tester._is_complete is False

    def test_wait_for_all_sets_complete_on_success(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester()
        tester.runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.COMPLETED,
            "func-b": FunctionStatus.NOT_INVOKED,
        }

        tester.wait_for_all()

        assert tester._is_complete is True

    def test_wait_for_all_raises_on_failure(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester()
        tester.runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.FAILED,
        }

        with pytest.raises(RuntimeError, match="Function func-a failed"):
            tester.wait_for_all()

        assert tester._is_complete is False

    def test_wait_for_all_does_not_throw_when_disabled(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester()
        tester.runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.FAILED,
        }

        tester.wait_for_all(should_throw=False)

        assert tester._is_complete is True

    def test_trigger_workflow_raises_while_run_in_progress(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester()

        with pytest.raises(RuntimeError, match="still in progress"):
            tester.trigger_workflow()

        mock_trigger.assert_called_once()

    def test_retrigger_after_wait_for_all(self, mock_trigger):
        first_runner = MagicMock()
        second_runner = MagicMock()
        mock_trigger.side_effect = [first_runner, second_runner]

        tester = WorkflowTester()
        tester.runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.COMPLETED,
        }
        tester.wait_for_all()

        tester.trigger_workflow()

        assert tester.runner is second_runner
        assert tester._is_complete is False
        first_runner.shutdown.assert_called_once()
        first_runner.cleanup.assert_called_once()
        assert mock_trigger.call_count == 2
