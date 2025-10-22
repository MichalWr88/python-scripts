#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

CONFIG_FILE = "config.json"
LOG_FILE = "backup.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)


def load_config() -> Dict[str, Any]:
    """Ładuje konfigurację z pliku JSON."""
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"Brak pliku konfiguracyjnego: {CONFIG_FILE}")
        sys.exit(1)
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Walidacja podstawowej struktury
        if "databases" not in config:
            logging.error("Brak sekcji 'databases' w pliku konfiguracyjnym")
            sys.exit(1)
        
        if not isinstance(config["databases"], list):
            logging.error("Sekcja 'databases' musi być listą")
            sys.exit(1)
        
        return config
    except json.JSONDecodeError as e:
        logging.error(f"Błąd parsowania pliku JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Błąd podczas wczytywania konfiguracji: {e}")
        sys.exit(1)


def run_cmd(cmd: List[str], env: Optional[Dict[str, str]] = None) -> bool:
    """Uruchamia proces i loguje wyjście, zwraca True jeśli zakończony sukcesem."""
    # Nie logujemy pełnej komendy w przypadku haseł w zmiennych środowiskowych
    safe_cmd = " ".join(cmd)
    logging.info(f"Uruchamiam polecenie: {safe_cmd}")
    
    try:
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            env=env, 
            text=True,
            timeout=3600  # 1 godzina timeout
        )
        
        if result.returncode == 0:
            logging.info(f"Pomyślnie wykonano: {safe_cmd}")
            if result.stdout:
                logging.debug(f"stdout: {result.stdout}")
            return True
        else:
            logging.error(f"Błąd wykonania: {safe_cmd}")
            logging.error(f"Kod wyjścia: {result.returncode}")
            if result.stdout:
                logging.error(f"stdout: {result.stdout}")
            if result.stderr:
                logging.error(f"stderr: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"Timeout podczas wykonywania komendy: {safe_cmd}")
        return False
    except FileNotFoundError:
        logging.error(f"Nie znaleziono programu: {cmd[0]}")
        return False
    except Exception as e:
        logging.error(f"Wyjątek podczas wykonywania komendy {safe_cmd}: {e}")
        return False


def validate_db_config(db: Dict[str, Any]) -> bool:
    """Waliduje konfigurację bazy danych."""
    required_fields = ["name", "type", "host", "port", "database", "backup_path"]
    
    for field in required_fields:
        if field not in db:
            logging.error(f"Brak wymaganego pola '{field}' w konfiguracji bazy {db.get('name', 'unknown')}")
            return False
    
    if db["type"].lower() not in ["mariadb", "postgresql", "mongodb"]:
        logging.error(f"Nieobsługiwany typ bazy: {db['type']}")
        return False
    
    return True


def backup_mariadb(db: Dict[str, Any]) -> bool:
    """Wykonuje backup bazy MariaDB."""
    if not validate_db_config(db):
        return False
    
    try:
        os.makedirs(db['backup_path'], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(db['backup_path'], f"{db['database']}_{timestamp}.sql")

        # Bezpieczne przekazanie hasła przez zmienną środowiskową
        env = os.environ.copy()
        env['MYSQL_PWD'] = db.get('password', '')
        
        # Sprawdź czy używać docker exec
        if db.get('use_docker_exec') and db.get('docker_container'):
            # Dla docker exec musimy przekazać hasło jako parametr -p (niebezpieczne ale w kontenerze)
            # W nowszych wersjach MariaDB, mysqldump jest aliasem dla mariadb-dump
            cmd = [
                "docker", "exec", "-i",
                db['docker_container'],
                "mariadb-dump",  # W kontenerze MariaDB używamy mariadb-dump
                "-h", "localhost",  # w kontenerze używamy localhost
                "-P", str(db['port']),
                "-u", db['user'],
                f"-p{db.get('password', '')}",  # Hasło jako parametr
                "--single-transaction",
                "--routines",
                "--triggers",
                db['database']
            ]
            
            logging.info(f"Backup MariaDB bazy {db['database']} do pliku {backup_file} (używając Docker exec)")
            
            # Dla docker exec, przekierujemy stdout do pliku
            with open(backup_file, "w", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd, 
                    stdout=f, 
                    stderr=subprocess.PIPE, 
                    text=True,
                    timeout=3600
                )
            
            if result.returncode == 0:
                file_size = os.path.getsize(backup_file)
                logging.info(f"Backup bazy {db['database']} zakończony sukcesem. Rozmiar pliku: {file_size} bajtów")
                cleanup_old_backups(db['backup_path'], db['database'])
                return True
            else:
                logging.error(f"Błąd podczas backupu bazy {db['database']}: {result.stderr}")
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return False
        else:
            # Standardowe wywołanie mysqldump na hoście
            cmd = [
                "mysqldump",
                f"--host={db['host']}",
                f"--port={db['port']}",
                f"--user={db['user']}",
                "--single-transaction",
                "--routines",
                "--triggers",
                db['database']
            ]

            logging.info(f"Backup MariaDB bazy {db['database']} do pliku {backup_file}")
            
            with open(backup_file, "w", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd, 
                    stdout=f, 
                    stderr=subprocess.PIPE, 
                    env=env, 
                    text=True,
                    timeout=3600
                )
            
            if result.returncode == 0:
                file_size = os.path.getsize(backup_file)
                logging.info(f"Backup bazy {db['database']} zakończony sukcesem. Rozmiar pliku: {file_size} bajtów")
                cleanup_old_backups(db['backup_path'], db['database'])
                return True
            else:
                logging.error(f"Błąd podczas backupu bazy {db['database']}: {result.stderr}")
                # Usuń niepełny plik backup
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return False
            
    except subprocess.TimeoutExpired:
        logging.error(f"Timeout podczas backupu bazy {db['database']}")
        return False
    except Exception as e:
        logging.error(f"Wyjątek podczas backupu MariaDB: {e}")
        return False


def restore_mariadb(db: Dict[str, Any], backup_file: str) -> bool:
    """Przywraca bazę MariaDB z pliku backup."""
    if not validate_db_config(db):
        return False
    
    if not os.path.exists(backup_file):
        logging.error(f"Plik backup {backup_file} nie istnieje")
        return False
    
    logging.info(f"Przywracanie MariaDB z pliku {backup_file} do bazy {db['database']}")
    
    env = os.environ.copy()
    env['MYSQL_PWD'] = db.get('password', '')
    
    # Sprawdź czy używać docker exec
    if db.get('use_docker_exec') and db.get('docker_container'):
        cmd = [
            "docker", "exec", "-i",
            db['docker_container'],
            "mariadb",  # W kontenerze MariaDB używamy mariadb zamiast mysql
            "-h", "localhost",
            "-P", str(db['port']),
            "-u", db['user'],
            f"-p{db.get('password', '')}",  # Hasło jako parametr
            db['database']
        ]
        
        logging.info(f"Przywracanie MariaDB używając Docker exec")
        
        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd, 
                    stdin=f, 
                    stderr=subprocess.PIPE, 
                    env=env, 
                    text=True,
                    timeout=3600
                )
            
            if result.returncode == 0:
                logging.info(f"Przywracanie bazy {db['database']} zakończone sukcesem.")
                restart_container(db.get("docker_container"))
                return True
            else:
                logging.error(f"Błąd podczas przywracania bazy {db['database']}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logging.error(f"Timeout podczas przywracania bazy {db['database']}")
            return False
        except Exception as e:
            logging.error(f"Wyjątek podczas przywracania MariaDB: {e}")
            return False
    else:
        # Standardowe wywołanie mysql na hoście
        cmd = [
            "mysql",
            f"--host={db['host']}",
            f"--port={db['port']}",
            f"--user={db['user']}",
            db['database']
        ]
        
        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd, 
                    stdin=f, 
                    stderr=subprocess.PIPE, 
                    env=env, 
                    text=True,
                    timeout=3600
                )
            
            if result.returncode == 0:
                logging.info(f"Przywracanie bazy {db['database']} zakończone sukcesem.")
                restart_container(db.get("docker_container"))
                return True
            else:
                logging.error(f"Błąd podczas przywracania bazy {db['database']}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logging.error(f"Timeout podczas przywracania bazy {db['database']}")
            return False
        except Exception as e:
            logging.error(f"Wyjątek podczas przywracania MariaDB: {e}")
            return False


def backup_postgresql(db: Dict[str, Any]) -> bool:
    """Wykonuje backup bazy PostgreSQL."""
    if not validate_db_config(db):
        return False
    
    try:
        os.makedirs(db['backup_path'], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Używamy rozszerzenia .dump dla formatu binarnego
        backup_file = os.path.join(db['backup_path'], f"{db['database']}_{timestamp}.dump")

        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('password', '')

        # Sprawdź czy używać docker exec
        if db.get('use_docker_exec') and db.get('docker_container'):
            cmd = [
                "docker", "exec", "-i",
                db['docker_container'],
                "pg_dump",
                "-h", "localhost",  # w kontenerze używamy localhost
                "-p", str(db['port']),
                "-U", db.get('user', 'postgres'),
                "-F", "c",  # format custom (binary)
                "-b",       # include blobs
                "-v",       # verbose
                db['database']
            ]
            
            logging.info(f"Backup PostgreSQL bazy {db['database']} do pliku {backup_file} (używając Docker exec)")
            
            # Dla docker exec, przekierujemy stdout do pliku
            with open(backup_file, "wb") as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, timeout=3600)
            
            if result.returncode == 0:
                file_size = os.path.getsize(backup_file)
                logging.info(f"Backup bazy {db['database']} zakończony sukcesem. Rozmiar pliku: {file_size} bajtów")
                cleanup_old_backups(db['backup_path'], db['database'])
                return True
            else:
                logging.error(f"Błąd podczas backupu bazy {db['database']}: {result.stderr.decode()}")
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return False
        else:
            # Standardowe wywołanie pg_dump na hoście
            cmd = [
                "pg_dump",
                "-h", db['host'],
                "-p", str(db['port']),
                "-U", db.get('user', 'postgres'),
                "-F", "c",  # format custom (binary)
                "-b",       # include blobs
                "-v",       # verbose
                "-f", backup_file,
                db['database']
            ]

            logging.info(f"Backup PostgreSQL bazy {db['database']} do pliku {backup_file}")
            
            if run_cmd(cmd, env):
                file_size = os.path.getsize(backup_file)
                logging.info(f"Backup bazy {db['database']} zakończony sukcesem. Rozmiar pliku: {file_size} bajtów")
                cleanup_old_backups(db['backup_path'], db['database'])
                return True
            else:
                # Usuń niepełny plik backup
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return False
    except Exception as e:
        logging.error(f"Wyjątek podczas backupu PostgreSQL: {e}")
        return False


def restore_postgresql(db: Dict[str, Any], backup_file: str) -> bool:
    """Przywraca bazę PostgreSQL z pliku backup."""
    if not validate_db_config(db):
        return False
    
    if not os.path.exists(backup_file):
        logging.error(f"Plik backup {backup_file} nie istnieje")
        return False
    
    env = os.environ.copy()
    env['PGPASSWORD'] = db.get('password', '')

    logging.info(f"Przywracanie PostgreSQL z pliku {backup_file} do bazy {db['database']}")

    # Sprawdź czy używać docker exec
    if db.get('use_docker_exec') and db.get('docker_container'):
        cmd = [
            "docker", "exec", "-i",
            db['docker_container'],
            "pg_restore",
            "-h", "localhost",  # w kontenerze używamy localhost
            "-p", str(db['port']),
            "-U", db.get('user', 'postgres'),
            "-d", db['database'],
            "--clean",
            "--if-exists",
            "-v"
        ]
        
        logging.info(f"Przywracanie PostgreSQL używając Docker exec")
        
        # Dla docker exec, przekażemy plik przez stdin
        with open(backup_file, "rb") as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, env=env, timeout=3600)
        
        if result.returncode == 0:
            logging.info(f"Przywracanie bazy {db['database']} zakończone sukcesem.")
            restart_container(db.get("docker_container"))
            return True
        else:
            logging.error(f"Błąd podczas przywracania bazy {db['database']}: {result.stderr.decode()}")
            return False
    else:
        # Standardowe wywołanie pg_restore na hoście
        cmd = [
            "pg_restore",
            "-h", db['host'],
            "-p", str(db['port']),
            "-U", db.get('user', 'postgres'),
            "-d", db['database'],
            "--clean",
            "--if-exists",
            "-v",
            backup_file
        ]

        if run_cmd(cmd, env):
            logging.info(f"Przywracanie bazy {db['database']} zakończone sukcesem.")
            restart_container(db.get("docker_container"))
            return True
        return False


def backup_mongodb(db: Dict[str, Any]) -> bool:
    """Wykonuje backup bazy MongoDB."""
    if not validate_db_config(db):
        return False
    
    try:
        os.makedirs(db['backup_path'], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(db['backup_path'], f"{db['database']}_{timestamp}")

        os.makedirs(backup_dir, exist_ok=True)

        cmd = [
            "mongodump",
            "--host", f"{db['host']}:{db['port']}",
            "--db", db['database'],
            "--out", backup_dir
        ]

        if db.get("user"):
            cmd.extend(["--username", db['user']])
        if db.get("password"):
            cmd.extend(["--password", db['password']])

        logging.info(f"Backup MongoDB bazy {db['database']} do katalogu {backup_dir}")
        
        if run_cmd(cmd):
            # Sprawdź czy backup się powiódł sprawdzając zawartość katalogu
            db_backup_path = os.path.join(backup_dir, db['database'])
            if os.path.exists(db_backup_path) and os.listdir(db_backup_path):
                logging.info(f"Backup bazy {db['database']} zakończony sukcesem.")
                cleanup_old_backups(db['backup_path'], db['database'])
                return True
            else:
                logging.error(f"Backup MongoDB nie zawiera danych dla bazy {db['database']}")
                return False
        return False
    except Exception as e:
        logging.error(f"Wyjątek podczas backupu MongoDB: {e}")
        return False


def restore_mongodb(db: Dict[str, Any], backup_dir: str) -> bool:
    """Przywraca bazę MongoDB z katalogu backup."""
    if not validate_db_config(db):
        return False
    
    if not os.path.exists(backup_dir):
        logging.error(f"Katalog backup {backup_dir} nie istnieje")
        return False
    
    logging.info(f"Przywracanie MongoDB z katalogu {backup_dir} do bazy {db['database']}")

    # Sprawdź czy katalog zawiera dane dla konkretnej bazy
    db_backup_path = os.path.join(backup_dir, db['database'])
    if not os.path.exists(db_backup_path):
        logging.error(f"Brak danych backup dla bazy {db['database']} w katalogu {backup_dir}")
        return False

    cmd = [
        "mongorestore",
        "--host", f"{db['host']}:{db['port']}",
        "--db", db['database'],
        "--drop",
        db_backup_path
    ]

    if db.get("user"):
        cmd.extend(["--username", db['user']])
    if db.get("password"):
        cmd.extend(["--password", db['password']])

    if run_cmd(cmd):
        logging.info(f"Przywracanie bazy {db['database']} zakończone sukcesem.")
        restart_container(db.get("docker_container"))
        return True
    return False


def cleanup_old_backups(backup_path: str, database_name: str, max_backups: int = 3) -> None:
    """Usuwa stare pliki backup, zachowując tylko najnowsze pliki."""
    try:
        if not os.path.exists(backup_path):
            return
        
        # Znajdź wszystkie pliki backup dla tej bazy danych
        backup_files = []
        for filename in os.listdir(backup_path):
            if filename.startswith(f"{database_name}_") and (filename.endswith('.sql') or filename.endswith('.dump')):
                file_path = os.path.join(backup_path, filename)
                if os.path.isfile(file_path):
                    backup_files.append((file_path, os.path.getmtime(file_path)))
        
        # Dla MongoDB - sprawdź katalogi backup
        for dirname in os.listdir(backup_path):
            if dirname.startswith(f"{database_name}_") and os.path.isdir(os.path.join(backup_path, dirname)):
                dir_path = os.path.join(backup_path, dirname)
                backup_files.append((dir_path, os.path.getmtime(dir_path)))
        
        # Sortuj według daty modyfikacji (najnowsze pierwsze)
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # Usuń stare pliki/katalogi (zachowaj tylko max_backups najnowszych)
        files_to_remove = backup_files[max_backups:]
        
        for file_path, _ in files_to_remove:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logging.info(f"Usunięto stary plik backup: {file_path}")
                elif os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
                    logging.info(f"Usunięto stary katalog backup: {file_path}")
            except Exception as e:
                logging.error(f"Błąd podczas usuwania {file_path}: {e}")
        
        if files_to_remove:
            logging.info(f"Usunięto {len(files_to_remove)} starych backupów dla bazy {database_name}")
        
    except Exception as e:
        logging.error(f"Błąd podczas czyszczenia starych backupów dla bazy {database_name}: {e}")


def restart_container(container_name: Optional[str]) -> bool:
    """Restartuje kontener Docker jeśli podano nazwę."""
    if not container_name:
        logging.info("Brak kontenera docker do restartu")
        return True
    
    logging.info(f"Restartuje kontener dockerowy: {container_name}")
    cmd = ["docker", "restart", container_name]
    
    if run_cmd(cmd):
        logging.info(f"Kontener {container_name} został zrestartowany.")
        return True
    else:
        logging.error(f"Nie udało się zrestartować kontenera {container_name}.")
        return False


def find_db(config: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """Znajduje konfigurację bazy danych po nazwie."""
    for db in config.get("databases", []):
        if db.get("name") == name:
            return db
    return None


def print_usage() -> None:
    """Wyświetla informacje o sposobie użycia skryptu."""
    print("Sposób użycia:")
    print("  python db_backup_restore.py backup                                    # wykona backup wszystkich baz z konfiguracji")
    print("  python db_backup_restore.py restore <name> <backup_file_or_dir>      # przywraca bazę o podanej nazwie z podanego backupu")
    print("  python db_backup_restore.py list                                     # wyświetla listę dostępnych baz")
    print()
    
    # Próba wczytania konfiguracji aby pokazać dostępne bazy
    try:
        config = load_config()
        print("Dostępne bazy w konfiguracji:")
        for db in config.get("databases", []):
            print(f"  - {db.get('name', 'N/A')} ({db.get('type', 'N/A')})")
    except:
        print("Nie można wczytać listy baz z konfiguracji.")


def list_databases() -> None:
    """Wyświetla listę dostępnych baz danych."""
    config = load_config()
    print("Dostępne bazy danych:")
    print("-" * 50)
    
    for db in config.get("databases", []):
        print(f"Nazwa: {db.get('name', 'N/A')}")
        print(f"Typ: {db.get('type', 'N/A')}")
        print(f"Host: {db.get('host', 'N/A')}:{db.get('port', 'N/A')}")
        print(f"Baza: {db.get('database', 'N/A')}")
        print(f"Ścieżka backupów: {db.get('backup_path', 'N/A')}")
        if db.get('docker_container'):
            print(f"Kontener Docker: {db['docker_container']}")
        print("-" * 50)

def main() -> None:
    """Główna funkcja programu."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()
    
    if command == "list":
        list_databases()
        return

    config = load_config()

    if command == "backup":
        success_count = 0
        total_count = len(config.get("databases", []))
        containers_to_restart = set()  # Zbiór unikalnych kontenerów do restartu
        
        for db in config.get("databases", []):
            logging.info(f"Rozpoczynam backup bazy: {db.get('name', 'N/A')}")
            
            if not validate_db_config(db):
                continue
                
            db_type = db["type"].lower()
            success = False
            
            if db_type == "mariadb":
                success = backup_mariadb(db)
            elif db_type == "postgresql":
                success = backup_postgresql(db)
            elif db_type == "mongodb":
                success = backup_mongodb(db)
            else:
                logging.error(f"Nieobsługiwany typ bazy: {db_type}")
                continue
            
            if success:
                success_count += 1
                # Dodaj kontener do listy do restartu (jeśli istnieje)
                if db.get("docker_container"):
                    containers_to_restart.add(db["docker_container"])
        
        # Restartuj wszystkie kontenery po zakończeniu backupów
        for container_name in containers_to_restart:
            restart_container(container_name)
                
        logging.info(f"Backupy zakończone. Pomyślnie: {success_count}/{total_count}")
        if containers_to_restart:
            logging.info(f"Zrestartowano kontenery: {', '.join(containers_to_restart)}")
        
    elif command == "restore":
        if len(sys.argv) != 4:
            print("Błąd: restore wymaga 2 argumentów: <name> <backup_file_or_dir>")
            print_usage()
            sys.exit(1)
            
        db_name = sys.argv[2]
        backup_source = sys.argv[3]
        
        db = find_db(config, db_name)
        if not db:
            logging.error(f"Nie znaleziono bazy o nazwie '{db_name}' w konfiguracji.")
            print("Dostępne bazy:")
            for available_db in config.get("databases", []):
                print(f"  - {available_db.get('name', 'N/A')}")
            sys.exit(1)
            
        if not os.path.exists(backup_source):
            logging.error(f"Plik lub katalog backupu '{backup_source}' nie istnieje.")
            sys.exit(1)

        if not validate_db_config(db):
            sys.exit(1)

        db_type = db["type"].lower()
        success = False
        
        if db_type == "mariadb":
            success = restore_mariadb(db, backup_source)
        elif db_type == "postgresql":
            success = restore_postgresql(db, backup_source)
        elif db_type == "mongodb":
            success = restore_mongodb(db, backup_source)
        else:
            logging.error(f"Nieobsługiwany typ bazy: {db_type}")
            sys.exit(1)

        if success:
            logging.info("Przywracanie zakończone sukcesem.")
        else:
            logging.error("Przywracanie zakończone błędem.")
            sys.exit(1)

    else:
        print(f"Nieznana komenda: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()