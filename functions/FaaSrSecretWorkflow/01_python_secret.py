from FaaSr_py.client.py_client_stubs import (
    faasr_invocation_id,
    faasr_put_file,
    faasr_secret,
)


def python_secret(folder_name: str):
    value = faasr_secret("TEST_SECRET")

    with open("secret_python.txt", "w") as f:
        f.write(value)

    invocation_id = faasr_invocation_id()

    faasr_put_file(
        local_file="secret_python.txt",
        remote_file=f"{invocation_id}/secret_python.txt",
        remote_folder=folder_name,
    )
