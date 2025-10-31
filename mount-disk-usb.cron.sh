#!/bin/bash

# Punkt montowania
MOUNT_POINT="/mnt/usb1"
# UUID dysku (zmień na właściwy UUID gdy będzie dostępny)
DISK_UUID="a4908213-f21d-41e7-b6e3-d1e1342fd1a9"
# Log file
LOG_FILE="/var/log/usb_mount.log"

# Funkcja logowania
log_msg() {
    local msg="$1"
    echo "$(date): $msg"
    
    # Sprawdź czy można pisać do pliku logów
    if [ -w "$LOG_FILE" ] || [ -w "$(dirname "$LOG_FILE")" ]; then
        echo "$(date): $msg" >> "$LOG_FILE" 2>/dev/null || true
    else
        # Jeśli nie można pisać do /var/log, użyj lokalnego pliku
        local local_log="./usb_mount.log"
        echo "$(date): $msg" >> "$local_log" 2>/dev/null || true
    fi
}

# Funkcja sprawdzenia zdrowia dysku
check_disk_health() {
    local device="$1"
    local device_path="$device"
    
    # Jeśli to UUID, znajdź prawdziwą ścieżkę
    if echo "$device" | grep -q "UUID="; then
        uuid=$(echo "$device" | cut -d'=' -f2)
        device_path=$(readlink -f "/dev/disk/by-uuid/$uuid" 2>/dev/null)
        if [ -z "$device_path" ]; then
            log_msg "WARNING: Nie można znaleźć ścieżki dla UUID $uuid"
            return 1
        fi
        log_msg "UUID $uuid wskazuje na urządzenie: $device_path"
    fi
    
    # Sprawdź czy urządzenie istnieje
    if [ ! -b "$device_path" ]; then
        log_msg "WARNING: Urządzenie $device_path nie istnieje jako block device"
        return 1
    fi
    
    # Sprawdź czy można czytać z dysku (najpierw bez sudo)
    if timeout 15 dd if="$device_path" of=/dev/null bs=1M count=1 >/dev/null 2>&1; then
        log_msg "Sprawdzenie zdrowia dysku $device_path: OK"
        return 0
    elif timeout 15 sudo dd if="$device_path" of=/dev/null bs=1M count=1 >/dev/null 2>&1; then
        log_msg "Sprawdzenie zdrowia dysku $device_path: OK (wymagane sudo)"
        return 0
    else
        log_msg "WARNING: Problemy z odczytem dysku $device_path"
        
        # Druga próba z mniejszym blokiem i sudo
        if timeout 10 sudo dd if="$device_path" of=/dev/null bs=512 count=1 >/dev/null 2>&1; then
            log_msg "Sprawdzenie zdrowia dysku $device_path: OK (po drugiej próbie z sudo)"
            return 0
        else
            log_msg "BŁĄD: Dysk $device_path nie odpowiada na testy odczytu"
            return 1
        fi
    fi
}

# Funkcja ciągłego monitorowania dysku (dla dodatkowego skryptu)
monitor_disk_health() {
    local device="$1"
    local interval="${2:-300}"  # Domyślnie co 5 minut
    
    log_msg "Rozpoczęcie monitorowania dysku $device co $interval sekund"
    
    while true; do
        if ! check_disk_health "$device"; then
            log_msg "ALARM: Problemy z dyskiem $device - próba odzyskania!"
            recover_usb_storage
            sleep 30
        fi
        sleep "$interval"
    done
}

