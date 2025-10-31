#!/bin/bash

# Demo skryptu odzyskiwania USB - pokazuje główne funkcje

echo "=== DEMO ODZYSKIWANIA USB ==="
echo "Ten skrypt demonstruje mechanizmy odzyskiwania dysku USB"
echo

# Załaduj główne funkcje
source "./mount-disk-usb.cron.sh"

# Funkcja menu
show_menu() {
    echo "Wybierz opcję:"
    echo "1. Pokaż dostępne urządzenia USB"
    echo "2. Znajdź dysk USB"
    echo "3. Sprawdź zdrowie dysku"
    echo "4. Wykonaj procedurę odzyskiwania"
    echo "5. Reset konkretnego urządzenia USB"
    echo "6. Sprawdź punkt montowania"
    echo "7. Pełny test systemu"
    echo "0. Wyjście"
    echo
    read -p "Wprowadź wybór [0-7]: " choice
}

# Główna pętla
while true; do
    show_menu
    
    case $choice in
        1)
            echo "=== Dostępne urządzenia USB ==="
            show_usb_devices
            echo
            ;;
        2)
            echo "=== Wyszukiwanie dysku USB ==="
            DEVICE=$(find_usb_disk)
            if [ -n "$DEVICE" ]; then
                log_msg "Znaleziono dysk: $DEVICE"
            else
                log_msg "Nie znaleziono dysku USB"
            fi
            echo
            ;;
        3)
            echo "=== Sprawdzenie zdrowia dysku ==="
            read -p "Podaj ścieżkę do dysku (lub Enter dla automatycznego): " manual_device
            if [ -z "$manual_device" ]; then
                DEVICE=$(find_usb_disk)
                if [ -z "$DEVICE" ]; then
                    log_msg "Nie znaleziono dysku do sprawdzenia"
                    continue
                fi
            else
                DEVICE="$manual_device"
            fi
            
            log_msg "Sprawdzanie zdrowia: $DEVICE"
            if check_disk_health "$DEVICE"; then
                log_msg "Dysk jest w dobrym stanie!"
            else
                log_msg "Wykryto problemy z dyskiem!"
            fi
            echo
            ;;
        4)
            echo "=== Procedura odzyskiwania USB ==="
            log_msg "Uwaga: Ta operacja może chwilowo odłączyć urządzenia USB"
            read -p "Kontynuować? (y/N): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                if recover_usb_storage; then
                    log_msg "Procedura odzyskiwania zakończona sukcesem"
                else
                    log_msg "Procedura odzyskiwania nie powiodła się"
                fi
            else
                log_msg "Operacja anulowana"
            fi
            echo
            ;;
        5)
            echo "=== Reset urządzenia USB ==="
            echo "Dostępne urządzenia:"
            lsusb | grep -E "(174c:55aa|0781:5583)" || echo "Brak znanych urządzeń"
            read -p "Podaj ID urządzenia (vendor:product, np. 174c:55aa): " device_id
            if [ -n "$device_id" ]; then
                if reset_usb_device "$device_id"; then
                    log_msg "Reset urządzenia $device_id zakończony"
                else
                    log_msg "Nie udało się zresetować urządzenia $device_id"
                fi
            fi
            echo
            ;;
        6)
            echo "=== Sprawdzenie punktu montowania ==="
            log_msg "Punkt montowania: $MOUNT_POINT"
            if mount | grep -q "$MOUNT_POINT"; then
                MOUNTED_DEV=$(mount | grep "$MOUNT_POINT" | awk '{print $1}')
                log_msg "Zamontowane urządzenie: $MOUNTED_DEV"
                
                if [ -d "$MOUNT_POINT" ]; then
                    FILE_COUNT=$(ls -A "$MOUNT_POINT" 2>/dev/null | wc -l)
                    log_msg "Liczba elementów: $FILE_COUNT"
                    
                    log_msg "Przykładowa zawartość:"
                    ls -la "$MOUNT_POINT" | head -10 | while read line; do
                        log_msg "  $line"
                    done
                fi
            else
                log_msg "Punkt montowania jest wolny"
            fi
            echo
            ;;
        7)
            echo "=== Pełny test systemu ==="
            log_msg "Rozpoczynanie pełnego testu..."
            
            # Test 1: Urządzenia
            log_msg "1. Sprawdzanie urządzeń USB..."
            show_usb_devices
            
            # Test 2: Wyszukiwanie
            log_msg "2. Wyszukiwanie dysku..."
            DEVICE=$(find_usb_disk)
            if [ -n "$DEVICE" ]; then
                log_msg "Znaleziony dysk: $DEVICE"
                
                # Test 3: Zdrowie
                log_msg "3. Test zdrowia dysku..."
                check_disk_health "$DEVICE"
            else
                log_msg "Brak dysku - test odzyskiwania..."
                recover_usb_storage
            fi
            
            # Test 4: Montowanie
            log_msg "4. Sprawdzenie montowania..."
            if mount | grep -q "$MOUNT_POINT"; then
                log_msg "Dysk zamontowany poprawnie"
            else
                log_msg "Dysk nie jest zamontowany"
            fi
            
            log_msg "Pełny test zakończony"
            echo
            ;;
        0)
            log_msg "Zakończenie demo"
            break
            ;;
        *)
            echo "Nieprawidłowy wybór. Spróbuj ponownie."
            echo
            ;;
    esac
    
    read -p "Naciśnij Enter aby kontynuować..."
    clear
done