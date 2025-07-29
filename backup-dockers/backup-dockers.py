import os
import sys
import json
import time
import logging
import signal
from datetime import datetime
from docker import from_env, errors
import requests

__version__ = "1.3.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/backup-dockers.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variable to track current operation
current_operation = None

def signal_handler(signum, frame):
    global current_operation
    logger.warning(f"Received signal {signum} (KeyboardInterrupt)")
    if current_operation:
        logger.warning(f"Interrupted during: {current_operation}")
    else:
        logger.warning("Interrupted during unknown operation")
    sys.exit(1)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

def send_error(webhook_url: str, message: str):
    logger.error(f"ERROR: {message}")
    try:
        requests.post(webhook_url, json={"error": message})
        logger.info("Error sent to webhook successfully")
    except Exception as e:
        logger.error(f"Failed to send error to webhook: {e}")

def send_info(webhook_url: str, message: str):
    logger.info(f"INFO: {message}")
    try:
        requests.post(webhook_url, json={"info": message})
    except Exception as e:
        logger.warning(f"Failed to send info to webhook: {e}")

def stop_container_with_retry(container, webhook_url, max_retries=3, stop_timeout=15, check_interval=1, max_wait=30):
    logger.info(f"Attempting to stop container: {container.name}")
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Stop attempt {attempt}/{max_retries} for container {container.name}")
            container.stop(timeout=stop_timeout)
        except Exception as e:
            error_msg = f"Próba zatrzymania kontenera {container.name} nr {attempt} nie powiodła się: {e}"
            send_error(webhook_url, error_msg)
            time.sleep(2)
            continue

        waited = 0
        while waited < max_wait:
            container.reload()
            if container.status in ['exited', 'dead']:
                logger.info(f"Container {container.name} stopped successfully after {waited} seconds")
                return True
            time.sleep(check_interval)
            waited += check_interval

        error_msg = f"Kontener {container.name} nie zatrzymał się po {max_wait} sekundach, próba nr {attempt}"
        send_error(webhook_url, error_msg)

    # Wymuszenie kill po nieudanych próbach stop
    try:
        logger.warning(f"Force killing container {container.name}")
        container.kill()
        error_msg = f"Wymuszono zatrzymanie kontenera {container.name} metodą kill() po nieudanych próbach stop()"
        send_error(webhook_url, error_msg)
        return True
    except Exception as e:
        error_msg = f"Nie udało się wymusić zatrzymania kontenera {container.name}: {e}"
        send_error(webhook_url, error_msg)
        return False

def backup_volume(volume_name: str, backup_path: str, webhook_url: str):
    global current_operation
    current_operation = f"backing up volume {volume_name}"
    logger.info(f"Starting backup of volume: {volume_name}")
    send_info(webhook_url, f"Starting backup of volume: {volume_name}")
    
    client = from_env()
    try:
        volume = client.volumes.get(volume_name)
        logger.info(f"Volume {volume_name} found successfully")
    except errors.NotFound as e:
        error_msg = f"Wolumen {volume_name} nie istnieje: {e}"
        send_error(webhook_url, error_msg)
        return
    except Exception as e:
        error_msg = f"Błąd przy pobieraniu wolumenu {volume_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    tmp_container_name = f"temp-backup-{volume_name}"
    logger.info(f"Creating temporary container {tmp_container_name} for volume backup")
    
    try:
        container = client.containers.run(
            image="alpine:latest",
            command="sleep 600",
            volumes={volume_name: {'bind': '/data', 'mode': 'ro'}},
            name=tmp_container_name,
            detach=True,
            remove=True,
        )
        logger.info(f"Temporary container {tmp_container_name} created successfully")
    except Exception as e:
        error_msg = f"Błąd tworzenia kontenera do backupu wolumenu {volume_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    try:
        current_operation = f"creating TAR archive for volume {volume_name}"
        logger.info(f"Creating TAR archive for volume {volume_name}")
        exec_result = container.exec_run("tar -cf /data_backup.tar -C /data .")
        if exec_result.exit_code != 0:
            error_msg = f"Błąd tworzenia archiwum TAR w kontenerze backupującym wolumen {volume_name}"
            send_error(webhook_url, error_msg)
            container.kill()
            return

        current_operation = f"copying volume data for {volume_name} to {backup_path}"
        logger.info(f"TAR archive created successfully, copying to {backup_path}")
        bits, stat = container.get_archive("/data_backup.tar")

        with open(backup_path, "wb") as f:
            chunk_count = 0
            for chunk in bits:
                f.write(chunk)
                chunk_count += 1
                if chunk_count % 100 == 0:  # Log every 100 chunks
                    logger.info(f"Volume {volume_name}: processed {chunk_count} chunks")

        file_size = os.path.getsize(backup_path)
        logger.info(f"Volume backup completed: {volume_name} -> {backup_path} ({file_size} bytes)")
        send_info(webhook_url, f"Volume backup completed: {volume_name} ({file_size} bytes)")

    except Exception as e:
        error_msg = f"Błąd podczas kopiowania archiwum wolumenu {volume_name}: {e}"
        send_error(webhook_url, error_msg)

    finally:
        try:
            logger.info(f"Cleaning up temporary container {tmp_container_name}")
            container.kill()
        except Exception:
            pass
        current_operation = None

