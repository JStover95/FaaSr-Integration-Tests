FROM ghcr.io/faasr/github-actions-python:latest

RUN pip uninstall -y FaaSr_py
RUN pip install --no-cache-dir "git+https://github.com/JStover95/FaaSr-Backend-Fork.git@fix/JStover95/HandleImportErrorsOnPythonWalk"

WORKDIR /action

CMD ["python3", "faasr_entry.py"]
