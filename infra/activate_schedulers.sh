#!/usr/bin/env bash
# Explicit post-validation activation for ASTRA production scheduler timers.
set -Eeuo pipefail

ASTRA_HOME="${ASTRA_HOME:-/opt/astra}"
ASTRA_USER="${ASTRA_USER:-astra}"
ASTRA_ENV_FILE="${ASTRA_ENV_FILE:-/etc/astra/astra.env}"
PROBE_PROVIDERS=false
SCHEDULER_TIMERS=(
    astra-scheduler-h1.timer
    astra-scheduler-h4.timer
    astra-scheduler-d1.timer
)

for argument in "$@"; do
    case "$argument" in
        --probe-providers) PROBE_PROVIDERS=true ;;
        --help)
            echo "Usage: infra/activate_schedulers.sh [--probe-providers]"
            exit 0
            ;;
        *) echo "Unknown argument: $argument" >&2; exit 64 ;;
    esac
done

run_privileged() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        sudo -n "$@"
    fi
}

[[ "$ASTRA_HOME" == /* && "$ASTRA_ENV_FILE" == /* ]] || {
    echo "ASTRA_HOME and ASTRA_ENV_FILE must be absolute paths" >&2
    exit 1
}

readiness_arguments=(
    readiness --project-root "$ASTRA_HOME" --environment-file "$ASTRA_ENV_FILE"
)
[[ "$PROBE_PROVIDERS" == true ]] && readiness_arguments+=(--probe-providers)
if ! run_privileged runuser --user "$ASTRA_USER" -- \
    "$ASTRA_HOME/venv/bin/python" "$ASTRA_HOME/infra/deployment_contract.py" \
    "${readiness_arguments[@]}"; then
    echo "Scheduler activation refused: production readiness is not READY." >&2
    exit 2
fi

rollback_schedulers() {
    local timer
    local residual_active=()
    local residual_enabled=()

    if ! run_privileged systemctl stop "${SCHEDULER_TIMERS[@]}"; then
        echo "Scheduler rollback warning: systemctl stop failed." >&2
    fi
    if ! run_privileged systemctl disable "${SCHEDULER_TIMERS[@]}"; then
        echo "Scheduler rollback warning: systemctl disable failed." >&2
    fi

    for timer in "${SCHEDULER_TIMERS[@]}"; do
        if run_privileged systemctl is-active --quiet "$timer"; then
            residual_active+=("$timer")
        fi
        if run_privileged systemctl is-enabled --quiet "$timer"; then
            residual_enabled+=("$timer")
        fi
    done

    if (( ${#residual_active[@]} )); then
        echo "Scheduler rollback incomplete; still active: ${residual_active[*]}" >&2
    else
        echo "Scheduler rollback verified: no scheduler timers remain active." >&2
    fi
    if (( ${#residual_enabled[@]} )); then
        echo "Scheduler rollback incomplete; still enabled: ${residual_enabled[*]}" >&2
    fi
}

activation_failed=false
for timer in "${SCHEDULER_TIMERS[@]}"; do
    if ! run_privileged systemctl enable --now "$timer"; then
        echo "Scheduler activation failed while enabling $timer." >&2
        activation_failed=true
        break
    fi
done

if [[ "$activation_failed" == false ]]; then
    for timer in "${SCHEDULER_TIMERS[@]}"; do
        if ! run_privileged systemctl is-enabled --quiet "$timer"; then
            echo "Scheduler activation verification failed; not enabled: $timer" >&2
            activation_failed=true
        fi
        if ! run_privileged systemctl is-active --quiet "$timer"; then
            echo "Scheduler activation verification failed; not active: $timer" >&2
            activation_failed=true
        fi
    done
fi

if [[ "$activation_failed" == true ]]; then
    rollback_schedulers
    exit 1
fi

echo "ASTRA H1/H4/D1 scheduler timers enabled after verified readiness."
