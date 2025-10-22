#!/bin/bash

# Skrypt do sprawdzania statusu ostatniego backupu
# Zwraca JSON dla łatwego parsowania w n8n
# Użycie: ./check_status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/backup.log"
PID_FILE="$SCRIPT_DIR/backup.pid"

STATUS="unknown"
MESSAGE=""
LAST_SUCCESS=""
LAST_ERROR=""
IS_RUNNING=false
PID=""

# Sprawdź czy proces backupu jest uruchomiony
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if ps -p "$PID" > /dev/null 2>&1; then
    IS_RUNNING=true
    STATUS="running"
    MESSAGE="Backup is currently running with PID $PID"
  else
    IS_RUNNING=false
    STATUS="completed"
    MESSAGE="Backup process not running"
  fi
else
  IS_RUNNING=false
  STATUS="not_started"
  MESSAGE="No backup process found"
fi

# Pobierz ostatnie komunikaty z loga
if [ -f "$LOG_FILE" ]; then
  # Sprawdź ostatnią linię z sukcesem
  LAST_SUCCESS=$(grep -E "Backupy zakończone|Backup.*zakończony sukcesem" "$LOG_FILE" | tail -1)
  
  # Sprawdź ostatnią linię z błędem
  LAST_ERROR=$(grep -E "ERROR|Błąd|BŁĄD" "$LOG_FILE" | tail -1)
  
  # Jeśli nie jest uruchomiony, sprawdź czy ostatni backup się powiódł
  if [ "$IS_RUNNING" = false ]; then
    if echo "$LAST_SUCCESS" | grep -q "Pomyślnie"; then
      SUCCESS_COUNT=$(echo "$LAST_SUCCESS" | grep -oP 'Pomyślnie: \K\d+' || echo "0")
      TOTAL_COUNT=$(echo "$LAST_SUCCESS" | grep -oP 'Pomyślnie: \d+/\K\d+' || echo "0")
      
      if [ "$SUCCESS_COUNT" = "$TOTAL_COUNT" ] && [ "$TOTAL_COUNT" != "0" ]; then
        STATUS="success"
        MESSAGE="Last backup completed successfully ($SUCCESS_COUNT/$TOTAL_COUNT databases)"
      else
        STATUS="partial_success"
        MESSAGE="Last backup partially completed ($SUCCESS_COUNT/$TOTAL_COUNT databases)"
      fi
    elif [ -n "$LAST_ERROR" ]; then
      STATUS="failed"
      MESSAGE="Last backup failed - check logs"
    fi
  fi
fi

# Zwróć JSON
cat << EOF
{
  "status": "$STATUS",
  "message": "$MESSAGE",
  "is_running": $IS_RUNNING,
  "pid": "${PID:-null}",
  "last_success": $([ -n "$LAST_SUCCESS" ] && echo "\"$LAST_SUCCESS\"" || echo "null"),
  "last_error": $([ -n "$LAST_ERROR" ] && echo "\"$LAST_ERROR\"" || echo "null"),
  "log_file": "$LOG_FILE"
}
EOF

# Exit code: 0 jeśli success lub running, 1 jeśli failed
if [ "$STATUS" = "success" ] || [ "$STATUS" = "running" ]; then
  exit 0
else
  exit 1
fi
