from framework.utils.enums import FunctionStatus
from framework.utils.utils import (
    completed,
    extract_function_name,
    failed,
    get_s3_path,
    has_completed,
    has_final_state,
    has_run,
    invoked,
    not_invoked,
    pending,
    running,
    skipped,
    timed_out,
)


class TestExtractFunctionName:
    """Tests for extract_function_name function"""

    def test_extract_function_name_with_parentheses(self):
        """Test extracting function name from string with parentheses"""
        assert extract_function_name("my_function()") == "my_function"
        assert extract_function_name("test_func(arg1, arg2)") == "test_func"
        assert extract_function_name("foo(bar)") == "foo"

    def test_extract_function_name_without_parentheses(self):
        """Test extracting function name from string without parentheses"""
        assert extract_function_name("my_function") == "my_function"
        assert extract_function_name("test_func") == "test_func"

    def test_extract_function_name_with_nested_parentheses(self):
        """Test extracting function name with nested parentheses"""
        assert extract_function_name("func((nested))") == "func"
        assert extract_function_name("test(a(b))") == "test"


class TestGetS3Path:
    """Tests for get_s3_path function"""

    def test_get_s3_path_with_backslashes(self):
        """Test converting backslashes to forward slashes"""
        assert get_s3_path("path\\to\\file") == "path/to/file"
        assert get_s3_path("bucket\\folder\\object") == "bucket/folder/object"

    def test_get_s3_path_with_forward_slashes(self):
        """Test path already with forward slashes"""
        assert get_s3_path("path/to/file") == "path/to/file"
        assert get_s3_path("bucket/folder/object") == "bucket/folder/object"

    def test_get_s3_path_mixed_slashes(self):
        """Test path with mixed slashes"""
        assert get_s3_path("path\\to/file") == "path/to/file"
        assert get_s3_path("bucket/folder\\object") == "bucket/folder/object"

    def test_get_s3_path_no_slashes(self):
        """Test path with no slashes"""
        assert get_s3_path("filename") == "filename"
        assert get_s3_path("object") == "object"


class TestPending:
    """Tests for pending function"""

    def test_pending_with_pending_status(self):
        """Test pending returns True for PENDING status"""
        assert pending(FunctionStatus.PENDING) is True

    def test_pending_with_other_statuses(self):
        """Test pending returns False for non-PENDING statuses"""
        assert pending(FunctionStatus.INVOKED) is False
        assert pending(FunctionStatus.NOT_INVOKED) is False
        assert pending(FunctionStatus.RUNNING) is False
        assert pending(FunctionStatus.COMPLETED) is False
        assert pending(FunctionStatus.FAILED) is False
        assert pending(FunctionStatus.SKIPPED) is False
        assert pending(FunctionStatus.TIMEOUT) is False


class TestInvoked:
    """Tests for invoked function"""

    def test_invoked_with_invoked_status(self):
        """Test invoked returns True for INVOKED status"""
        assert invoked(FunctionStatus.INVOKED) is True

    def test_invoked_with_other_statuses(self):
        """Test invoked returns False for non-INVOKED statuses"""
        assert invoked(FunctionStatus.PENDING) is False
        assert invoked(FunctionStatus.NOT_INVOKED) is False
        assert invoked(FunctionStatus.RUNNING) is False
        assert invoked(FunctionStatus.COMPLETED) is False
        assert invoked(FunctionStatus.FAILED) is False
        assert invoked(FunctionStatus.SKIPPED) is False
        assert invoked(FunctionStatus.TIMEOUT) is False


