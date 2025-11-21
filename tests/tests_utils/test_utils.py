import pytest

from framework.utils.enums import FunctionStatus
from framework.utils.utils import (
    completed,
    extract_function_name,
    failed,
    get_s3_path,
    has_completed,
    has_final_state,
    has_run,
    not_invoked,
    pending,
    running,
    skipped,
    timed_out,
)


class TestExtractFunctionName:
    """Tests for extract_function_name function"""

    @pytest.mark.parametrize(
        ("function_name", "expected_name"),
        [
            ("my_function()", "my_function"),
            ("test_func(arg1, arg2)", "test_func"),
            ("foo(bar)", "foo"),
        ],
    )
    def test_extract_function_name_with_parentheses(
        self,
        function_name: str,
        expected_name: str,
    ):
        """Test extracting function name from string with parentheses"""
        assert extract_function_name(function_name) == expected_name

    @pytest.mark.parametrize(
        ("function_name", "expected_name"),
        [
            ("my_function", "my_function"),
            ("test_func", "test_func"),
        ],
    )
    def test_extract_function_name_without_parentheses(
        self,
        function_name: str,
        expected_name: str,
    ):
        """Test extracting function name from string without parentheses"""
        assert extract_function_name(function_name) == expected_name

    @pytest.mark.parametrize(
        ("function_name", "expected_name"),
        [
            ("my_function(nested)", "my_function"),
            ("test_func(a(b))", "test_func"),
        ],
    )
    def test_extract_function_name_with_nested_parentheses(
        self,
        function_name: str,
        expected_name: str,
    ):
        """Test extracting function name with nested parentheses"""
        assert extract_function_name(function_name) == expected_name


class TestGetS3Path:
    """Tests for get_s3_path function"""

    @pytest.mark.parametrize(
        ("path", "expected_path"),
        [
            ("path\\to\\file", "path/to/file"),
            ("bucket\\folder\\object", "bucket/folder/object"),
        ],
    )
    def test_get_s3_path_with_backslashes(self, path: str, expected_path: str):
        """Test converting backslashes to forward slashes"""
        assert get_s3_path(path) == expected_path

    @pytest.mark.parametrize(
        ("path", "expected_path"),
        [
            ("path/to/file", "path/to/file"),
            ("bucket/folder/object", "bucket/folder/object"),
        ],
    )
    def test_get_s3_path_with_forward_slashes(self, path: str, expected_path: str):
        """Test path already with forward slashes"""
        assert get_s3_path(path) == expected_path

    @pytest.mark.parametrize(
        ("path", "expected_path"),
        [
            ("path\\to/file", "path/to/file"),
            ("bucket/folder\\object", "bucket/folder/object"),
        ],
    )
    def test_get_s3_path_mixed_slashes(self, path: str, expected_path: str):
        """Test path with mixed slashes"""
        assert get_s3_path(path) == expected_path

    @pytest.mark.parametrize(
        ("path", "expected_path"),
        [
            ("path", "path"),
            ("bucket/folder/object", "bucket/folder/object"),
        ],
    )
    def test_get_s3_path_no_slashes(self, path: str, expected_path: str):
        """Test path with no slashes"""
        assert get_s3_path(path) == expected_path


class TestStatusFunctions:
    """Tests for status functions"""

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.PENDING, True),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.COMPLETED, False),
            (FunctionStatus.FAILED, False),
            (FunctionStatus.SKIPPED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_pending_with_pending_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert pending(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.NOT_INVOKED, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.COMPLETED, False),
            (FunctionStatus.FAILED, False),
            (FunctionStatus.SKIPPED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_not_invoked_with_not_invoked_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert not_invoked(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.RUNNING, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.COMPLETED, False),
            (FunctionStatus.FAILED, False),
            (FunctionStatus.SKIPPED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_running_with_running_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert running(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.COMPLETED, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.SKIPPED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_completed_with_completed_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert completed(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.FAILED, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.SKIPPED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_failed_with_failed_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert failed(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.SKIPPED, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.COMPLETED, False),
            (FunctionStatus.FAILED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_skipped_with_skipped_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert skipped(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.TIMEOUT, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.COMPLETED, False),
            (FunctionStatus.FAILED, False),
            (FunctionStatus.SKIPPED, False),
        ],
    )
    def test_timed_out_with_timeout_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert timed_out(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.RUNNING, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, False),
            (FunctionStatus.COMPLETED, True),
            (FunctionStatus.FAILED, True),
            (FunctionStatus.SKIPPED, True),
        ],
    )
    def test_has_run_with_running_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert has_run(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.COMPLETED, True),
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.NOT_INVOKED, True),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.FAILED, False),
            (FunctionStatus.SKIPPED, False),
            (FunctionStatus.TIMEOUT, False),
        ],
    )
    def test_has_completed_with_completed_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert has_completed(status) == expected_result

    @pytest.mark.parametrize(
        ("status", "expected_result"),
        [
            (FunctionStatus.PENDING, False),
            (FunctionStatus.INVOKED, False),
            (FunctionStatus.RUNNING, False),
            (FunctionStatus.COMPLETED, True),
            (FunctionStatus.NOT_INVOKED, True),
            (FunctionStatus.FAILED, True),
            (FunctionStatus.SKIPPED, True),
            (FunctionStatus.TIMEOUT, True),
        ],
    )
    def test_has_final_state_with_not_invoked_status(
        self, status: FunctionStatus, expected_result: bool
    ):
        assert has_final_state(status) == expected_result
