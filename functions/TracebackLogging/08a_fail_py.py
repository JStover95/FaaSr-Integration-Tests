from .utils.enums import TracebackLoggingTestValue


def fail_py():
    try:
        raise Exception(TracebackLoggingTestValue.INSIDE_EXCEPTION.value)
    except Exception as e:
        raise Exception(TracebackLoggingTestValue.OUTSIDE_EXCEPTION.value) from e
