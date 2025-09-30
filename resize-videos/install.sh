#!/bin/bash

# Skrypt instalacyjny FFmpeg dla Debian/Ubuntu

set -e  # przerwij skrypt przy błędzie

echo "Aktualizacja listy pakietów..."
sudo apt-get update

echo "Instalacja pakietu ffmpeg..."
sudo apt-get install -y ffmpeg

echo "Sprawdzanie wersji zainstalowanego ffmpeg..."
if command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg zainstalowany pomyślnie."
    ffmpeg -version | head -n 1
else
    echo "Błąd: ffmpeg nie jest dostępny po instalacji."
    exit 1
fi

echo "Instalacja zakończona."