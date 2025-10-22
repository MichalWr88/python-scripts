#!/usr/bin/env python3
"""
Prosty skrypt do uruchamiania backupu w tle i zwracania od razu odpowiedzi.
Użycie: python start_backup_async.py
"""
import subprocess
import sys
import os
import json
from datetime import datetime

def start_backup_async():
    """Uruchamia backup w tle i zwraca status."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, "venv", "bin", "python")
    backup_script = os.path.join(script_dir, "db_backup_restore.py")
    log_file = os.path.join(script_dir, "async_backup.log")
    
    # Sprawdź czy venv istnieje
    if not os.path.exists(venv_python):
        return {
            "status": "error",
            "message": "Virtual environment not found. Run init.sh first.",
            "timestamp": datetime.now().isoformat()
        }
    
    # Sprawdź czy backup już nie jest uruchomiony
    try:
        result = subprocess.run(
            ["pgrep", "-f", "db_backup_restore.py backup"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return {
                "status": "already_running",
                "message": "Backup is already running",
                "pid": result.stdout.strip(),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        pass  # Jeśli pgrep nie działa, kontynuuj
    
    # Uruchom backup w tle
    try:
        with open(log_file, "a") as log:
            log.write(f"\n{'='*50}\n")
            log.write(f"Backup started at: {datetime.now().isoformat()}\n")
            log.write(f"{'='*50}\n")
            
        # Użyj subprocess.Popen aby uruchomić proces w tle
        process = subprocess.Popen(
            [venv_python, backup_script, "backup"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=script_dir,
            start_new_session=True  # Odłącz od sesji rodzica
        )
        
        # Przekieruj output do logu w tle
        def log_output():
            with open(log_file, "a") as log:
                for line in process.stdout:
                    log.write(line.decode())
                    log.flush()
        
        import threading
        thread = threading.Thread(target=log_output, daemon=True)
        thread.start()
        
        return {
            "status": "started",
            "message": "Backup started successfully in background",
            "pid": process.pid,
            "log_file": log_file,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to start backup: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    result = start_backup_async()
    print(json.dumps(result, indent=2))
    
    # Exit code 0 jeśli started lub already_running
    if result["status"] in ["started", "already_running"]:
        sys.exit(0)
    else:
        sys.exit(1)
