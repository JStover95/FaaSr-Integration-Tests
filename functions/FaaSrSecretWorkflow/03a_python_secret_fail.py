from FaaSr_py.client.py_client_stubs import faasr_secret


def python_secret_fail():
    faasr_secret("NON_EXISTENT_SECRET")
