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
        assert tester._current_invocation == 1
        assert tester._is_complete is False

    def test_wait_for_all_raises_on_failure(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester()
        tester.runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.FAILED,
        }

        with pytest.raises(RuntimeError, match="Function func-a failed"):
            tester._wait_for_all()

        assert tester._is_complete is False

    def test_wait_for_advances_to_requested_invocation(self, mock_trigger):
        first_runner = MagicMock()
        second_runner = MagicMock()
        mock_trigger.side_effect = [first_runner, second_runner]

        tester = WorkflowTester(num_invocations=2)
        first_runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.COMPLETED,
        }
        second_runner.get_function_statuses.return_value = {
            "func-b": FunctionStatus.COMPLETED,
        }

        tester.wait_for("func-a", invocation_num=1)
        tester.wait_for("func-b", invocation_num=2)

        assert tester._current_invocation == 2
        assert mock_trigger.call_count == 2
        first_runner.shutdown.assert_called_once()

    def test_wait_for_requires_invocation_num_when_configured(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester(num_invocations=2)

        with pytest.raises(ValueError, match="invocation_num is required"):
            tester.wait_for("func-a")

    def test_wait_for_rejects_invocation_num_out_of_range(self, mock_trigger):
        mock_trigger.return_value = MagicMock()
        tester = WorkflowTester(num_invocations=2)

        with pytest.raises(ValueError, match="must be between 1 and 2"):
            tester.wait_for("func-a", invocation_num=3)

    def test_wait_for_rejects_past_invocation(self, mock_trigger):
        first_runner = MagicMock()
        second_runner = MagicMock()
        mock_trigger.side_effect = [first_runner, second_runner]

        tester = WorkflowTester(num_invocations=2)
        first_runner.get_function_statuses.return_value = {
            "func-a": FunctionStatus.COMPLETED,
        }
        second_runner.get_function_statuses.return_value = {
            "func-b": FunctionStatus.COMPLETED,
        }

        tester.wait_for("func-b", invocation_num=2)

        with pytest.raises(RuntimeError, match="already at invocation 2"):
            tester.wait_for("func-a", invocation_num=1)
