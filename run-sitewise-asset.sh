#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}==============================================${NC}"
echo -e "${CYAN}     AWS IoT SiteWise Asset Creator          ${NC}"
echo -e "${CYAN}==============================================${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required commands
if ! command_exists python3; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.${NC}"
    exit 1
fi

# Set the virtual environment path - use the same one as the model script
VENV_PATH="venv-sitewise"

# Check if virtual environment exists, create if not
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Setting up Python virtual environment at ${VENV_PATH}...${NC}"
    python3 -m venv "$VENV_PATH"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment. Please ensure python3-venv is installed.${NC}"
        exit 1
    fi
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"

# Install required packages in the virtual environment
echo -e "${YELLOW}Checking required packages...${NC}"
if ! "$VENV_PATH/bin/python" -c "import boto3" &>/dev/null; then
    echo -e "${YELLOW}boto3 not found, installing it...${NC}"
    "$VENV_PATH/bin/pip" install boto3
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install boto3. Please install it manually.${NC}"
        deactivate
        exit 1
    fi
fi

# Check AWS credentials
echo -e "${YELLOW}Checking AWS credentials...${NC}"
if ! "$VENV_PATH/bin/python" -c "import boto3; boto3.client('sts').get_caller_identity()" &>/dev/null; then
    echo -e "${RED}Error: AWS credentials not found or not properly configured!${NC}"
    echo -e "Please configure your AWS credentials using one of the following methods:"
    echo -e "1. Run ${CYAN}aws configure${NC}"
    echo -e "2. Set environment variables ${CYAN}AWS_ACCESS_KEY_ID${NC} and ${CYAN}AWS_SECRET_ACCESS_KEY${NC}"
    echo -e "3. Place credentials in ${CYAN}~/.aws/credentials${NC}"
    
    # Check if rootkey.csv exists and offer to use it
    if [ -f "rootkey.csv" ]; then
        echo -e "\n${YELLOW}Found rootkey.csv in the current directory.${NC}"
        read -p "Do you want to configure AWS credentials using this file? (y/n): " use_rootkey
        
        if [[ "$use_rootkey" == "y" || "$use_rootkey" == "Y" ]]; then
            # Extract credentials from rootkey.csv
            AWS_ACCESS_KEY_ID=$(grep -o 'AWSAccessKeyId=.*' rootkey.csv | cut -d= -f2)
            AWS_SECRET_ACCESS_KEY=$(grep -o 'AWSSecretKey=.*' rootkey.csv | cut -d= -f2)
            
            # Export credentials for this session
            export AWS_ACCESS_KEY_ID
            export AWS_SECRET_ACCESS_KEY
            
            echo -e "${GREEN}Credentials from rootkey.csv have been temporarily configured for this session.${NC}"
        else
            echo -e "${YELLOW}Exiting. Please configure AWS credentials before running this script.${NC}"
            deactivate
            exit 1
        fi
    else
        echo -e "${YELLOW}Exiting. Please configure AWS credentials before running this script.${NC}"
        deactivate
        exit 1
    fi
fi

# Ask for AWS region if not set
AWS_REGION=$("$VENV_PATH/bin/python" -c "import boto3; import os; print(boto3.session.Session().region_name or os.environ.get('AWS_REGION', ''))" 2>/dev/null)
if [ -z "$AWS_REGION" ]; then
    echo -e "${YELLOW}AWS region is not set.${NC}"
    read -p "Enter the AWS region to use (e.g., us-east-1): " input_region
    
    export AWS_REGION=$input_region
    echo -e "${GREEN}Using AWS region: ${CYAN}$AWS_REGION${NC}"
else
    echo -e "${GREEN}Using AWS region: ${CYAN}$AWS_REGION${NC}"
fi

# Check if the IoT SiteWise asset creator script exists
if [ ! -f "create-iotsitewise-asset.py" ]; then
    echo -e "${RED}Error: create-iotsitewise-asset.py not found in the current directory!${NC}"
    deactivate
    exit 1
fi

# Make the script executable if it isn't already
if [ ! -x "create-iotsitewise-asset.py" ]; then
    chmod +x create-iotsitewise-asset.py
fi

# Get the model ID either from command line argument or prompt
MODEL_ID=""
if [ "$#" -ge 1 ]; then
    MODEL_ID="$1"
    echo -e "${GREEN}Using provided model ID: ${CYAN}$MODEL_ID${NC}"
else
    echo -e "${YELLOW}No model ID provided as an argument.${NC}"
    
    # Try to list available models to help the user
    echo -e "${YELLOW}Attempting to list available IoT SiteWise models...${NC}"
    echo -e "${CYAN}This may take a few seconds...${NC}"
    
    MODEL_LIST=$("$VENV_PATH/bin/python" -c "
import boto3
try:
    client = boto3.client('iotsitewise')
    response = client.list_asset_models(maxResults=10)
    print('Available models:')
    for model in response.get('assetModelSummaries', []):
        print(f\"- {model['name']}: {model['id']}\")
except Exception as e:
    print(f'Error listing models: {e}')
" 2>/dev/null)
    
    echo -e "${CYAN}$MODEL_LIST${NC}"
    echo ""
    
    read -p "Enter the model ID to use: " MODEL_ID
    
    if [ -z "$MODEL_ID" ]; then
        echo -e "${RED}No model ID provided. Exiting.${NC}"
        deactivate
        exit 1
    fi
fi

# Explain what will happen
echo -e "\n${CYAN}This script will create a new IoT SiteWise asset based on the model with ID ${YELLOW}$MODEL_ID${NC}"
echo -e "The asset will be assigned a unique serial number automatically."

# Ask for confirmation
echo ""
read -p "Do you want to proceed? (y/n): " confirm

if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    echo -e "\n${GREEN}Creating IoT SiteWise asset...${NC}"
    
    # Run the IoT SiteWise asset creation script using Python from the virtual environment
    "$VENV_PATH/bin/python" create-iotsitewise-asset.py "$MODEL_ID"
    
    # Check if the script executed successfully
    if [ $? -eq 0 ]; then
        echo -e "\n${GREEN}Asset creation completed.${NC}"
    else
        echo -e "\n${RED}The script encountered an error during execution.${NC}"
    fi
else
    echo -e "${YELLOW}Asset creation cancelled.${NC}"
fi

# Deactivate virtual environment
deactivate

echo -e "${CYAN}==============================================${NC}"