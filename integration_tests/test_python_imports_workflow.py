import pytest

from integration_tests.conftest import WorkflowTester


@pytest.fixture(scope="module", autouse=True)
def pass_tester(workflow_file):
    with workflow_file("workflows/PythonImportsPassWorkflow.json") as tester:
        yield tester


@pytest.fixture(scope="module", autouse=True)
def fail_tester(workflow_file):
    with workflow_file("workflows/PythonImportsFailWorkflow.json") as tester:
        yield tester


def test_more_imports(pass_tester: WorkflowTester, fail_tester: WorkflowTester):
    # The more imports function should always complete successfully
    pass_tester.wait_for("more-imports")
    pass_tester.assert_function_completed("more-imports")
    fail_tester.wait_for("more-imports")
    fail_tester.assert_function_completed("more-imports")


def test_less_imports(pass_tester: WorkflowTester, fail_tester: WorkflowTester):
    # The failing workflow should fail due to an import error
    fail_tester.wait_for("less-imports", should_fail=True)
    fail_tester.assert_function_failed("less-imports")
    fail_tester.assert_logs_contain(
        "less-imports",
        "Python file 01_more_imports.py has following source error: No module named 'numpy'",
    )

    # The passing workflow should complete successfully
    pass_tester.wait_for("less-imports")
    pass_tester.assert_function_completed("less-imports")
