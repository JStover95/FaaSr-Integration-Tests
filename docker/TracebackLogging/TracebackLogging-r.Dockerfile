FROM ghcr.io/faasr/github-actions-r:latest

RUN pip install --no-cache-dir "git+https://github.com/JStover95/FaaSr-Backend-Fork.git@feature/JStover95/traceback-logging"

WORKDIR /action

CMD ["python3", "faasr_entry.py"]
