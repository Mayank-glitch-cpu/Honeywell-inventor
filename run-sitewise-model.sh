#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}==============================================${NC}"
echo -e "${CYAN}     AWS IoT SiteWise Model Creator          ${NC}"
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

# Check if AWS CLI is installed
if ! command_exists aws; then
    echo -e "${RED}Error: AWS CLI is not installed.${NC}"
    echo -e "${YELLOW}Installing AWS CLI...${NC}"
    
    # Check if pip is installed
    if command_exists pip3; then
        pip3 install --user awscli
    else
        echo -e "${RED}Error: pip3 is not installed. Please install pip3 or AWS CLI manually.${NC}"
        echo -e "You can install AWS CLI by following instructions at: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi
    
    # Check if AWS CLI is in PATH after installation
    if ! command_exists aws; then
        echo -e "${YELLOW}AWS CLI installed but not found in PATH.${NC}"
        echo -e "You may need to add ~/.local/bin to your PATH or restart your terminal."
        echo -e "Attempting to use the AWS CLI from the user's local bin..."
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi

# Ensure python3-venv is installed
if ! python3 -c "import venv" &>/dev/null; then
    echo -e "${YELLOW}Python venv module not available. Attempting to install...${NC}"
    sudo apt-get update && sudo apt-get install -y python3-venv python3-full
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install python3-venv. Please install it manually with:${NC}"
        echo -e "${CYAN}sudo apt-get install python3-venv python3-full${NC}"
        exit 1
    fi
fi

# Set the virtual environment path - use a dedicated one for this project
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
echo -e "${YELLOW}Installing required packages in virtual environment...${NC}"
if [ -f "requirements.txt" ]; then
    "$VENV_PATH/bin/pip" install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install packages from requirements.txt${NC}"
        deactivate
        exit 1
    fi
else
    echo -e "${YELLOW}No requirements.txt found, creating one with basic dependencies...${NC}"
    echo "boto3>=1.26.0" > requirements.txt
    "$VENV_PATH/bin/pip" install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install boto3${NC}"
        deactivate
        exit 1
    fi
fi

# Verify boto3 is installed
if ! "$VENV_PATH/bin/python" -c "import boto3" &>/dev/null; then
    echo -e "${YELLOW}boto3 not found, installing it directly...${NC}"
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

# Check if the IoT SiteWise model creator script exists
if [ ! -f "create-iotsitewise-model.py" ]; then
    echo -e "${RED}Error: create-iotsitewise-model.py not found in the current directory!${NC}"
    deactivate
    exit 1
fi

# Make the script executable if it isn't already
if [ ! -x "create-iotsitewise-model.py" ]; then
    chmod +x create-iotsitewise-model.py
fi

# Explain what will happen
echo -e "\n${CYAN}This script will create a new IoT SiteWise model named 'Motor-scripted' with:${NC}"
echo -e " - ${YELLOW}Attribute:${NC} Serial Number (String type)"
echo -e " - ${YELLOW}Measurement:${NC} Speed (Double type, RPM unit)"

# Ask for confirmation
echo ""
read -p "Do you want to proceed? (y/n): " confirm

if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    echo -e "\n${GREEN}Creating IoT SiteWise Motor model...${NC}"
    
    # Run the IoT SiteWise model creation script using the Python from the virtual environment
    MODEL_ID=$("$VENV_PATH/bin/python" create-iotsitewise-model.py | grep "Model ID:" | cut -d ":" -f 2 | tr -d ' ')
    
    # Check if the script executed successfully
    if [ $? -eq 0 ]; then
        echo -e "\n${GREEN}Model creation completed successfully.${NC}"
        if [ ! -z "$MODEL_ID" ]; then
            echo -e "${GREEN}Model ID: ${CYAN}$MODEL_ID${NC}"
            echo -e "${GREEN}To create assets based on this model, run:${NC}"
            echo -e "${CYAN}./run-sitewise-asset.sh $MODEL_ID${NC}"
        fi
    else
        echo -e "\n${RED}The script encountered an error during execution.${NC}"
    fi
else
    echo -e "${YELLOW}Model creation cancelled.${NC}"
fi

# Deactivate virtual environment
deactivate

echo -e "${CYAN}==============================================${NC}"