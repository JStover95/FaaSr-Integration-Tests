import pytest

from functions.IntegrationTestWorkflow.utils.enums import (
    CreateInput,
    TestConditional,
    TestPyApi,
    TestRank,
)
from integration_tests.conftest import WorkflowTester


@pytest.fixture(scope="module", autouse=True)
def tester(workflow_file):
    with workflow_file("workflows/TracebackLoggingTestWorkflow.json") as tester:
        yield tester


def test_create_input(tester: WorkflowTester):
    tester.wait_for("create-input")
    tester.assert_function_completed("create-input")
    tester.assert_object_exists("input1.txt")
    tester.assert_content_equals("input1.txt", CreateInput.INPUT_1_CONTENT.value)
    tester.assert_object_exists("input2.txt")
    tester.assert_content_equals("input2.txt", CreateInput.INPUT_2_CONTENT.value)
    tester.assert_object_exists("input3.txt")
    tester.assert_content_equals("input3.txt", CreateInput.INPUT_3_CONTENT.value)
    tester.assert_object_exists("input4.txt")
    tester.assert_content_equals("input4.txt", CreateInput.INPUT_4_CONTENT.value)

    tester.assert_object_does_not_exist("does_not_exist.txt")


def test_py_api(tester: WorkflowTester):
    tester.wait_for("test-py-api")
    tester.assert_function_completed("test-py-api")
    tester.assert_object_does_not_exist("input1.txt")
    tester.assert_object_exists("input2.txt")
    tester.assert_object_exists("input3.txt")
    tester.assert_object_exists("output1-py.txt")
    tester.assert_content_equals("output1-py.txt", TestPyApi.OUTPUT_1_CONTENT.value)
    tester.assert_object_exists("output2-py.txt")
    tester.assert_content_equals("output2-py.txt", TestPyApi.OUTPUT_2_CONTENT.value)

    tester.assert_object_does_not_exist("does_not_exist.txt")


def test_r_api(tester: WorkflowTester):
    tester.wait_for("test-r-api")
    tester.assert_function_completed("test-r-api")
    tester.assert_object_does_not_exist("input4.txt")
    tester.assert_object_exists("input2.txt")
    tester.assert_object_exists("input3.txt")
    tester.assert_object_exists("output1-R.txt")
    tester.assert_content_equals("output1-R.txt", TestPyApi.OUTPUT_1_CONTENT.value)
    tester.assert_object_exists("output2-R.txt")
    tester.assert_content_equals("output2-R.txt", TestPyApi.OUTPUT_2_CONTENT.value)

    tester.assert_object_does_not_exist("does_not_exist.txt")


def sync1(tester: WorkflowTester):
    tester.wait_for("sync1")
    tester.assert_function_completed("sync1")


def test_run_true(tester: WorkflowTester):
    tester.wait_for("test-run-true")
    tester.assert_function_completed("test-run-true")
    tester.assert_object_exists("run_true_output.txt")
    tester.assert_content_equals(
        "run_true_output.txt", TestConditional.RUN_TRUE_CONTENT.value
    )


def test_dontrun_false(tester: WorkflowTester):
    tester.wait_for("test-dontrun-false")
    tester.assert_function_not_invoked("test-dontrun-false")


def test_run_false(tester: WorkflowTester):
    tester.wait_for("test-run-false")
    tester.assert_function_completed("test-run-false")
    tester.assert_object_exists("run_false_output.txt")
    tester.assert_content_equals(
        "run_false_output.txt", TestConditional.RUN_FALSE_CONTENT.value
    )


def test_dontrun_true(tester: WorkflowTester):
    tester.wait_for("test-dontrun-true")
    tester.assert_function_not_invoked("test-dontrun-true")


def test_rank_1(tester: WorkflowTester):
    tester.wait_for("test-rank(1)")
    tester.assert_function_completed("test-rank(1)")
    tester.assert_object_exists("rank_files/rank1.txt")
    tester.assert_content_equals("rank_files/rank1.txt", f"{TestRank}1")


def test_rank_2(tester: WorkflowTester):
    tester.wait_for("test-rank(2)")
    tester.assert_function_completed("test-rank(2)")
    tester.assert_object_exists("rank_files/rank2.txt")
    tester.assert_content_equals("rank_files/rank2.txt", f"{TestRank}2")


def test_rank_3(tester: WorkflowTester):
    tester.wait_for("test-rank(3)")
    tester.assert_function_completed("test-rank(3)")
    tester.assert_object_exists("rank_files/rank3.txt")
    tester.assert_content_equals("rank_files/rank3.txt", f"{TestRank}3")


def test_rank_4(tester: WorkflowTester):
    tester.wait_for("test-rank(4)")
    tester.assert_function_completed("test-rank(4)")
    tester.assert_object_exists("rank_files/rank4.txt")
    tester.assert_content_equals("rank_files/rank4.txt", f"{TestRank}4")


def test_rank_5(tester: WorkflowTester):
    tester.wait_for("test-rank(5)")
    tester.assert_function_completed("test-rank(5)")
    tester.assert_object_exists("rank_files/rank5.txt")
    tester.assert_content_equals("rank_files/rank5.txt", f"{TestRank}5")


def sync2(tester: WorkflowTester):
    tester.wait_for("sync2")
    tester.assert_function_completed("sync2")


def fail_py(tester: WorkflowTester):
    tester.wait_for("fail-py", should_fail=True)
    tester.assert_function_failed("fail-py")

    # The full stack trace should be logged
    tester.assert_logs_contain("fail-py", "Exception: inside_exception")
    tester.assert_logs_contain("fail-py", "Exception: outside_exception")


def fail_r(tester: WorkflowTester):
    tester.wait_for("fail-r", should_fail=True)
    tester.assert_function_failed("fail-r")

    # The full stack trace should be logged
    tester.assert_logs_contain("fail-r", 'stop("inside_exception")')
    tester.assert_logs_contain("fail-r", 'stop("outside_exception")')
