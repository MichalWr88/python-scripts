#!/bin/bash

# Skrypt do debugowania problemów z montowaniem USB

echo "=== DEBUGOWANIE MONTOWANIA USB ==="
echo "Data: $(date)"
echo

# Załaduj funkcje z głównego skryptu
source "./mount-disk-usb.cron.sh"

UUID="a4908213-f21d-41e7-b6e3-d1e1342fd1a9"
DEVICE="/dev/sdb1"
MOUNT_POINT="/mnt/usb1"

echo "=== 1. Sprawdzenie obecnego stanu ==="
mount | grep "$MOUNT_POINT" && echo "Dysk już zamontowany" || echo "Dysk nie zamontowany"
echo

echo "=== 2. Test uprawnień użytkownika ==="
id
groups
echo

echo "=== 3. Test sudo ==="
sudo -l | head -5
echo

echo "=== 4. Sprawdzenie UUID ==="
sudo blkid | grep "$UUID"
echo

echo "=== 5. Test montowania ręcznego ==="
if mount | grep -q "$MOUNT_POINT"; then
    echo "Demontowanie obecnego dysku..."
    sudo umount "$MOUNT_POINT" 2>&1
fi

echo "Próba montowania przez UUID:"
sudo mount "UUID=$UUID" "$MOUNT_POINT" 2>&1
MOUNT_STATUS=$?
echo "Status: $MOUNT_STATUS"

if [ $MOUNT_STATUS -eq 0 ]; then
    echo "✓ Montowanie przez UUID działa!"
    ls -la "$MOUNT_POINT" | head -5
else
    echo "✗ Montowanie przez UUID nie działa"
    
    echo "Próba montowania przez urządzenie:"
    sudo mount "$DEVICE" "$MOUNT_POINT" 2>&1
    MOUNT_STATUS2=$?
    echo "Status: $MOUNT_STATUS2"
    
    if [ $MOUNT_STATUS2 -eq 0 ]; then
        echo "✓ Montowanie przez urządzenie działa!"
        ls -la "$MOUNT_POINT" | head -5
    else
        echo "✗ Montowanie przez urządzenie też nie działa"
    fi
fi
echo

echo "=== 6. Porównanie z Webmin ==="
echo "Webmin prawdopodobnie używa:"
echo "- Pełnych uprawnień root (nie sudo)"
echo "- Innych opcji montowania"
echo "- Sprawdź /var/log/syslog dla szczegółów"
echo

echo "=== 7. Test praw dostępu ==="
echo "Uprawnienia do /mnt/usb1:"
ls -ld "$MOUNT_POINT" 2>/dev/null || echo "Katalog nie istnieje"

echo "Uprawnienia do urządzenia:"
ls -l "$DEVICE" 2>/dev/null || echo "Urządzenie nie istnieje"
echo

echo "=== 8. Test jako prawdziwy root ==="
echo "Uruchom to jako root (nie sudo):"
echo "sudo su -"
echo "mount UUID=$UUID $MOUNT_POINT"
echo

echo "=== 9. Sprawdzenie logów systemowych ==="
echo "Ostatnie wpisy dotyczące mount/USB:"
sudo dmesg | tail -10 | grep -i -E "(usb|mount|sdb)" || echo "Brak ostatnich wpisów"
echo

echo "=== 10. Test funkcji skryptu ==="
debug_mount_issues "$DEVICE" "$MOUNT_POINT"