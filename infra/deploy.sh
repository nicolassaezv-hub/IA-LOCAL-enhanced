#!/usr/bin/env bash
# ASTRA production deployment for Ubuntu 24.04 / Python 3.12 / ARM64 or x86_64.
set -Eeuo pipefail

ASTRA_HOME="${ASTRA_HOME:-/opt/astra}"
ASTRA_USER="${ASTRA_USER:-astra}"
ASTRA_GROUP="${ASTRA_GROUP:-astra}"
ASTRA_ENV_FILE="${ASTRA_ENV_FILE:-/etc/astra/astra.env}"
ASTRA_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_SYSTEM_PACKAGES=false
ALLOW_PUBLIC_HTTP=false
PROBE_PROVIDERS=false
ASTRA_BACKUP_DIR=""

for argument in "$@"; do
    case "$argument" in
        --install-system-packages) INSTALL_SYSTEM_PACKAGES=true ;;
        --allow-public-http) ALLOW_PUBLIC_HTTP=true ;;
        --probe-providers) PROBE_PROVIDERS=true ;;
        --help)
            echo "Usage: infra/deploy.sh [--install-system-packages] [--allow-public-http] [--probe-providers]"
            exit 0
            ;;
        *) echo "Unknown argument: $argument" >&2; exit 64 ;;
    esac
done

declare -a PHASE_ORDER=()
declare -A PHASE_STATUS=()
CURRENT_PHASE=""

record_phase() {
    local name="$1" status="$2"
    PHASE_ORDER+=("$name")
    PHASE_STATUS["$name"]="$status"
    printf '%-22s %s\n' "$name" "$status"
}

print_summary() {
    echo
    echo "Deployment phases:"
    local name
    for name in "${PHASE_ORDER[@]}"; do
        printf '  %-20s %s\n' "$name" "${PHASE_STATUS[$name]}"
    done
}

on_unexpected_error() {
    local exit_code=$?
    if [[ -n "$CURRENT_PHASE" && "${PHASE_STATUS[$CURRENT_PHASE]:-}" != "FAIL" ]]; then
        record_phase "$CURRENT_PHASE" "FAIL"
    fi
    print_summary
    echo "DEPLOYMENT RESULT: FAILED" >&2
    exit "$exit_code"
}
trap on_unexpected_error ERR

run_phase() {
    local name="$1"
    shift
    CURRENT_PHASE="$name"
    echo
    echo "==> $name"
    "$@"
    record_phase "$name" "PASS"
    CURRENT_PHASE=""
}

run_privileged() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

