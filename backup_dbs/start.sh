#!/bin/bash

# Check if a Python file name is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <python_file>"
  exit 1
fi

PYTHON_FILE=$1

# Check if the virtual environment directory exists
if [ ! -d "venv" ]; then
  echo "Virtual environment not found. Please run init.sh first."
  exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Run the specified Python file with all additional arguments
shift # Remove the first argument (python file name)
python $PYTHON_FILE "$@"

# Deactivate virtual environment
deactivate