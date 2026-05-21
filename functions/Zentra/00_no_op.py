from FaaSr_py.client.py_client_stubs import faasr_log


def no_op():
    """No-op function to allow for multiple GetZentraData actions."""
    faasr_log("No-op function called")
    return
