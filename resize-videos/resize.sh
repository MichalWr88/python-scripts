#!/bin/bash

# Skrypt do rekursywnej konwersji plików video do MP4 z h264
# Zarządzanie plikami success.txt i errors.txt oraz katalogiem temporary
# Użycie: ./resize.sh /sciezka/do/folderu [opcje]
# Opcje:
#   -c, --crf VALUE     CRF (0-51, domyślnie 20)
#   -p, --preset VALUE  Preset (ultrafast,superfast,veryfast,faster,fast,medium,slow,slower,veryslow)
#   -b, --backup        Twórz kopie zapasowe zamiast nadpisywać
#   -v, --verbose       Szczegółowe logowanie
#   -h, --help          Pokaż pomoc

set -euo pipefail

# Domyślne ustawienia
DEFAULT_CRF=20
DEFAULT_PRESET="slow"
BACKUP_MODE=false
VERBOSE=false
SUPPORTED_FORMATS=("mp4" "avi" "mkv" "mov" "wmv" "flv" "webm" "m4v")

# Funkcja pomocy
show_help() {
    cat << EOF
Skrypt do konwersji plików video do MP4 z h264

Użycie: $0 <ścieżka_do_folderu> [opcje]

Opcje:
  -c, --crf VALUE     CRF (0-51, domyślnie $DEFAULT_CRF)
  -p, --preset VALUE  Preset FFmpeg (domyślnie $DEFAULT_PRESET)
  -b, --backup        Twórz kopie zapasowe zamiast nadpisywać
  -v, --verbose       Szczegółowe logowanie
  -h, --help          Pokaż tę pomoc

Obsługiwane formaty: ${SUPPORTED_FORMATS[*]}
EOF
}

# Funkcja logowania z timestampem
log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
}

# Sprawdzenie czy FFmpeg jest dostępny
check_ffmpeg() {
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log "ERROR" "FFmpeg nie jest zainstalowany. Uruchom install.sh aby go zainstalować."
        exit 1
    fi
    log "INFO" "FFmpeg znaleziony: $(ffmpeg -version | head -n1 | cut -d' ' -f3)"
}

# Sprawdzenie dostępnego miejsca na dysku
check_disk_space() {
    local file="$1"
    local file_size=$(stat -c%s "$file")
    local available_space=$(df "$(dirname "$file")" | awk 'NR==2 {print $4*1024}')
    
    if [ "$file_size" -gt "$available_space" ]; then
        log "ERROR" "Niewystarczające miejsce na dysku dla pliku: $file"
        return 1
    fi
    return 0
}

# Parsowanie argumentów
CRF=$DEFAULT_CRF
PRESET=$DEFAULT_PRESET
SRC_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--crf)
            CRF="$2"
            if ! [[ "$CRF" =~ ^[0-9]+$ ]] || [ "$CRF" -lt 0 ] || [ "$CRF" -gt 51 ]; then
                log "ERROR" "CRF musi być liczbą między 0 a 51"
                exit 1
            fi
            shift 2
            ;;
        -p|--preset)
            PRESET="$2"
            if ! [[ "$PRESET" =~ ^(ultrafast|superfast|veryfast|faster|fast|medium|slow|slower|veryslow)$ ]]; then
                log "ERROR" "Nieprawidłowy preset: $PRESET"
                exit 1
            fi
            shift 2
            ;;
        -b|--backup)
            BACKUP_MODE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            log "ERROR" "Nieznana opcja: $1"
            show_help
            exit 1
            ;;
        *)
            if [ -z "$SRC_DIR" ]; then
                SRC_DIR="$1"
            else
                log "ERROR" "Zbyt wiele argumentów"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# Sprawdzenie argumentu
if [ -z "$SRC_DIR" ]; then
    log "ERROR" "Nie podano ścieżki do folderu"
    show_help
    exit 1
fi

if [ ! -d "$SRC_DIR" ]; then
    log "ERROR" "Katalog nie istnieje: $SRC_DIR"
    exit 1
fi

# Sprawdzenie FFmpeg
check_ffmpeg

# Katalog, w którym jest skrypt (i gdzie będą success.txt, errors.txt oraz temporary)
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SUCCESS_FILE="$BASE_DIR/success.txt"
ERROR_FILE="$BASE_DIR/errors.txt"
LOG_FILE="$BASE_DIR/conversion.log"
TEMP_DIR="$BASE_DIR/temporary"

mkdir -p "$TEMP_DIR"
touch "$SUCCESS_FILE" "$ERROR_FILE" "$LOG_FILE"

log "INFO" "Rozpoczynanie konwersji w katalogu: $SRC_DIR"
log "INFO" "Ustawienia: CRF=$CRF, Preset=$PRESET, Backup=$BACKUP_MODE"

# Funkcja do sprawdzania, czy plik został już przetworzony
is_already_processed() {
    local filepath="$1"
    grep -Fxq "$filepath" "$SUCCESS_FILE" 2>/dev/null && return 0
    grep -Fxq "$filepath" "$ERROR_FILE" 2>/dev/null && return 0
    return 1
}

# Tworzenie wzorca find dla obsługiwanych formatów
create_find_pattern() {
    local pattern=""
    for fmt in "${SUPPORTED_FORMATS[@]}"; do
        if [ -n "$pattern" ]; then
            pattern="$pattern -o"
        fi
        pattern="$pattern -iname \"*.$fmt\""
    done
    echo "( $pattern )"
}

# Znajdź pierwszy plik video rekurencyjnie, który nie był przetworzony
FIND_PATTERN=$(create_find_pattern)
FILE_TO_PROCESS=$(find "$SRC_DIR" -type f \( $(eval echo "$FIND_PATTERN") \) -print0 |
while IFS= read -r -d '' file; do
    # absolutna ścieżka
    abs_path="$(readlink -f "$file")"
    if ! is_already_processed "$abs_path"; then
        echo "$abs_path"
        break
    fi
done)

