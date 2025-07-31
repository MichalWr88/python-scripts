#!/bin/bash


# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install necessary packages (if any)
# Uncomment and add packages if needed
# pip install <package_name>
pip install -r requirements.txt
# Create requirements file
pip freeze > requirements.txt

echo "Project initialized with virtual environment."