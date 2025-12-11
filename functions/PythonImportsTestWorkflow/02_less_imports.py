from FaaSr_py.client.py_client_stubs import faasr_log


def less_imports():
    """
    This function is imported second during the directory walk, and should fail when
    `01_more_imports.py` is imported.
    """
    faasr_log("This function should fail due to the missing packages.")
