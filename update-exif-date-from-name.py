import argparse
import os
from datetime import datetime
import re
from PIL import Image
from PIL.ExifTags import TAGS
import piexif
from typing import Optional

def extract_date_from_filename(filename, filepath=None):
    # Define regex patterns to match dates in the filename
    patterns = [
        # Format: 20151101_145717
        (r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]),
                            int(m[3]), int(m[4]), int(m[5]))),

        # Format: 2017-01-14 18.31.48
        (r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]),
                            int(m[3]), int(m[4]), int(m[5]))),

        # Format: 2014-07-11 18.49.29-2 (with suffix)
        (r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})(?:-\d+)?',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]),
                            int(m[3]), int(m[4]), int(m[5]))),

        # Format: LrMobile0101-2016-024520622738581791_20160218185112909 (extract date from end)
        (r'LrMobile.*_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\d{3}',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]),
                            int(m[3]), int(m[4]), int(m[5]))),

        # Format: lv_7397050064964717829_20240921213845 (extract date from end)
        (r'lv_\d+_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]),
                            int(m[3]), int(m[4]), int(m[5]))),

        # Format: PicsArt_1433450401860 (PicsArt with timestamp)
        (r'PicsArt_(\d{13})',
         lambda m: datetime.fromtimestamp(int(m[0]) / 1000)),

        # Format: afterfocus_1344548876254 (afterfocus with timestamp)
        (r'afterfocus_(\d{13})',
         lambda m: datetime.fromtimestamp(int(m[0]) / 1000)),

        # Format: ePicsArt_1400094221136 (ePicsArt with timestamp)
        (r'ePicsArt_(\d{13})',
         lambda m: datetime.fromtimestamp(int(m[0]) / 1000)),

        # Format: received_1050084378400782 (received with timestamp - handle large numbers)
        (r'received_(\d{13})',
         lambda m: datetime.fromtimestamp(int(m[0]) / 1000)),

        # Format: Unix timestamp 13 digits (milliseconds since epoch)
        (r'(\d{13})',
         lambda m: datetime.fromtimestamp(int(m[0]) / 1000)),

        # Format: YYYY-MM-DD
        (r'(\d{4})-(\d{2})-(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]))),

        # Format: YYYYMMDD
        (r'(\d{4})(\d{2})(\d{2})',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]))),

        # Format: DD-MM-YYYY
        (r'(\d{2})-(\d{2})-(\d{4})',
         lambda m: datetime(int(m[2]), int(m[1]), int(m[0]))),

        # Format: DDMMYYYY
        (r'(\d{2})(\d{2})(\d{4})',
         lambda m: datetime(int(m[2]), int(m[1]), int(m[0]))),

        # Format: {prefix} 20151101_145717
        (r'.*?(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2}).*',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]),
                            int(m[3]), int(m[4]), int(m[5]))),

        # Format: IMG-20230502-WA0022
        (r'.*?(\d{4})(\d{2})(\d{2}).*',
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2]))),

        # Format: N_zoo_MM_YYYY (e.g., 19_zoo_07_2021.jpg)
        (r'(\d+)_zoo_(\d{2})_(\d{4})',
         lambda m: datetime(int(m[2]), int(m[1]), 1)),

        # Format: zoo_DD_MM_YYYY (e.g., zoo_20_04_2019-72.webp)
        (r'zoo_(\d{2})_(\d{2})_(\d{4})',
         lambda m: datetime(int(m[2]), int(m[1]), int(m[0]))),

        # Format: Files in folders with dates like "moje urodziny 07.03.2009/" or "Chrzest Marcina 16.04.2016/"
        (r'.*(\d{2})\.(\d{2})\.(\d{4})/',
         lambda m: datetime(int(m[2]), int(m[1]), int(m[0])))
    ]
    
    # Check patterns against filename first
    for pattern, date_func in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                date = date_func(match.groups())
                return date
            except ValueError:
                continue
    
    # If no match in filename and filepath is provided, check full path
    if filepath:
        for pattern, date_func in patterns:
            match = re.search(pattern, filepath)
            if match:
                try:
                    date = date_func(match.groups())
                    return date
                except ValueError:
                    continue
    
    raise ValueError("Invalid date format")

def get_exif_date(image_path: str) -> Optional[datetime]:
    """Extract creation date from image EXIF metadata."""
    try:
        image = Image.open(image_path)
        exif = image.getexif()
        if not exif:
            return None

        # Look for different date fields in EXIF
        date_fields = [
            36867,  # DateTimeOriginal
            36868,  # DateTimeDigitized
            306,    # DateTime
        ]

        for field in date_fields:
            if field in exif:
                try:
                    date_str = exif[field]
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                except (ValueError, TypeError):
                    continue

        return None

    except Exception as e:
        print(f"Error reading EXIF from {image_path}: {str(e)}")
        return None

def is_supported_image_format(file_path: str) -> bool:
    """Check if the file is a supported image format for EXIF processing."""
    supported_extensions = {'.jpg', '.jpeg', '.tiff', '.tif', '.webp', '.png', '.dng'}
    file_extension = os.path.splitext(file_path)[1].lower()
    return file_extension in supported_extensions

