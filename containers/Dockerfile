FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
RUN apt-get update && apt-get install -y --no-install-recommends strace git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir reportlab==4.4.4 pypdf==6.1.1
RUN mkdir -p /source /sandbox /audit /opt/tsg
COPY worker.py payload.py drop_exec.py reference.py /opt/tsg/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/opt/tsg/worker.py"]
