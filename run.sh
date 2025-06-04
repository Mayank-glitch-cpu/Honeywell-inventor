#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0m' # No Color

# Parse arguments
WORKSPACE_ID="CookieFactoryTwin"  # Default to CookieFactoryTwin
NON_INTERACTIVE=false

# Parse command line options
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --workspace-id)
      WORKSPACE_ID="$2"
      shift
      shift
      ;;
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      shift
      ;;
  esac
done

echo -e "${CYAN}====================================${NC}"
echo -e "${CYAN}AWS IoT TwinMaker Workspace Creator${NC}"
echo -e "${CYAN}====================================${NC}"
echo -e "${YELLOW}Creating workspace: ${WORKSPACE_ID}${NC}"

# Use the same virtual environment as master-setup.sh
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

# Install requirements
echo -e "${YELLOW}Installing requirements...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
fi

# Check if .env file exists and load it
if [ -f .env ]; then
    echo -e "${YELLOW}Loading environment variables...${NC}"
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${YELLOW}No .env file found. Using credentials from configuration.${NC}"
fi

# Check if rootkey.csv exists and use it if no credentials are configured
if [ -z "$AWS_ACCESS_KEY_ID" ] && [ -f rootkey.csv ]; then
    echo -e "${YELLOW}Using credentials from rootkey.csv${NC}"
    export AWS_ACCESS_KEY_ID=$(grep -o 'AWSAccessKeyId=.*' rootkey.csv | cut -d= -f2)
    export AWS_SECRET_ACCESS_KEY=$(grep -o 'AWSSecretKey=.*' rootkey.csv | cut -d= -f2)
fi

# Set default region if not already set
if [ -z "$AWS_REGION" ] && [ -z "$AWS_DEFAULT_REGION" ]; then
    export AWS_DEFAULT_REGION="us-east-1"
    export AWS_REGION="us-east-1"
fi

# Verify AWS credentials
echo -e "${YELLOW}Verifying AWS credentials...${NC}"
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
    echo -e "${RED}Error: AWS credentials not properly configured!${NC}"
    deactivate
    exit 1
fi

# Run the TwinMaker script with the specified workspace ID
echo -e "${YELLOW}Running TwinMaker workspace creator...${NC}"
if [ "$NON_INTERACTIVE" = true ]; then
    python twin-maker-script.py --workspace-id "$WORKSPACE_ID" --non-interactive
else
    python twin-maker-script.py --workspace-id "$WORKSPACE_ID"
fi

# Check if the script executed successfully
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ TwinMaker workspace creation process completed successfully.${NC}"
else
    echo -e "\n${RED}✗ Error creating TwinMaker workspace.${NC}"
    deactivate
    exit 1
fi

# Deactivate virtual environment
deactivate