if [ -z "$FILE_TO_PROCESS" ]; then
    log "INFO" "Brak nowych plików do przetworzenia."
    exit 0
fi

log "INFO" "Przetwarzam plik: $FILE_TO_PROCESS"

# Sprawdzenie dostępnego miejsca na dysku
if ! check_disk_space "$FILE_TO_PROCESS"; then
    log "ERROR" "Niewystarczające miejsce na dysku"
    echo "$FILE_TO_PROCESS" >> "$ERROR_FILE"
    exit 1
fi

# Nazwa pliku tymczasowego w katalogu temporary - unikalna, oparta na timestampie
BASENAME="$(basename "$FILE_TO_PROCESS")"
TIMESTAMP=$(date +%s)
TEMP_FILE="$TEMP_DIR/${BASENAME%.*}_${TIMESTAMP}_converted.mp4"

# Opcjonalna kopia zapasowa
if [ "$BACKUP_MODE" = true ]; then
    BACKUP_FILE="${FILE_TO_PROCESS}.backup"
    log "INFO" "Tworzenie kopii zapasowej: $BACKUP_FILE"
    cp "$FILE_TO_PROCESS" "$BACKUP_FILE"
fi

# Funkcja do usuwania pliku tymczasowego przy błędzie lub na koniec działania
cleanup() {
    if [ -f "$TEMP_FILE" ]; then
        log "INFO" "Usuwanie pliku tymczasowego: $TEMP_FILE"
        rm -f "$TEMP_FILE"
    fi
}

trap cleanup EXIT

# Przygotowanie opcji FFmpeg
FFMPEG_OPTS="-y -i"
if [ "$VERBOSE" = false ]; then
    FFMPEG_OPTS="$FFMPEG_OPTS \"$FILE_TO_PROCESS\" -c:v libx264 -preset $PRESET -crf $CRF -c:a copy \"$TEMP_FILE\" -hide_banner -loglevel error"
else
    FFMPEG_OPTS="$FFMPEG_OPTS \"$FILE_TO_PROCESS\" -c:v libx264 -preset $PRESET -crf $CRF -c:a copy \"$TEMP_FILE\" -hide_banner"
fi

log "INFO" "Rozpoczynanie konwersji z parametrami: preset=$PRESET, crf=$CRF"

# Konwersja przy pomocy ffmpeg
if [ "$VERBOSE" = true ]; then
    log "INFO" "Uruchamianie: ffmpeg $FFMPEG_OPTS"
    ffmpeg -y -i "$FILE_TO_PROCESS" -c:v libx264 -preset "$PRESET" -crf "$CRF" -c:a copy "$TEMP_FILE" -hide_banner
    RET_CODE=$?
else
    ffmpeg -y -i "$FILE_TO_PROCESS" -c:v libx264 -preset "$PRESET" -crf "$CRF" -c:a copy "$TEMP_FILE" -hide_banner -loglevel error 2>"$TEMP_DIR/ffmpeg_error.log"
    RET_CODE=$?
fi

if [ $RET_CODE -eq 0 ]; then
    # Sprawdzenie czy plik wynikowy jest poprawny
    if [ ! -f "$TEMP_FILE" ] || [ ! -s "$TEMP_FILE" ]; then
        log "ERROR" "Plik wynikowy jest pusty lub nie istnieje"
        echo "$FILE_TO_PROCESS" >> "$ERROR_FILE"
        exit 1
    fi
    
    # Porównanie rozmiarów plików
    ORIGINAL_SIZE=$(stat -c%s "$FILE_TO_PROCESS")
    NEW_SIZE=$(stat -c%s "$TEMP_FILE")
    COMPRESSION_RATIO=$(echo "scale=1; $NEW_SIZE * 100 / $ORIGINAL_SIZE" | bc -l 2>/dev/null || echo "N/A")
    
    # Sukces - bezpieczne nadpisanie oryginału
    mv "$TEMP_FILE" "$FILE_TO_PROCESS"
    echo "$FILE_TO_PROCESS" >> "$SUCCESS_FILE"
    
    log "INFO" "Plik przetworzony pomyślnie."
    log "INFO" "Rozmiar: $(numfmt --to=iec $ORIGINAL_SIZE) -> $(numfmt --to=iec $NEW_SIZE) (${COMPRESSION_RATIO}% oryginału)"
    
    # Logowanie do pliku
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $FILE_TO_PROCESS ($ORIGINAL_SIZE -> $NEW_SIZE bytes)" >> "$LOG_FILE"
else
    # Błąd - dopisz do errors.txt i zapisz szczegóły błędu
    echo "$FILE_TO_PROCESS" >> "$ERROR_FILE"
    
    if [ "$VERBOSE" = false ] && [ -f "$TEMP_DIR/ffmpeg_error.log" ]; then
        ERROR_MSG=$(cat "$TEMP_DIR/ffmpeg_error.log")
        log "ERROR" "Błąd FFmpeg: $ERROR_MSG"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $FILE_TO_PROCESS - $ERROR_MSG" >> "$LOG_FILE"
        rm -f "$TEMP_DIR/ffmpeg_error.log"
    else
        log "ERROR" "Błąd przetwarzania pliku. Kod błędu: $RET_CODE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $FILE_TO_PROCESS - FFmpeg exit code: $RET_CODE" >> "$LOG_FILE"
    fi
    
    exit 1
fi

# Usuwanie pułapki i pliku tymczasowego
trap - EXIT
if [ -f "$TEMP_FILE" ]; then
    rm -f "$TEMP_FILE"
fi

log "INFO" "Konwersja zakończona pomyślnie."