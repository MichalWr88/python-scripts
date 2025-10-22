#!/bin/bash

# Skrypt do uruchamiania backupu w tle (asynchronicznie)
# Użycie: ./start_async.sh db_backup_restore.py backup

if [ -z "$1" ]; then
  echo "Usage: $0 <python_file> [arguments...]"
  exit 1
fi

PYTHON_FILE=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/async_backup.log"
PID_FILE="$SCRIPT_DIR/backup.pid"

# Check if the virtual environment directory exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
  echo '{"status":"error","message":"Virtual environment not found. Run init.sh first."}'
  exit 1
fi

# Sprawdź czy backup już nie jest uruchomiony
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if ps -p "$OLD_PID" > /dev/null 2>&1; then
    echo "{\"status\":\"already_running\",\"message\":\"Backup is already running\",\"pid\":$OLD_PID}"
    exit 0
  fi
fi

# Uruchom backup w tle jako niezależny proces
cd "$SCRIPT_DIR"
shift # Remove the first argument (python file name)

# Wyczyść stary log i rozpocznij nowy
echo "=== Backup started at $(date) ===" > "$LOG_FILE"

# Użyj nohup + setsid aby całkowicie odłączyć proces od terminala
setsid bash -c "
  source venv/bin/activate
  python $PYTHON_FILE $@ >> $LOG_FILE 2>&1
  EXIT_CODE=\$?
  echo \"=== Backup finished at \$(date) with exit code \$EXIT_CODE ===\" >> $LOG_FILE
  deactivate
  rm -f $PID_FILE
" </dev/null >/dev/null 2>&1 &

BACKUP_PID=$!
echo "$BACKUP_PID" > "$PID_FILE"

# Zwróć JSON dla łatwiejszego parsowania w n8n
echo "{\"status\":\"started\",\"message\":\"Backup started in background\",\"pid\":$BACKUP_PID,\"log_file\":\"$LOG_FILE\"}"

exit 0
