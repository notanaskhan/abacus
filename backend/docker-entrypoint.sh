#!/bin/sh
# Picks the process this container runs. The first argument names it; the rest go to it.
#   api                       uvicorn on :8000 (ABACUS_API_PORT overrides), behind the ALB
#   worker [--classes a,b]    Temporal workers for some or all work classes
#   migrate                   alembic upgrade head, as the owner role (ABACUS_MIGRATIONS_DATABASE_URL)
#   bootstrap                 the one-off bootstrap task (Q-01-T20; not built yet)
#   ops <tool> [args]         an operator tool, abacus_tools.<tool> (Q-01-T36, T38, T45)
# Anything else runs as a command, so `docker run IMAGE python -V` works.
set -eu

command_name="${1:-api}"
if [ "$#" -gt 0 ]; then shift; fi

case "$command_name" in
  api)
    # Proxy headers are handled by the app (create_app), only from ABACUS_PROXY_TRUSTED_HOSTS (the
    # load balancer's subnets); uvicorn's own handling, which trusts loopback, is off.
    exec uvicorn --factory abacus.api.app:create_app \
      --host 0.0.0.0 --port "${ABACUS_API_PORT:-8000}" \
      --no-proxy-headers \
      --no-server-header "$@"
    ;;
  worker)
    exec python -m abacus.worker "$@"
    ;;
  migrate)
    exec alembic upgrade head "$@"
    ;;
  bootstrap)
    echo "bootstrap: the bootstrap task is built by Q-01-T20" >&2
    exit 64
    ;;
  ops)
    tool="${1:?ops needs a tool name, e.g. ops tenants}"
    shift
    exec python -m "abacus_tools.${tool}" "$@"
    ;;
  *)
    exec "$command_name" "$@"
    ;;
esac