precheck() {
    [[ "$(uname -s)" == "Linux" ]] || { echo "Linux is required" >&2; return 1; }
    [[ -r /etc/os-release ]] || { echo "/etc/os-release is required" >&2; return 1; }
    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] || {
        echo "Unsupported distribution: Ubuntu 24.04 is required" >&2
        return 1
    }
    [[ "$ASTRA_HOME" == /* && "$ASTRA_ENV_FILE" == /* ]] || {
        echo "ASTRA_HOME and ASTRA_ENV_FILE must be absolute paths" >&2
        return 1
    }
    [[ "$ASTRA_HOME" =~ ^/[A-Za-z0-9._/-]+$ && "$ASTRA_ENV_FILE" =~ ^/[A-Za-z0-9._/-]+$ ]] || {
        echo "ASTRA_HOME or ASTRA_ENV_FILE contains unsupported characters" >&2
        return 1
    }
    [[ "/$ASTRA_HOME/" != *"/../"* && "/$ASTRA_ENV_FILE/" != *"/../"* ]] || {
        echo "ASTRA_HOME and ASTRA_ENV_FILE must not contain parent traversal" >&2
        return 1
    }
    [[ "$ASTRA_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ && "$ASTRA_GROUP" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || {
        echo "Invalid ASTRA service user or group name" >&2
        return 1
    }
    [[ "$ASTRA_USER" != "root" && "$ASTRA_GROUP" != "root" ]] || {
        echo "The ASTRA service identity must not be root" >&2
        return 1
    }
    command -v python3.12 >/dev/null || {
        echo "python3.12 is required; install it explicitly before deployment" >&2
        return 1
    }
    [[ -d /run/systemd/system ]] || {
        echo "systemd is not running; refusing to install competing cron supervision" >&2
        return 1
    }
    [[ -f "$ASTRA_REPO/workspace/server.py" && -f "$ASTRA_REPO/requirements.txt" ]] || {
        echo "Invalid ASTRA project directory: $ASTRA_REPO" >&2
        return 1
    }
    python3.12 "$ASTRA_REPO/infra/deployment_contract.py" precheck \
        --project-root "$ASTRA_REPO" \
        --service-user "$ASTRA_USER" \
        --install-root "$ASTRA_HOME" \
        --environment-file "$ASTRA_ENV_FILE"
    if [[ "$EUID" -ne 0 ]]; then
        command -v sudo >/dev/null || { echo "sudo is required for installation" >&2; return 1; }
        sudo -v
    fi
}

system_dependencies() {
    local packages=(python3.12 python3.12-venv python3-pip rsync curl)
    local missing=() package
    for package in "${packages[@]}"; do
        dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed' || missing+=("$package")
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
        return 0
    fi
    if [[ "$INSTALL_SYSTEM_PACKAGES" != true ]]; then
        echo "Missing required OS packages: ${missing[*]}" >&2
        echo "Rerun with --install-system-packages to authorize apt installation." >&2
        return 1
    fi
    run_privileged apt-get update
    run_privileged apt-get install -y --no-install-recommends "${missing[@]}"
}

configure_service_environment() {
    run_privileged install -d -m 0750 -o root -g "$ASTRA_GROUP" "$(dirname "$ASTRA_ENV_FILE")"
    if [[ ! -e "$ASTRA_ENV_FILE" ]]; then
        local generated
        generated="$(mktemp)"
        sed -e "s|/opt/astra|$ASTRA_HOME|g" \
            -e "s|/etc/astra/astra.env|$ASTRA_ENV_FILE|g" \
            "$ASTRA_REPO/infra/config/astra.env.example" > "$generated"
        run_privileged install -m 0640 -o root -g "$ASTRA_GROUP" "$generated" "$ASTRA_ENV_FILE"
        rm -f -- "$generated"
        echo "Created $ASTRA_ENV_FILE without secrets; set ASTRA_API_KEY and rerun." >&2
    else
        run_privileged chown root:"$ASTRA_GROUP" "$ASTRA_ENV_FILE"
        run_privileged chmod 0640 "$ASTRA_ENV_FILE"
    fi

    local config_arguments=(validate-config --environment-file "$ASTRA_ENV_FILE" --project-root "$ASTRA_HOME")
    [[ "$ALLOW_PUBLIC_HTTP" == true ]] && config_arguments+=(--allow-public-http)
    run_privileged python3.12 "$ASTRA_REPO/infra/deployment_contract.py" "${config_arguments[@]}"

    ASTRA_BACKUP_DIR="$(run_privileged python3.12 - "$ASTRA_ENV_FILE" "$ASTRA_REPO" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[2])
from infra.deployment_contract import load_environment_file

print(load_environment_file(Path(sys.argv[1])).get("ASTRA_BACKUP_ROOT", "/var/backups/astra"))
PY
)"
    [[ "$ASTRA_BACKUP_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || {
        echo "ASTRA_BACKUP_ROOT contains unsupported characters" >&2
        return 1
    }
    run_privileged install -d -m 0750 -o "$ASTRA_USER" -g "$ASTRA_GROUP" "$ASTRA_BACKUP_DIR"
}

create_service_identity() {
    if ! getent group "$ASTRA_GROUP" >/dev/null; then
        run_privileged groupadd --system "$ASTRA_GROUP"
    fi
    if ! id "$ASTRA_USER" >/dev/null 2>&1; then
        run_privileged useradd --system --gid "$ASTRA_GROUP" \
            --home-dir /nonexistent --shell /usr/sbin/nologin "$ASTRA_USER"
    fi
    [[ "$(id -gn "$ASTRA_USER")" == "$ASTRA_GROUP" ]] || {
        echo "Existing service user $ASTRA_USER does not use group $ASTRA_GROUP" >&2
        return 1
    }
}

install_filesystem() {
    create_service_identity
    run_privileged install -d -m 0755 -o root -g root "$ASTRA_HOME"
    if [[ "$ASTRA_REPO" != "$ASTRA_HOME" ]]; then
        run_privileged rsync -a --chown=root:root \
            --exclude='/.git/' --exclude='*.env' \
            --exclude='*.key' --exclude='*.pem' --exclude='/venv/' \
            --exclude='/memory_db/' --exclude='/models/' --exclude='/CSVs/' \
            --exclude='/forex/data/*.csv' --exclude='/workspace/uploads/' \
            --exclude='/reports/' --exclude='/logs/' --exclude='/lab_reports/' \
            --exclude='/data/forex_analytics/' \
            "$ASTRA_REPO/" "$ASTRA_HOME/"
        if [[ -d "$ASTRA_REPO/models/forex/params" ]]; then
            run_privileged install -d -m 0750 "$ASTRA_HOME/models/forex/params"
            run_privileged rsync -a "$ASTRA_REPO/models/forex/params/" "$ASTRA_HOME/models/forex/params/"
        fi
    fi

    local runtime_directories=(
        memory_db models CSVs CSVs/H1 CSVs/H4 CSVs/D1
        workspace/uploads reports reports/deployment logs data data/forex_analytics
        lab_reports prediction/reports
    )
    local relative
    for relative in "${runtime_directories[@]}"; do
        run_privileged install -d -m 0750 -o "$ASTRA_USER" -g "$ASTRA_GROUP" "$ASTRA_HOME/$relative"
    done
    run_privileged install -d -m 0750 -o "$ASTRA_USER" -g "$ASTRA_GROUP" /var/log/astra

    run_privileged chmod -R go-w "$ASTRA_HOME"
    for relative in "${runtime_directories[@]}"; do
        run_privileged chown -R "$ASTRA_USER:$ASTRA_GROUP" "$ASTRA_HOME/$relative"
        run_privileged chmod 0750 "$ASTRA_HOME/$relative"
    done
    run_privileged chown -R "$ASTRA_USER:$ASTRA_GROUP" /var/log/astra
}

install_python_environment() {
    if [[ ! -x "$ASTRA_HOME/venv/bin/python" ]]; then
        run_privileged python3.12 -m venv "$ASTRA_HOME/venv"
    fi
    local version
    version="$("$ASTRA_HOME/venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    [[ "$version" == "3.12" ]] || {
        echo "Existing venv uses Python $version; Python 3.12 is required" >&2
        return 1
    }
    run_privileged "$ASTRA_HOME/venv/bin/python" -m pip install \
        --requirement "$ASTRA_HOME/requirements.txt" \
        --constraint "$ASTRA_HOME/constraints-py312.txt" \
        --prefer-binary
    run_privileged chown -R root:root "$ASTRA_HOME/venv"
    run_privileged chmod -R go-w "$ASTRA_HOME/venv"
    run_privileged "$ASTRA_HOME/venv/bin/python" -m pip check
}

install_systemd() {
    local source destination generated unit
    [[ -n "$ASTRA_BACKUP_DIR" ]] || {
        echo "Validated ASTRA_BACKUP_ROOT is unavailable" >&2
        return 1
    }
    for source in "$ASTRA_HOME"/infra/systemd/*.service "$ASTRA_HOME"/infra/systemd/*.timer; do
        unit="$(basename "$source")"
        destination="/etc/systemd/system/$unit"
        generated="$(mktemp)"
        sed -e "s|/opt/astra|$ASTRA_HOME|g" \
            -e "s|/etc/astra/astra.env|$ASTRA_ENV_FILE|g" \
            -e "s|^User=astra$|User=$ASTRA_USER|" \
            -e "s|^Group=astra$|Group=$ASTRA_GROUP|" \
            -e "s|/var/backups/astra|$ASTRA_BACKUP_DIR|g" "$source" > "$generated"
        local pending_destination="${destination}.astra-new.$$"
        run_privileged install -m 0644 -o root -g root "$generated" "$pending_destination"
        run_privileged mv -f -- "$pending_destination" "$destination"
        rm -f -- "$generated"
    done
    generated="$(mktemp)"
    sed -e "s|su astra astra|su $ASTRA_USER $ASTRA_GROUP|" \
        -e "s|create 0640 astra astra|create 0640 $ASTRA_USER $ASTRA_GROUP|" \
        "$ASTRA_HOME/infra/logging/logrotate.conf" > "$generated"
    local pending_logrotate="/etc/logrotate.d/astra.astra-new.$$"
    run_privileged install -m 0644 -o root -g root "$generated" "$pending_logrotate"
    run_privileged mv -f -- "$pending_logrotate" /etc/logrotate.d/astra
    rm -f -- "$generated"
    run_privileged systemctl daemon-reload
    run_privileged systemctl enable astra-api.service astra-monitor.service \
        astra-scheduler-h1.timer astra-scheduler-h4.timer astra-scheduler-d1.timer \
        astra-backup.timer
    if command -v systemd-analyze >/dev/null; then
        run_privileged systemd-analyze verify \
            /etc/systemd/system/astra-api.service \
            /etc/systemd/system/astra-monitor.service \
            /etc/systemd/system/astra-scheduler@.service \
            /etc/systemd/system/astra-backup.service
    fi
}

start_and_verify() {
    run_privileged systemctl restart astra-api.service astra-monitor.service
    run_privileged systemctl start astra-scheduler-h1.timer astra-scheduler-h4.timer \
        astra-scheduler-d1.timer astra-backup.timer
    run_privileged systemctl is-active --quiet astra-api.service

    run_privileged runuser --user "$ASTRA_USER" -- \
        "$ASTRA_HOME/venv/bin/python" - "$ASTRA_ENV_FILE" "$ASTRA_HOME" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, sys.argv[2])
from infra.deployment_contract import load_environment_file

values = load_environment_file(Path(sys.argv[1]))
port = int(values.get("ASTRA_PORT", "8000"))
url = f"http://127.0.0.1:{port}/health"
for _ in range(30):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.load(response)
            if response.status == 200 and payload == {"status": "ok"}:
                raise SystemExit(0)
    except (OSError, ValueError, urllib.error.URLError):
        pass
    time.sleep(2)
print("ASTRA process is active but the canonical health response was not observed", file=sys.stderr)
raise SystemExit(1)
PY
}

run_readiness() {
    local arguments=(readiness --project-root "$ASTRA_HOME" --environment-file "$ASTRA_ENV_FILE")
    [[ "$PROBE_PROVIDERS" == true ]] && arguments+=(--probe-providers)
    run_privileged runuser --user "$ASTRA_USER" -- \
        "$ASTRA_HOME/venv/bin/python" "$ASTRA_HOME/infra/deployment_contract.py" "${arguments[@]}"
}

echo "ASTRA deployment target: Ubuntu 24.04, $(uname -m), Python 3.12"
echo "Project: $ASTRA_REPO"
echo "Install root: $ASTRA_HOME"
echo "Service identity: $ASTRA_USER:$ASTRA_GROUP"

run_phase PRECHECK precheck
run_phase DEPENDENCIES system_dependencies
run_phase FILESYSTEM install_filesystem
run_phase CONFIGURATION configure_service_environment
run_phase PYTHON_DEPENDENCIES install_python_environment
run_phase SYSTEMD install_systemd
run_phase START start_and_verify

CURRENT_PHASE="READINESS"
READINESS_EXIT=0
if run_readiness; then
    READINESS_EXIT=0
else
    READINESS_EXIT=$?
fi
CURRENT_PHASE=""
if [[ "$READINESS_EXIT" -eq 0 ]]; then
    record_phase READINESS PASS
    print_summary
    echo "DEPLOYMENT RESULT: SUCCESS"
    echo "ASTRA is listening on loopback; publish only through a separately secured HTTPS reverse proxy."
    exit 0
elif [[ "$READINESS_EXIT" -eq 2 ]]; then
    record_phase READINESS PENDING
    print_summary
    echo "DEPLOYMENT RESULT: DEPLOYED_NOT_READY"
    echo "The service is healthy, but canonical production readiness evidence is incomplete."
    exit 2
else
    record_phase READINESS FAIL
    print_summary
    echo "DEPLOYMENT RESULT: FAILED" >&2
    exit 1
fi