# Funkcja reset USB device
reset_usb_device() {
    local device_id="$1"
    log_msg "Próba resetu urządzenia USB $device_id"
    
    local reset_count=0
    
    # Znajdź ścieżkę do urządzenia USB
    for usb_dev in /sys/bus/usb/devices/*/idVendor; do
        if [ -f "$usb_dev" ]; then
            vendor=$(cat "$usb_dev" 2>/dev/null)
            product=$(cat "$(dirname "$usb_dev")/idProduct" 2>/dev/null)
            if [ "$vendor:$product" = "$device_id" ]; then
                usb_path=$(dirname "$usb_dev")
                device_name=$(basename "$usb_path")
                log_msg "Znaleziono urządzenie $device_id w $usb_path"
                
                if [ -w "$usb_path/authorized" ]; then
                    log_msg "Wykonywanie resetu urządzenia $device_name..."
                    echo 0 > "$usb_path/authorized" 2>/dev/null && log_msg "Deautoryzacja: OK" || log_msg "Deautoryzacja: BŁĄD"
                    sleep 2
                    echo 1 > "$usb_path/authorized" 2>/dev/null && log_msg "Autoryzacja: OK" || log_msg "Autoryzacja: BŁĄD"
                    reset_count=$((reset_count + 1))
                else
                    log_msg "Brak uprawnień do resetu $usb_path/authorized"
                fi
            fi
        fi
    done
    
    if [ $reset_count -gt 0 ]; then
        log_msg "Reset wykonano dla $reset_count urządzeń"
        return 0
    else
        log_msg "Nie znaleziono urządzenia $device_id do resetu"
        return 1
    fi
}

# Funkcja odzyskiwania USB storage
recover_usb_storage() {
    log_msg "Próba odzyskania USB storage..."
    
    # Reset modułu usb-storage
    if lsmod | grep -q usb_storage; then
        log_msg "Przeładowanie modułu usb-storage"
        sudo modprobe -r usb_storage 2>/dev/null || true
        sleep 2
        sudo modprobe usb_storage 2>/dev/null || true
        sleep 5
    fi
    
    # Reset urządzenia ASMT (kieszeń)
    reset_usb_device "174c:55aa"
    
    # Czekaj na ponowne wykrycie
    sleep 10
}

# Funkcja debug - pokaż dostępne urządzenia USB
show_usb_devices() {
    log_msg "DEBUG: Dostępne urządzenia USB:"
    lsusb | while read line; do
        log_msg "DEBUG: $line"
    done
    
    log_msg "DEBUG: Dostępne dyski:"
    for disk in /sys/block/sd*; do
        if [ -e "$disk" ]; then
            disk_name=$(basename $disk)
            removable=$(cat $disk/removable 2>/dev/null || echo "N/A")
            vendor=$(cat $disk/device/vendor 2>/dev/null | tr -d ' ' || echo "N/A")
            model=$(cat $disk/device/model 2>/dev/null | tr -d ' ' || echo "N/A")
            mounted=$(mount | grep "^/dev/$disk_name" | awk '{print $3}' || echo "nie zamontowany")
            log_msg "DEBUG: $disk_name - removable:$removable vendor:$vendor model:$model mounted:$mounted"
        fi
    done
}

# Funkcja znajdowania dysku USB
find_usb_disk() {
    # Sprawdź czy podany UUID istnieje
    if [ -e "/dev/disk/by-uuid/$DISK_UUID" ]; then
        echo "UUID=$DISK_UUID"
        return 0
    fi
    
    # Sprawdź dostępne dyski USB (removable) które NIE SĄ już zamontowane
    for disk in /sys/block/sd*; do
        if [ -e "$disk/removable" ] && [ "$(cat $disk/removable)" = "1" ]; then
            disk_name=$(basename $disk)
            device_path="/dev/${disk_name}"
            
            # Sprawdź czy dysk nie jest już zamontowany
            if mount | grep -q "^$device_path"; then
                echo "$(date): INFO: Dysk $device_path jest już zamontowany - pomijam" >&2
                continue
            fi
            
            # Sprawdź czy ma partycje
            if [ -e "/dev/${disk_name}1" ] && ! mount | grep -q "^/dev/${disk_name}1"; then
                echo "/dev/${disk_name}1"
                return 0
            elif [ -b "$device_path" ] && ! mount | grep -q "^$device_path"; then
                echo "$device_path"
                return 0
            fi
        fi
    done
    
    return 1
}

# Znajdź urządzenie do zamontowania
log_msg "Wyszukiwanie dysku USB..."
DEVICE_TO_MOUNT=$(find_usb_disk)

if [ -z "$DEVICE_TO_MOUNT" ]; then
    log_msg "BŁĄD! Nie znaleziono dysku USB ani UUID=$DISK_UUID."
    log_msg "Sprawdzam ponownie za 5 sekund..."
    sleep 5
    DEVICE_TO_MOUNT=$(find_usb_disk)
    
    if [ -z "$DEVICE_TO_MOUNT" ]; then
        log_msg "Nadal brak dostępnych dysków USB. Próba odzyskania..."
        show_usb_devices
        
        # Próba odzyskania USB
        if recover_usb_storage; then
            log_msg "Próba ponownego wyszukania po odzyskaniu..."
            sleep 3
            DEVICE_TO_MOUNT=$(find_usb_disk)
        fi
        
        if [ -z "$DEVICE_TO_MOUNT" ]; then
            log_msg "BŁĄD: Nie udało się znaleźć dysku USB nawet po próbie odzyskania!"
            exit 1
        else
            log_msg "Sukces! Dysk znaleziony po odzyskaniu: $DEVICE_TO_MOUNT"
        fi
    fi
fi

DEVICE_INFO="$DEVICE_TO_MOUNT"
log_msg "Znaleziono urządzenie: $DEVICE_INFO"

# Sprawdzenie, czy punkt montowania znajduje się w wyjściu komendy mount
if ! mount | grep -q "$MOUNT_POINT"; then
    log_msg "Dysk $DEVICE_INFO nie jest podmontowany. Próba montowania..."
    
    # Sprawdź czy katalog montowania istnieje
    if [ ! -d "$MOUNT_POINT" ]; then
        log_msg "Tworzenie katalogu $MOUNT_POINT..."
        sudo mkdir -p "$MOUNT_POINT"
    fi
    
    # Sprawdź stan dysku przed montowaniem
    if ! check_disk_health "$DEVICE_TO_MOUNT"; then
        log_msg "OSTRZEŻENIE: Problemy z dyskiem przed montowaniem"
    fi
    
    # Użycie 'mount' z prawami roota
    sudo mount "$DEVICE_TO_MOUNT" "$MOUNT_POINT"

    # Sprawdzenie, czy montowanie się powiodło
    if [ $? -eq 0 ]; then
        log_msg "Montowanie $DEVICE_INFO do $MOUNT_POINT zakończone sukcesem."
        
        # Sprawdź stan dysku po montowaniu
        check_disk_health "$DEVICE_TO_MOUNT"
        
        # Dodatkowa weryfikacja
        if [ -d "$MOUNT_POINT" ] && [ "$(ls -A "$MOUNT_POINT" 2>/dev/null | wc -l)" -gt 0 ]; then
            log_msg "Weryfikacja: Dysk zawiera $(ls -A "$MOUNT_POINT" 2>/dev/null | wc -l) plików/katalogów"
        else
            log_msg "OSTRZEŻENIE: Dysk wydaje się pusty lub niedostępny"
        fi
    else
        log_msg "BŁĄD! Montowanie $DEVICE_INFO do $MOUNT_POINT nie powiodło się."
        log_msg "Ostatnia próba odzyskania..."
        
        # Ostatnia próba odzyskania
        if recover_usb_storage; then
            sleep 3
            NEW_DEVICE=$(find_usb_disk)
            if [ -n "$NEW_DEVICE" ]; then
                log_msg "Ponowna próba montowania z $NEW_DEVICE"
                sudo mount "$NEW_DEVICE" "$MOUNT_POINT" && log_msg "Montowanie po odzyskaniu: SUKCES" || log_msg "Montowanie po odzyskaniu: BŁĄD"
            fi
        fi
    fi
else
    log_msg "Dysk jest już podmontowany w $MOUNT_POINT. Sprawdzanie stanu..."
    
    # Sprawdź stan zamontowanego dysku
    MOUNTED_DEVICE=$(mount | grep "$MOUNT_POINT" | awk '{print $1}' | head -1)
    if [ -n "$MOUNTED_DEVICE" ]; then
        check_disk_health "$MOUNTED_DEVICE"
        log_msg "Stan dysku: OK, zamontowany jako $MOUNTED_DEVICE"
    fi
fi