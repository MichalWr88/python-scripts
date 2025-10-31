#!/bin/bash

# Test skryptu odzyskiwania USB
# Tento skrypt testuje różne scenariusze awarii i odzyskiwania dysku USB

# Załaduj funkcje z głównego skryptu
source "./mount-disk-usb.cron.sh"

echo "=== TEST SKRYPTU ODZYSKIWANIA USB ==="
echo "Data: $(date)"
echo

# Test 1: Sprawdzenie obecnego stanu
echo "=== TEST 1: Sprawdzenie obecnego stanu ==="
log_msg "Sprawdzanie obecnego stanu systemu..."
show_usb_devices
echo

# Test 2: Wyszukiwanie dysku USB
echo "=== TEST 2: Wyszukiwanie dysku USB ==="
log_msg "Próba znalezienia dysku USB..."
FOUND_DEVICE=$(find_usb_disk)
if [ -n "$FOUND_DEVICE" ]; then
    log_msg "Znaleziono dysk: $FOUND_DEVICE"
    
    # Test sprawdzenia zdrowia
    echo "=== TEST 3: Sprawdzenie zdrowia dysku ==="
    if check_disk_health "$FOUND_DEVICE"; then
        log_msg "Dysk jest w dobrym stanie"
    else
        log_msg "Wykryto problemy z dyskiem"
    fi
else
    log_msg "Nie znaleziono dysku USB"
fi
echo

# Test 4: Symulacja odzyskiwania
echo "=== TEST 4: Test procedury odzyskiwania ==="
log_msg "Testowanie procedury odzyskiwania USB..."
if recover_usb_storage; then
    log_msg "Procedura odzyskiwania zakończona"
    sleep 5
    
    # Sprawdź ponownie
    NEW_DEVICE=$(find_usb_disk)
    if [ -n "$NEW_DEVICE" ]; then
        log_msg "Po odzyskaniu znaleziono: $NEW_DEVICE"
    else
        log_msg "Po odzyskaniu nadal brak dysku"
    fi
else
    log_msg "Procedura odzyskiwania nie powiodła się"
fi
echo

# Test 5: Sprawdzenie punktu montowania
echo "=== TEST 5: Sprawdzenie punktu montowania ==="
if mount | grep -q "$MOUNT_POINT"; then
    MOUNTED_DEV=$(mount | grep "$MOUNT_POINT" | awk '{print $1}')
    log_msg "Punkt montowania $MOUNT_POINT jest zajęty przez: $MOUNTED_DEV"
    
    # Sprawdź dostępność plików
    if [ -d "$MOUNT_POINT" ]; then
        FILE_COUNT=$(ls -A "$MOUNT_POINT" 2>/dev/null | wc -l)
        log_msg "Liczba plików/katalogów: $FILE_COUNT"
        
        # Test dostępu do plików
        if timeout 5 ls "$MOUNT_POINT" >/dev/null 2>&1; then
            log_msg "Dostęp do plików: OK"
        else
            log_msg "Dostęp do plików: BŁĄD"
        fi
    fi
else
    log_msg "Punkt montowania $MOUNT_POINT jest wolny"
fi
echo

# Test 6: Informacje o systemie USB
echo "=== TEST 6: Informacje systemowe ==="
log_msg "Moduły USB:"
lsmod | grep -E "(usb|storage)" | while read line; do
    log_msg "  $line"
done

log_msg "Urządzenia w /dev:"
ls -la /dev/sd* 2>/dev/null | while read line; do
    log_msg "  $line"
done
echo

echo "=== KONIEC TESTÓW ==="
echo "Sprawdź log w: $LOG_FILE"