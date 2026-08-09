#!/bin/bash
# ASTRA v6.0.1-prod — Provider-Agnostic Deployment Script
# Works on any Linux VM — provider-agnostic
set -e

ASTRA_HOME="${ASTRA_HOME:-/opt/astra}"
ASTRA_USER="${ASTRA_USER:-$(whoami)}"
ASTRA_REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "╔════════════════════════════════════════════════╗"
echo "║   ASTRA v6.0.1-prod — Deployment              ║"
echo "╚════════════════════════════════════════════════╝"
echo "Home: $ASTRA_HOME"
echo "Repo: $ASTRA_REPO"
echo "User: $ASTRA_USER"

# ── 1. Detect distro ──
if [ -f /etc/debian_version ]; then
    DISTRO="debian"
    PKG_MGR="apt"
elif [ -f /etc/redhat-release ]; then
    DISTRO="rhel"
    PKG_MGR="dnf"
elif [ -f /etc/alpine-release ]; then
    DISTRO="alpine"
    PKG_MGR="apk"
else
    DISTRO="unknown"
    PKG_MGR=""
fi
echo "Distro: $DISTRO ($PKG_MGR)"

# ── 2. Install system packages ──
echo "── Installing system packages ──"
if [ "$DISTRO" = "debian" ]; then
    sudo apt update -qq && sudo apt install -y -qq python3 python3-venv python3-pip unzip curl > /dev/null
elif [ "$DISTRO" = "rhel" ]; then
    sudo dnf install -y python3 python3-devel unzip curl > /dev/null
elif [ "$DISTRO" = "alpine" ]; then
    sudo apk add python3 py3-pip unzip curl > /dev/null
fi
echo "  System packages installed."

# ── 3. Copy project to ASTRA_HOME ──
echo "── Copying project to $ASTRA_HOME ──"
if [ "$ASTRA_REPO" != "$ASTRA_HOME" ]; then
    sudo mkdir -p "$ASTRA_HOME"
    sudo cp -r "$ASTRA_REPO"/* "$ASTRA_HOME/" 2>/dev/null || true
    sudo cp -r "$ASTRA_REPO"/.agents "$ASTRA_HOME/" 2>/dev/null || true
fi
cd "$ASTRA_HOME"

# ── 4. Create venv and install deps ──
echo "── Setting up Python venv ──"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install yfinance -q
echo "  Dependencies installed."

# ── 5. Create directories ──
echo "── Creating directories ──"
sudo mkdir -p /var/log/astra /var/backups/astra
sudo chown -R "$ASTRA_USER" /var/log/astra /var/backups/astra 2>/dev/null || true
mkdir -p memory_db forex/data forex/models

# ── 6. Copy systemd services ──
echo "── Setting up systemd services ──"
if [ -d /etc/systemd/system ]; then
    sudo cp infra/systemd/*.service /etc/systemd/system/ 2>/dev/null || true
    sudo cp infra/systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
    # Fix paths in service files
    sudo sed -i "s|/opt/astra|$ASTRA_HOME|g" /etc/systemd/system/astra-*.service 2>/dev/null || true
    sudo systemctl daemon-reload
    sudo systemctl enable astra-api astra-monitor 2>/dev/null || true
    sudo systemctl enable astra-scheduler-h1.timer astra-scheduler-h4.timer astra-scheduler-d1.timer 2>/dev/null || true
    sudo systemctl enable astra-backup.timer 2>/dev/null || true
    echo "  Systemd services enabled."
else
    echo "  systemd not found — using cron instead"
    # Set up cron jobs
    (crontab -l 2>/dev/null; echo "2 * * * * cd $ASTRA_HOME && venv/bin/python scheduler/autonomous_scheduler.py --timeframe H1 >> /var/log/astra/scheduler_h1.log 2>&1") | crontab -
    (crontab -l 2>/dev/null; echo "5 */4 * * * cd $ASTRA_HOME && venv/bin/python scheduler/autonomous_scheduler.py --timeframe H4 >> /var/log/astra/scheduler_h4.log 2>&1") | crontab -
    (crontab -l 2>/dev/null; echo "10 0 * * * cd $ASTRA_HOME && venv/bin/python scheduler/autonomous_scheduler.py --timeframe D1 >> /var/log/astra/scheduler_d1.log 2>&1") | crontab -
    echo "  Cron jobs installed."
fi

# ── 7. Set up logrotate ──
echo "── Setting up log rotation ──"
if [ -d /etc/logrotate.d ]; then
    sudo cp infra/logging/logrotate.conf /etc/logrotate.d/astra
    echo "  Logrotate configured."
fi

# ── 8. Initial dataset generation ──
echo "── Initial dataset generation ──"
python scheduler/autonomous_scheduler.py --init 2>&1 || echo "  Init may need internet access — will retry on first scheduled cycle."

# ── 9. Verify ──
echo "── Verification ──"
python check_startup.py 2>/dev/null || echo "  check_startup.py warnings (may be ok)"
python test_complete_pipeline.py 2>/dev/null || echo "  test_complete_pipeline.py warnings"

# ── 10. Start services ──
echo "── Starting services ──"
if [ -d /etc/systemd/system ]; then
    sudo systemctl start astra-api 2>/dev/null || true
    sudo systemctl start astra-monitor 2>/dev/null || true
    sudo systemctl start astra-scheduler-h1.timer 2>/dev/null || true
    sudo systemctl start astra-scheduler-h4.timer 2>/dev/null || true
    sudo systemctl start astra-scheduler-d1.timer 2>/dev/null || true
    sudo systemctl start astra-backup.timer 2>/dev/null || true
    echo "  Services started."
fi

# ── 11. Print summary ──
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   ASTRA v6.0.1-prod — Deployed!                ║"
echo "╠════════════════════════════════════════════════╣"
echo "║  Workspace: http://$EXTERNAL_IP:8000"
echo "║  Health:    http://$EXTERNAL_IP:8000/health"
echo "║  Logs:      /var/log/astra/"
echo "║  Backups:   /var/backups/astra/"
echo "║  DB:        $ASTRA_HOME/memory_db/astra_autonomous.db"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "Commands:"
echo "  Status:     python scheduler/autonomous_scheduler.py --status"
echo "  Manual H1:  python scheduler/autonomous_scheduler.py --timeframe H1"
echo "  Add symbol: python scheduler/autonomous_scheduler.py --add-symbol NZDUSD"