def set_exif_date(image_path: str, date: datetime) -> bool:
    """Set the creation date in the image EXIF metadata."""
    
    # Check if the file exists and we have write permissions
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return False
    
    if not os.access(image_path, os.W_OK):
        print(f"No write permission for: {image_path}")
        return False
    
    try:
        # First try to load existing EXIF data
        try:
            exif_dict = piexif.load(image_path)
        except Exception:
            # If loading fails, create a minimal EXIF structure
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        
        # Ensure the Exif IFD exists
        if 'Exif' not in exif_dict or exif_dict['Exif'] is None:
            exif_dict['Exif'] = {}
        
        # Convert datetime to EXIF format
        exif_date_str = date.strftime('%Y:%m:%d %H:%M:%S')
        
        # Set the date fields
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date_str
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date_str
        
        # Handle existing problematic EXIF fields by removing them
        problematic_fields = [37121, 37500, 37510]  # Common problematic fields
        for field in problematic_fields:
            if field in exif_dict['Exif']:
                del exif_dict['Exif'][field]
        
        # Try to dump and insert the EXIF data
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        return True
        
    except PermissionError:
        print(f"Permission denied: {image_path}")
        return False
    except OSError as e:
        if e.errno == 13:  # Permission denied
            print(f"Permission denied: {image_path}")
        else:
            print(f"OS Error for {image_path}: {str(e)}")
        return False
    except Exception as e:
        # If all else fails, try with a minimal EXIF structure
        try:
            minimal_exif = {
                "0th": {},
                "Exif": {
                    piexif.ExifIFD.DateTimeOriginal: date.strftime('%Y:%m:%d %H:%M:%S'),
                    piexif.ExifIFD.DateTimeDigitized: date.strftime('%Y:%m:%d %H:%M:%S')
                },
                "GPS": {},
                "1st": {},
                "thumbnail": None
            }
            exif_bytes = piexif.dump(minimal_exif)
            piexif.insert(exif_bytes, image_path)
            return True
        except (PermissionError, OSError) as e2:
            if hasattr(e2, 'errno') and e2.errno == 13:
                print(f"Permission denied: {image_path}")
            else:
                print(f"Error setting EXIF date for {image_path}: {str(e2)}")
            return False
        except Exception as e2:
            print(f"Error setting EXIF date for {image_path}: {str(e2)}")
            return False

# Function to process images in a folder and its subfolders
def process_images(folder_path, skip_permission_errors=False, dry_run=False):
    permission_errors = []
    processed_count = 0
    updated_count = 0
    skipped_count = 0
    
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            
            # Skip unsupported file formats
            if not is_supported_image_format(file_path):
                continue
            
            processed_count += 1
            
            try:
                # Extract date from filename and full path
                filename_date = extract_date_from_filename(filename, file_path)
            except ValueError:
                print(f"Skipping file {filename}: invalid date format")
                skipped_count += 1
                # Get the current date
                current_date = datetime.now().strftime("%Y-%m-%d")
                # Open the file in append mode and write the path
                if not dry_run:
                    with open(f"{current_date}.txt", "a") as f:
                        f.write(f"{file_path}\n")
                continue

            # Check write permissions before attempting to read EXIF
            if not os.access(file_path, os.W_OK):
                if skip_permission_errors:
                    print(f"Skipping (no write permission): {filename}")
                    permission_errors.append(file_path)
                    skipped_count += 1
                    continue
                else:
                    print(f"Warning: No write permission for {filename}")
                    permission_errors.append(file_path)

            # Get EXIF date
            exif_date = get_exif_date(file_path)
            # Compare dates and update if necessary
            if not exif_date or exif_date != filename_date:
                if dry_run:
                    print(f"Would update EXIF date for {filename}: {filename_date}")
                    updated_count += 1
                else:
                    print(f"Updating EXIF date for {filename}")
                    if set_exif_date(file_path, filename_date):
                        print(f"Successfully updated EXIF date for {filename}")
                        updated_count += 1
                    else:
                        print(f"Failed to update EXIF date for {filename}")
                        skipped_count += 1
            else:
                print(f"EXIF date already correct for {filename}")
    
    # Print summary
    print(f"\n--- Processing Summary ---")
    print(f"Files processed: {processed_count}")
    if dry_run:
        print(f"Files that would be updated: {updated_count}")
    else:
        print(f"Files updated: {updated_count}")
    print(f"Files skipped: {skipped_count}")
    print(f"Permission errors: {len(permission_errors)}")
    
    if permission_errors:
        print(f"\nFiles with permission errors:")
        for file_path in permission_errors[:10]:  # Show first 10
            print(f"  {file_path}")
        if len(permission_errors) > 10:
            print(f"  ... and {len(permission_errors) - 10} more")
        print(f"\nTo fix permission errors, try:")
        print(f"  sudo chmod 664 <file>  # For individual files")
        print(f"  sudo chmod -R 664 <directory>  # For entire directory")
        print(f"  Or run this script with sudo (not recommended)")
        
    return updated_count, skipped_count, len(permission_errors)

# Example usage
if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Process images in a folder and update EXIF dates from filenames.")
    parser.add_argument('folder_path', type=str, help="Path to the folder containing the images")
    parser.add_argument('--skip-permission-errors', action='store_true', 
                        help="Skip files with permission errors instead of warning about them")
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would be done without actually modifying files")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE: No files will be modified")
    
    updated, skipped, permission_errors = process_images(args.folder_path, args.skip_permission_errors, args.dry_run)
    
    if permission_errors > 0:
        print(f"\nNote: {permission_errors} files had permission errors.")
        print("You may need to run with appropriate permissions or change file permissions.")