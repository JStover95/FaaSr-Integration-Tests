FROM ubuntu:22.04 AS builder

RUN apt-get update && apt-get install -y git
WORKDIR /tmp
RUN git clone -b feature/JStover95/pulumi-secret-store https://github.com/JStover95/FaaSr-Docker.git

FROM faasr/openwhisk-python:latest AS base

COPY --from=builder /tmp/FaaSr-Docker/faas_specific/faasr_entry.py /action/faasr_entry.py

RUN pip uninstall -y FaaSr_py
RUN pip install --no-cache-dir "git+https://github.com/JStover95/FaaSr-Backend-Fork.git@feature/JStover95/pulumi-secret-store"
RUN pip install pulumi_esc_sdk

WORKDIR /action

CMD ["python3", "faasr_entry.py"]
