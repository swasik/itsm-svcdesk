# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file for Lab 1; Claude Code added the Lab 5 triage (digest pin, apt-get upgrade, no pip at run time)
# Dependencies are installed at build time; the running container needs no network (Tier B has no egress).
# Lab 5 triage (TRIAGE.md): the base pinned by digest (python:3.13-slim as of 2026-10-11), Debian's fixes applied with
# apt-get upgrade, and pip removed from the runtime image once the service is installed - pip vendors msgpack,
# setuptools (pkg_resources) and urllib3 at versions with fixable HIGH advisories, and nothing calls pip at run time.
FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SVCDESK_DB=/data/svcdesk.db

WORKDIR /app

# The whole repository (minus .dockerignore) so that the tests service can also run the repository self-checks.
COPY . /app

RUN pip install ".[tests]" \
    && pip uninstall -y pip \
    && useradd --system --uid 10001 --create-home svcdesk \
    && mkdir -p /data \
    && chown svcdesk:svcdesk /data

USER svcdesk
EXPOSE 8080

CMD ["uvicorn", "svcdesk.main:app", "--host", "0.0.0.0", "--port", "8080"]
