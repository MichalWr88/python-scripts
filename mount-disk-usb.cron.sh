#!/bin/bash

# Punkt montowania
MOUNT_POINT="/mnt/usb1"
# Urządzenie blokowe
DEVICE="/dev/sde1"

# Sprawdzenie, czy punkt montowania znajduje się w wyjściu komendy mount
if ! mount | grep -q "$MOUNT_POINT"; then
    echo "$(date): Dysk $DEVICE nie jest podmontowany. Próba montowania..."
    # Użycie 'mount' z prawami roota
    /usr/bin/mount "$DEVICE" "$MOUNT_POINT"

    # Sprawdzenie, czy montowanie się powiodło
    if [ $? -eq 0 ]; then
        echo "$(date): Montowanie $DEVICE do $MOUNT_POINT zakończone sukcesem."
    else
        echo "$(date): BŁĄD! Montowanie $DEVICE do $MOUNT_POINT nie powiodło się."
    fi
else
    echo "$(date): Dysk $DEVICE jest już podmontowany. Pomijanie."
fi