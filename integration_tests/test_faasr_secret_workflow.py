import pytest

from integration_tests.conftest import WorkflowTester


@pytest.fixture(scope="module", autouse=True)
def tester(workflow_file):
    with workflow_file("workflows/FaaSrSecretWorkflow.json") as base_tester:
        yield base_tester


def test_python_secret(tester: WorkflowTester):
    tester.wait_for("python-secret")
    tester.assert_function_completed("python-secret")
    tester.assert_object_exists("secret_python.txt")
    tester.assert_content_equals("secret_python.txt", "TEST_SECRET_VALUE")


def test_r_secret(tester: WorkflowTester):
    tester.wait_for("r-secret")
    tester.assert_function_completed("r-secret")
    tester.assert_object_exists("secret_r.txt")
    tester.assert_content_equals("secret_r.txt", "TEST_SECRET_VALUE")


def test_python_secret_fail(tester: WorkflowTester):
    tester.wait_for("python-secret-fail", should_fail=True)
    tester.assert_function_failed("python-secret-fail")
    tester.assert_logs_contain(
        "python-secret-fail",
        "faasr_secret: Secret 'NON_EXISTENT_SECRET' not found in environment variables",
    )


def test_r_secret_fail(tester: WorkflowTester):
    tester.wait_for("r-secret-fail", should_fail=True)
    tester.assert_function_failed("r-secret-fail")
    tester.assert_logs_contain(
        "r-secret-fail",
        "faasr_secret: Secret 'NON_EXISTENT_SECRET' not found in environment variables",
    )