class TestNotInvoked:
    """Tests for not_invoked function"""

    def test_not_invoked_with_not_invoked_status(self):
        """Test not_invoked returns True for NOT_INVOKED status"""
        assert not_invoked(FunctionStatus.NOT_INVOKED) is True

    def test_not_invoked_with_other_statuses(self):
        """Test not_invoked returns False for non-NOT_INVOKED statuses"""
        assert not_invoked(FunctionStatus.PENDING) is False
        assert not_invoked(FunctionStatus.INVOKED) is False
        assert not_invoked(FunctionStatus.RUNNING) is False
        assert not_invoked(FunctionStatus.COMPLETED) is False
        assert not_invoked(FunctionStatus.FAILED) is False
        assert not_invoked(FunctionStatus.SKIPPED) is False
        assert not_invoked(FunctionStatus.TIMEOUT) is False


class TestRunning:
    """Tests for running function"""

    def test_running_with_running_status(self):
        """Test running returns True for RUNNING status"""
        assert running(FunctionStatus.RUNNING) is True

    def test_running_with_other_statuses(self):
        """Test running returns False for non-RUNNING statuses"""
        assert running(FunctionStatus.PENDING) is False
        assert running(FunctionStatus.INVOKED) is False
        assert running(FunctionStatus.NOT_INVOKED) is False
        assert running(FunctionStatus.COMPLETED) is False
        assert running(FunctionStatus.FAILED) is False
        assert running(FunctionStatus.SKIPPED) is False
        assert running(FunctionStatus.TIMEOUT) is False


class TestCompleted:
    """Tests for completed function"""

    def test_completed_with_completed_status(self):
        """Test completed returns True for COMPLETED status"""
        assert completed(FunctionStatus.COMPLETED) is True

    def test_completed_with_other_statuses(self):
        """Test completed returns False for non-COMPLETED statuses"""
        assert completed(FunctionStatus.PENDING) is False
        assert completed(FunctionStatus.INVOKED) is False
        assert completed(FunctionStatus.NOT_INVOKED) is False
        assert completed(FunctionStatus.RUNNING) is False
        assert completed(FunctionStatus.FAILED) is False
        assert completed(FunctionStatus.SKIPPED) is False
        assert completed(FunctionStatus.TIMEOUT) is False


class TestFailed:
    """Tests for failed function"""

    def test_failed_with_failed_status(self):
        """Test failed returns True for FAILED status"""
        assert failed(FunctionStatus.FAILED) is True

    def test_failed_with_other_statuses(self):
        """Test failed returns False for non-FAILED statuses"""
        assert failed(FunctionStatus.PENDING) is False
        assert failed(FunctionStatus.INVOKED) is False
        assert failed(FunctionStatus.NOT_INVOKED) is False
        assert failed(FunctionStatus.RUNNING) is False
        assert failed(FunctionStatus.COMPLETED) is False
        assert failed(FunctionStatus.SKIPPED) is False
        assert failed(FunctionStatus.TIMEOUT) is False


class TestSkipped:
    """Tests for skipped function"""

    def test_skipped_with_skipped_status(self):
        """Test skipped returns True for SKIPPED status"""
        assert skipped(FunctionStatus.SKIPPED) is True

    def test_skipped_with_other_statuses(self):
        """Test skipped returns False for non-SKIPPED statuses"""
        assert skipped(FunctionStatus.PENDING) is False
        assert skipped(FunctionStatus.INVOKED) is False
        assert skipped(FunctionStatus.NOT_INVOKED) is False
        assert skipped(FunctionStatus.RUNNING) is False
        assert skipped(FunctionStatus.COMPLETED) is False
        assert skipped(FunctionStatus.FAILED) is False
        assert skipped(FunctionStatus.TIMEOUT) is False


class TestTimedOut:
    """Tests for timed_out function"""

    def test_timed_out_with_timeout_status(self):
        """Test timed_out returns True for TIMEOUT status"""
        assert timed_out(FunctionStatus.TIMEOUT) is True

    def test_timed_out_with_other_statuses(self):
        """Test timed_out returns False for non-TIMEOUT statuses"""
        assert timed_out(FunctionStatus.PENDING) is False
        assert timed_out(FunctionStatus.INVOKED) is False
        assert timed_out(FunctionStatus.NOT_INVOKED) is False
        assert timed_out(FunctionStatus.RUNNING) is False
        assert timed_out(FunctionStatus.COMPLETED) is False
        assert timed_out(FunctionStatus.FAILED) is False
        assert timed_out(FunctionStatus.SKIPPED) is False


