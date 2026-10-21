# syntax=docker/dockerfile:1.7
# The backend image (ADR-088: built once, promoted by digest; Q-01-T06). PROTECTED.
#
# One image runs every backend process; the entrypoint picks which (docker-entrypoint.sh):
#   api | worker [--classes ...] | migrate | bootstrap | ops <tool> [args]
# Build with this directory as the context:  docker build -t abacus-backend backend
#
# The runtime stage is the default (last) target. It runs as a non-root user on a read-only root
# filesystem: nothing is written outside /tmp (a tmpfs in the task definition).
# `--target test` adds the dev group and the tests, to run the Linux-only checks (the isolation
# child limits) inside the image's own base:
#   docker build --target test -t abacus-backend-test backend

# The base image is pinned by digest (the multi-arch index), never by tag alone. Refresh it with
# the weekly base rebuild (Q-01-T11): docker buildx imagetools inspect python:3.12-slim
ARG PYTHON_IMAGE=python:3.12-slim@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2

FROM ${PYTHON_IMAGE} AS builder
# uv builds the environment from uv.lock and is not shipped: it stays in this stage.
ARG UV_VERSION=0.12.3
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
WORKDIR /app
# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --locked --no-dev

FROM builder AS test
RUN uv sync --locked
COPY tests ./tests
ENV PATH=/app/.venv/bin:$PATH
ENTRYPOINT []
CMD ["pytest", "tests/unit", "-q"]

FROM ${PYTHON_IMAGE} AS runtime
# A fixed non-root identity with no login shell and no home directory.
RUN groupadd --system --gid 10001 abacus \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
       --home-dir /nonexistent --shell /usr/sbin/nologin abacus
# Owned by root and read-only to the app user: the process can't rewrite its own code.
COPY --from=builder --chown=root:root /app /app
COPY --chown=root:root --chmod=0755 docker-entrypoint.sh /usr/local/bin/abacus-entrypoint
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    TMPDIR=/tmp
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/abacus-entrypoint"]
CMD ["api"]
