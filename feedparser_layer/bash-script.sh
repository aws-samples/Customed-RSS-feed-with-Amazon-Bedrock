#!/bin/bash

python -m venv venv

# Ensure we're in the virtual environment
source venv/bin/activate

# Install or upgrade the required packages
pip install -r requirements.txt

# Create a temporary directory for our layer
mkdir -p python/lib/python3.12/site-packages

# Copy the installed packages to our layer directory
cp -r venv/lib/python3.12/site-packages/* python/lib/python3.12/site-packages/

# Create the zip file
zip -r ../feedparser-layer.zip python

# Clean up
rm -rf python

deactivate