class TestHasRun:
    """Tests for has_run function"""

    def test_has_run_with_running_status(self):
        """Test has_run returns True for RUNNING status"""
        assert has_run(FunctionStatus.RUNNING) is True

    def test_has_run_with_completed_status(self):
        """Test has_run returns True for COMPLETED status"""
        assert has_run(FunctionStatus.COMPLETED) is True

    def test_has_run_with_failed_status(self):
        """Test has_run returns True for FAILED status"""
        assert has_run(FunctionStatus.FAILED) is True

    def test_has_run_with_skipped_status(self):
        """Test has_run returns True for SKIPPED status"""
        assert has_run(FunctionStatus.SKIPPED) is True

    def test_has_run_with_timeout_status(self):
        """Test has_run returns True for TIMEOUT status"""
        assert has_run(FunctionStatus.TIMEOUT) is True

    def test_has_run_with_pending_status(self):
        """Test has_run returns False for PENDING status"""
        assert has_run(FunctionStatus.PENDING) is False

    def test_has_run_with_invoked_status(self):
        """Test has_run returns False for INVOKED status"""
        assert has_run(FunctionStatus.INVOKED) is False

    def test_has_run_with_not_invoked_status(self):
        """Test has_run returns False for NOT_INVOKED status"""
        assert has_run(FunctionStatus.NOT_INVOKED) is False


class TestHasCompleted:
    """Tests for has_completed function"""

    def test_has_completed_with_completed_status(self):
        """Test has_completed returns True for COMPLETED status"""
        assert has_completed(FunctionStatus.COMPLETED) is True

    def test_has_completed_with_not_invoked_status(self):
        """Test has_completed returns True for NOT_INVOKED status"""
        assert has_completed(FunctionStatus.NOT_INVOKED) is True

    def test_has_completed_with_other_statuses(self):
        """Test has_completed returns False for other statuses"""
        assert has_completed(FunctionStatus.PENDING) is False
        assert has_completed(FunctionStatus.INVOKED) is False
        assert has_completed(FunctionStatus.RUNNING) is False
        assert has_completed(FunctionStatus.FAILED) is False
        assert has_completed(FunctionStatus.SKIPPED) is False
        assert has_completed(FunctionStatus.TIMEOUT) is False


class TestHasFinalState:
    """Tests for has_final_state function"""

    def test_has_final_state_with_completed_status(self):
        """Test has_final_state returns True for COMPLETED status"""
        assert has_final_state(FunctionStatus.COMPLETED) is True

    def test_has_final_state_with_not_invoked_status(self):
        """Test has_final_state returns True for NOT_INVOKED status"""
        assert has_final_state(FunctionStatus.NOT_INVOKED) is True

    def test_has_final_state_with_failed_status(self):
        """Test has_final_state returns True for FAILED status"""
        assert has_final_state(FunctionStatus.FAILED) is True

    def test_has_final_state_with_skipped_status(self):
        """Test has_final_state returns True for SKIPPED status"""
        assert has_final_state(FunctionStatus.SKIPPED) is True

    def test_has_final_state_with_timeout_status(self):
        """Test has_final_state returns True for TIMEOUT status"""
        assert has_final_state(FunctionStatus.TIMEOUT) is True

    def test_has_final_state_with_non_final_statuses(self):
        """Test has_final_state returns False for non-final statuses"""
        assert has_final_state(FunctionStatus.PENDING) is False
        assert has_final_state(FunctionStatus.INVOKED) is False
        assert has_final_state(FunctionStatus.RUNNING) is False
