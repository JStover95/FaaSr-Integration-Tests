FROM faasr/openwhisk-python:latest

RUN pip uninstall -y FaaSr_py
RUN pip install --no-cache-dir "git+https://github.com/JStover95/FaaSr-Backend-Fork.git@feature/JStover95/ow-pulumi"

WORKDIR /action

CMD ["python3", "faasr_entry.py"]
