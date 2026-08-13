#!/usr/bin/env bash
# Compatibility entry point. Production systemd calls the same venv Python
# implementation directly so there is only one backup protocol.
set -Eeuo pipefail

ASTRA_HOME="${ASTRA_HOME:-/opt/astra}"
exec "$ASTRA_HOME/venv/bin/python" "$ASTRA_HOME/infra/backup/create_backup.py" \
    --project-root "$ASTRA_HOME"
