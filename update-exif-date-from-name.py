import argparse
import os
from datetime import datetime
import re
from PIL import Image
from PIL.ExifTags import TAGS
import piexif
from typing import Optional

def extract_date_from_filename(filename):
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
         lambda m: datetime(int(m[0]), int(m[1]), int(m[2])))
    ]
    
    for pattern, date_func in patterns:
        match = re.search(pattern, filename)
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

def set_exif_date(image_path: str, date: datetime) -> bool:
    """Set the creation date in the image EXIF metadata."""
    try:
        exif_dict = piexif.load(image_path)
        exif_date_str = date.strftime('%Y:%m:%d %H:%M:%S')
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date_str
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date_str
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        return True
    except Exception as e:
        print(f"Error setting EXIF date for {image_path}: {str(e)}")
        return False

# Function to process images in a folder and its subfolders
def process_images(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                # Extract date from filename
                filename_date = extract_date_from_filename(filename)
            except ValueError:
                print(f"Skipping file {filename}: invalid date format")
                # Get the current date
                current_date = datetime.now().strftime("%Y-%m-%d")
                # Open the file in append mode and write the path
                with open(f"{current_date}.txt", "a") as f:
                    f.write(f"{file_path}\n")
                continue

            # Get EXIF date
            exif_date = get_exif_date(file_path)
            # Compare dates and update if necessary
            if not exif_date or exif_date != filename_date:
                print(f"Updating EXIF date for {filename}")
                if set_exif_date(file_path, filename_date):
                    print(f"Successfully updated EXIF date for {filename}")
                else:
                    print(f"Failed to update EXIF date for {filename}")

# Example usage
if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Process images in a folder and update EXIF dates from filenames.")
    parser.add_argument('folder_path', type=str, help="Path to the folder containing the images")
    args = parser.parse_args()
    process_images(args.folder_path)