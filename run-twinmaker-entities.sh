#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse arguments
NON_INTERACTIVE=false
FORCE_RECREATE=false
WORKSPACE_ID=""

# Parse command line options
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    --force-recreate)
      FORCE_RECREATE=true
      shift
      ;;
    *)
      # First non-flag argument is treated as workspace ID
      if [[ -z "$WORKSPACE_ID" ]]; then
        WORKSPACE_ID="$1"
      fi
      shift
      ;;
  esac
done

# Only show banner in interactive mode
if [ "$NON_INTERACTIVE" = false ]; then
  echo -e "${CYAN}=======================================================${NC}"
  echo -e "${CYAN}     AWS IoT TwinMaker Motor Entity Creator            ${NC}"
  echo -e "${CYAN}=======================================================${NC}"
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required commands
if ! command_exists python3; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.${NC}"
    exit 1
fi

# Set the virtual environment path - using the same one as other scripts
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
    
    # In non-interactive mode, just exit with error
    if [ "$NON_INTERACTIVE" = true ]; then
        echo -e "${RED}Cannot proceed without AWS credentials in non-interactive mode.${NC}"
        deactivate
        exit 1
    fi
    
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
            AWS_ACCESS_KEY_ID=$(grep -i "Access key ID" rootkey.csv | cut -d ',' -f 2)
            AWS_SECRET_ACCESS_KEY=$(grep -i "Secret access key" rootkey.csv | cut -d ',' -f 2)
            
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
    if [ "$NON_INTERACTIVE" = true ]; then
        echo -e "${RED}AWS region is not set and required in non-interactive mode.${NC}"
        deactivate
        exit 1
    fi
    
    echo -e "${YELLOW}AWS region is not set.${NC}"
    read -p "Enter the AWS region to use (e.g., us-east-1): " input_region
    
    export AWS_REGION=$input_region
    echo -e "${GREEN}Using AWS region: ${CYAN}$AWS_REGION${NC}"
else
    echo -e "${GREEN}Using AWS region: ${CYAN}$AWS_REGION${NC}"
fi

# Check if the TwinMaker entity creator script exists
if [ ! -f "create-twinmaker-entities.py" ]; then
    echo -e "${RED}Error: create-twinmaker-entities.py not found in the current directory!${NC}"
    deactivate
    exit 1
fi

# Make the script executable if it isn't already
if [ ! -x "create-twinmaker-entities.py" ]; then
    chmod +x create-twinmaker-entities.py
fi

# Get the workspace ID either from command line argument, environment, or prompt
if [ -z "$WORKSPACE_ID" ]; then
    if [ -n "$WORKSPACE_ID" ]; then
        echo -e "${GREEN}Using workspace ID from environment: ${CYAN}$WORKSPACE_ID${NC}"
    elif [ "$NON_INTERACTIVE" = true ]; then
        # In non-interactive mode, use default workspace
        WORKSPACE_ID="SimpleFactoryTwin"
        echo -e "${GREEN}Using default workspace ID in non-interactive mode: ${CYAN}$WORKSPACE_ID${NC}"
    else
        # Try to list available workspaces to help the user
        echo -e "${YELLOW}No workspace ID provided. Attempting to list available TwinMaker workspaces...${NC}"
        echo -e "${CYAN}This may take a few seconds...${NC}"
        
        WORKSPACE_LIST=$("$VENV_PATH/bin/python" -c "
import boto3
try:
    client = boto3.client('iottwinmaker')
    response = client.list_workspaces(maxResults=10)
    print('Available workspaces:')
    for workspace in response.get('workspaceSummaries', []):
        print(f\"- {workspace.get('workspaceId')}\")
except Exception as e:
    print(f'Error listing workspaces: {e}')
" 2>/dev/null)
        
        echo -e "${CYAN}$WORKSPACE_LIST${NC}"
        echo ""
        
        # Default workspace ID based on other scripts
        DEFAULT_WORKSPACE="SimpleFactoryTwin"
        read -p "Enter the workspace ID to use (or press enter for default '$DEFAULT_WORKSPACE'): " WORKSPACE_ID
        
        if [ -z "$WORKSPACE_ID" ]; then
            WORKSPACE_ID="$DEFAULT_WORKSPACE"
            echo -e "${GREEN}Using default workspace ID: ${CYAN}$WORKSPACE_ID${NC}"
        fi
    fi
fi

# Only ask for confirmation in interactive mode
if [ "$NON_INTERACTIVE" = false ]; then
    # Explain what will happen
    echo -e "\n${CYAN}This script will create a component type and entity in the TwinMaker workspace ${YELLOW}$WORKSPACE_ID${NC}"
    echo -e "The following will be created:"
    echo -e " - ${YELLOW}Component Type:${NC} MotorComponentType"
    echo -e " - ${YELLOW}Entity:${NC} motor-scripted-1"
    
    # Ask for confirmation
    echo ""
    read -p "Do you want to proceed? (y/n): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${YELLOW}Entity creation cancelled.${NC}"
        deactivate
        exit 0
    fi
fi

echo -e "\n${GREEN}Creating TwinMaker motor entity...${NC}"

# Build command with appropriate flags
CMD_ARGS=()

# Add workspace ID as a positional argument
CMD_ARGS+=("$WORKSPACE_ID")

# Add optional flags
if [ "$NON_INTERACTIVE" = true ]; then
    CMD_ARGS+=("--non-interactive")
fi

if [ "$FORCE_RECREATE" = true ]; then
    CMD_ARGS+=("--force-recreate")
fi

# Run the entity creation script using Python from the virtual environment
# Use explicit command instead of relying on command output redirection
"$VENV_PATH/bin/python" create-twinmaker-entities.py "${CMD_ARGS[@]}"

# Check if the script executed successfully
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}TwinMaker motor entity created successfully.${NC}"
    echo -e "${GREEN}You can now view and interact with this entity in the AWS IoT TwinMaker console.${NC}"
else
    echo -e "\n${RED}The script encountered an error during execution.${NC}"
    deactivate
    exit 1
fi

# Deactivate virtual environment
deactivate

# Only show footer in interactive mode
if [ "$NON_INTERACTIVE" = false ]; then
    echo -e "${CYAN}=======================================================${NC}"
fi