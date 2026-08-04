#!/bin/bash
# ASTRA Backup Script — creates tar.gz with DB, datasets, models, config, scheduler
set -e

ASTRA_HOME="${ASTRA_HOME:-/opt/astra}"
BACKUP_DIR="/var/backups/astra"
RETENTION_DAYS="${ASTRA_BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/astra_backup_$TIMESTAMP.tar.gz"

echo "[$(date)] Starting ASTRA backup..." >> /var/log/astra/backup.log

mkdir -p "$BACKUP_DIR"

cd "$ASTRA_HOME"
tar -czf "$BACKUP_FILE" \
    memory_db/ \
    forex/data/ \
    forex/models/ \
    infra/config/astra.env \
    scheduler/ \
    infra/db/ \
    infra/monitor/ \
    workspace/server.py \
    2>/dev/null || true

# Also save a manifest
echo "Backup: $BACKUP_FILE" > "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
echo "Date: $(date)" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
find . -name "*.db" -o -name "*.csv" -o -name "*.pkl" -o -name "*.joblib" | head -50 >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"

# Delete old backups
find "$BACKUP_DIR" -name "astra_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "manifest_*.txt" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

echo "[$(date)] Backup complete: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))" >> /var/log/astra/backup.log
echo "Backup created: $BACKUP_FILE"