def restore_volume(volume_name: str, backup_path: str, webhook_url: str):
    logger.info(f"Starting restore of volume: {volume_name}")
    send_info(webhook_url, f"Starting restore of volume: {volume_name}")
    
    client = from_env()
    if not os.path.isfile(backup_path):
        error_msg = f"Backup wolumenu {volume_name} nie istnieje pod ścieżką {backup_path}"
        send_error(webhook_url, error_msg)
        return

    try:
        volume = client.volumes.get(volume_name)
        logger.info(f"Volume {volume_name} already exists")
    except errors.NotFound:
        try:
            volume = client.volumes.create(name=volume_name)
            logger.info(f"Volume {volume_name} created successfully")
        except Exception as e:
            error_msg = f"Błąd tworzenia wolumenu {volume_name}: {e}"
            send_error(webhook_url, error_msg)
            return
    except Exception as e:
        error_msg = f"Błąd pobierania wolumenu {volume_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    tmp_container_name = f"temp-restore-{volume_name}"
    logger.info(f"Creating temporary container {tmp_container_name} for volume restore")
    
    try:
        container = client.containers.run(
            image="alpine:latest",
            command="sleep 600",
            volumes={volume_name: {'bind': '/data', 'mode': 'rw'}},
            name=tmp_container_name,
            detach=True,
            remove=True,
        )
        logger.info(f"Temporary container {tmp_container_name} created successfully")
    except Exception as e:
        error_msg = f"Błąd tworzenia kontenera do przywracania wolumenu {volume_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    try:
        logger.info(f"Reading backup file: {backup_path}")
        with open(backup_path, "rb") as f:
            data = f.read()
        
        logger.info(f"Restoring data to volume {volume_name}")
        success = container.put_archive(path="/data", data=data)
        if not success:
            error_msg = f"Nie udało się przywrócić plików do wolumenu {volume_name}"
            send_error(webhook_url, error_msg)
        else:
            logger.info(f"Volume restore completed: {volume_name}")
            send_info(webhook_url, f"Volume restore completed: {volume_name}")
    except Exception as e:
        error_msg = f"Błąd podczas przywracania statutu wolumenu {volume_name}: {e}"
        send_error(webhook_url, error_msg)
    finally:
        try:
            logger.info(f"Cleaning up temporary container {tmp_container_name}")
            container.kill()
        except Exception:
            pass

def backup_container_snapshot(container_name: str, backup_path: str, webhook_url: str):
    global current_operation
    current_operation = f"backing up container {container_name}"
    logger.info(f"Starting backup of container: {container_name}")
    send_info(webhook_url, f"Starting backup of container: {container_name}")
    
    client = from_env()
    try:
        container = client.containers.get(container_name)
        logger.info(f"Container {container_name} found successfully")
    except errors.NotFound:
        error_msg = f"Kontener {container_name} nie istnieje."
        send_error(webhook_url, error_msg)
        return
    except Exception as e:
        error_msg = f"Błąd pobierania kontenera {container_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    snapshot_image_name = f"backup_snapshot_{container_name.lower()}"
    current_operation = f"creating snapshot image for container {container_name}"
    logger.info(f"Creating snapshot image: {snapshot_image_name}")

    try:
        image = container.commit(repository=snapshot_image_name)
        logger.info(f"Container snapshot created successfully: {snapshot_image_name}")
    except Exception as e:
        error_msg = f"Błąd tworzenia snapshotu kontenera {container_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    try:
        current_operation = f"saving container snapshot {container_name} to file {backup_path}"
        logger.info(f"Saving container snapshot to file: {backup_path}")
        image_tar_stream = image.save(named=True)
        
        with open(backup_path, "wb") as f:
            chunk_count = 0
            bytes_written = 0
            for chunk in image_tar_stream:
                f.write(chunk)
                chunk_count += 1
                bytes_written += len(chunk)
                if chunk_count % 50 == 0:  # Log every 50 chunks
                    logger.info(f"Container {container_name}: processed {chunk_count} chunks, {bytes_written} bytes")

        file_size = os.path.getsize(backup_path)
        logger.info(f"Container backup completed: {container_name} -> {backup_path} ({file_size} bytes)")
        send_info(webhook_url, f"Container backup completed: {container_name} ({file_size} bytes)")

        try:
            logger.info(f"Cleaning up snapshot image: {snapshot_image_name}")
            client.images.remove(snapshot_image_name, force=True)
        except Exception:
            pass

    except Exception as e:
        error_msg = f"Błąd zapisu snapshotu kontenera {container_name} do pliku: {e}"
        send_error(webhook_url, error_msg)
    finally:
        current_operation = None

