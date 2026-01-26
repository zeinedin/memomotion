#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Start the application
python -m uvicorn main:app --host 0.0.0.0 --port 8000
