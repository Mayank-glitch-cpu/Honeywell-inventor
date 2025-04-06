#!/bin/bash

# Set up virtual environment
echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Check if .env file exists and load it
if [ -f .env ]; then
    echo "Loading environment variables..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "No .env file found. Using hard-coded credentials."
fi

# Hard code AWS credentials (these will override any from .env)
echo "Setting AWS credentials..."
export AWS_ACCESS_KEY_ID=AKIA46ZDFHBNNFSQQG4C
export AWS_SECRET_ACCESS_KEY=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
export AWS_DEFAULT_REGION=us-east-1

# Verify AWS credentials - making sure the AWS CLI is installed first
echo "Verifying AWS credentials..."
if ! pip list | grep -q "awscli"; then
    echo "Installing AWS CLI..."
    pip install awscli
fi

# Use python to verify credentials to ensure we're using the same environment 
echo "Verifying credentials with boto3..."
python -c "
import boto3
try:
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    print(f'Authenticated as: {identity[\"Arn\"]}')
except Exception as e:
    print(f'Error: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "Error: AWS credentials not properly configured!"
    exit 1
fi

# Run the TwinMaker script
echo "Running TwinMaker workspace creator..."
python twin-maker-script.py

# Deactivate virtual environment
deactivate