def restore_container_snapshot(container_name: str, backup_path: str, webhook_url: str):
    logger.info(f"Starting restore of container: {container_name}")
    send_info(webhook_url, f"Starting restore of container: {container_name}")
    
    client = from_env()
    if not os.path.isfile(backup_path):
        error_msg = f"Backup snapshotu kontenera {container_name} nie istnieje pod ścieżką {backup_path}"
        send_error(webhook_url, error_msg)
        return

    try:
        logger.info(f"Loading container snapshot from: {backup_path}")
        with open(backup_path, "rb") as f:
            images = client.images.load(f.read())
        logger.info(f"Container snapshot loaded successfully")
    except Exception as e:
        error_msg = f"Błąd ładowania snapshotu kontenera {container_name}: {e}"
        send_error(webhook_url, error_msg)
        return

    try:
        existing_container = client.containers.get(container_name)
        logger.info(f"Existing container {container_name} found, stopping it")
        stopped = stop_container_with_retry(existing_container, webhook_url)
        if stopped:
            existing_container.remove()
            logger.info(f"Existing container {container_name} removed")
        else:
            error_msg = f"Nie udało się zatrzymać kontenera {container_name}, pomijam usunięcie i start nowego."
            send_error(webhook_url, error_msg)
            return
    except errors.NotFound:
        logger.info(f"No existing container {container_name} found")
        pass
    except Exception as e:
        error_msg = f"Błąd usuwania istniejącego kontenera {container_name}: {e}"
        send_error(webhook_url, error_msg)

    try:
        image_id = images[0].id if images else None
        if not image_id:
            error_msg = f"Brak obrazu do uruchomienia kontenera {container_name}"
            send_error(webhook_url, error_msg)
            return

        logger.info(f"Starting new container {container_name} from snapshot")
        client.containers.run(image=image_id, name=container_name, detach=True)
        logger.info(f"Container restore completed: {container_name}")
        send_info(webhook_url, f"Container restore completed: {container_name}")
    except Exception as e:
        error_msg = f"Błąd uruchamiania kontenera {container_name} ze snapshotu: {e}"
        send_error(webhook_url, error_msg)

def load_config(config_path: str):
    if not os.path.isfile(config_path):
        print(f"Brak pliku konfiguracyjnego: {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    logger.info(f"Starting backup-dockers script v{__version__}")
    
    if len(sys.argv) < 3 or sys.argv[1] not in {"backup", "restore"}:
        print(f"Użycie: {sys.argv[0]} [backup|restore] <ścieżka_do_konfigu>")
        sys.exit(1)

    mode = sys.argv[1]
    config_path = sys.argv[2]
    logger.info(f"Mode: {mode}, Config: {config_path}")
    
    config = load_config(config_path)

    volumes = config.get("volumes", [])
    containers = config.get("containers", [])
    backup_dir = config.get("backup_dir", "/mnt/pendrak")
    webhook_url = config.get("webhook_url")

    logger.info(f"Found {len(volumes)} volumes and {len(containers)} containers to process")
    logger.info(f"Backup directory: {backup_dir}")

    os.makedirs(backup_dir, exist_ok=True)

    if mode == "backup":
        logger.info("Starting backup process")
        send_info(webhook_url, f"Starting backup process: {len(volumes)} volumes, {len(containers)} containers")
        
        for i, volume in enumerate(volumes, 1):
            logger.info(f"Processing volume {i}/{len(volumes)}: {volume}")
            backup_path = os.path.join(backup_dir, f"{volume}.tar")
            backup_volume(volume, backup_path, webhook_url)

        for i, container in enumerate(containers, 1):
            logger.info(f"Processing container {i}/{len(containers)}: {container}")
            backup_path = os.path.join(backup_dir, f"{container}.tar")
            backup_container_snapshot(container, backup_path, webhook_url)
            
        logger.info("Backup process completed")
        send_info(webhook_url, "Backup process completed successfully")

    elif mode == "restore":
        logger.info("Starting restore process")
        send_info(webhook_url, f"Starting restore process: {len(volumes)} volumes, {len(containers)} containers")
        
        for i, volume in enumerate(volumes, 1):
            logger.info(f"Processing volume {i}/{len(volumes)}: {volume}")
            backup_path = os.path.join(backup_dir, f"{volume}.tar")
            restore_volume(volume, backup_path, webhook_url)

        for i, container in enumerate(containers, 1):
            logger.info(f"Processing container {i}/{len(containers)}: {container}")
            backup_path = os.path.join(backup_dir, f"{container}.tar")
            restore_container_snapshot(container, backup_path, webhook_url)
            
        logger.info("Restore process completed")
        send_info(webhook_url, "Restore process completed successfully")

if __name__ == "__main__":
    main()