#!/bin/bash

# Script to backup Docker containers/volumes and sync to remote server
# Usage: ./backup-and-sync.sh

set -e  # Exit on any error

SCRIPT_DIR="/home/michal/github/python-scripts/backup-dockers"
CONFIG_FILE="$SCRIPT_DIR/config.json"
BACKUP_DIR="/mnt/pendrak1/backup-docker"
LOG_FILE="/tmp/backup-and-sync.log"

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Starting backup and sync process"

# Change to script directory
cd "$SCRIPT_DIR"

# Run backup process (remove the & to wait for completion)
log "Starting Docker backup process"
if ./start.sh backup-dockers.py backup ./config.json; then
    log "Docker backup completed successfully"
else
    log "ERROR: Docker backup failed with exit code $?"
    exit 1
fi

# Check if backup directory exists and has files
if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR")" ]; then
    log "ERROR: Backup directory is empty or doesn't exist"
    exit 1
fi

# Sync to remote server
log "Starting rsync to remote server"
if rsync -av --progress --stats --password-file=<(echo "V#GK^yzdX6") "$BACKUP_DIR/" rsync://michal@192.168.0.80/others/backup-dockers/; then
    log "Rsync completed successfully"
else
    log "ERROR: Rsync failed with exit code $?"
    exit 1
fi

log "Backup and sync process completed successfully"
