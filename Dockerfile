# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.8 and 7.4; the lecturer built and ran it with Docker Compose
# Dependencies are installed at build time; the running container needs no network (Tier B has no egress).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SVCDESK_DB=/data/svcdesk.db

WORKDIR /app

# The whole repository (minus .dockerignore) so that the tests service can also run the repository self-checks.
COPY . /app

RUN pip install ".[tests]" \
    && useradd --system --uid 10001 --create-home svcdesk \
    && mkdir -p /data \
    && chown svcdesk:svcdesk /data

USER svcdesk
EXPOSE 8080

CMD ["uvicorn", "svcdesk.main:app", "--host", "0.0.0.0", "--port", "8080"]
