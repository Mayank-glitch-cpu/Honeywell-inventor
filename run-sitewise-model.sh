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

# Get available model types from config.json
MODEL_TYPES=$("$VENV_PATH/bin/python" -c "
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    models = config.get('sitewise', {}).get('models', {})
    if models:
        print('\\n'.join(models.keys()))
    else:
        print('No model types found in config.json')
except Exception as e:
    print(f'Error reading config.json: {e}')
")

# Check if we got any model types
if [[ "$MODEL_TYPES" == *"Error"* || "$MODEL_TYPES" == "No model types found"* ]]; then
    echo -e "${RED}Error: Could not find model types in config.json.${NC}"
    echo -e "${YELLOW}Please ensure your config.json is properly set up with 'sitewise.models' section.${NC}"
    deactivate
    exit 1
fi

# Convert the newline-separated string to an array
IFS=$'\n' read -d '' -r -a MODEL_TYPE_ARRAY <<< "$MODEL_TYPES"

# Display available model types
echo -e "\n${CYAN}Available Cookie Factory Models:${NC}"
for i in "${!MODEL_TYPE_ARRAY[@]}"; do
    INDEX=$((i+1))
    MODEL_TYPE="${MODEL_TYPE_ARRAY[$i]}"
    
    # Get model name and description from config
    MODEL_INFO=$("$VENV_PATH/bin/python" -c "
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    model = config.get('sitewise', {}).get('models', {}).get('$MODEL_TYPE', {})
    print(f\"{model.get('name', '$MODEL_TYPE')}|{model.get('description', 'No description')}|{len(model.get('properties', []))}\" )
except Exception as e:
    print(f'Unknown|Error reading model info: {e}|0')
")
    
    # Parse the model info
    IFS='|' read -r MODEL_NAME MODEL_DESC PROP_COUNT <<< "$MODEL_INFO"
    
    echo -e "${GREEN}$INDEX.${NC} ${CYAN}$MODEL_NAME${NC} ($MODEL_TYPE)"
    echo -e "   ${YELLOW}Description:${NC} $MODEL_DESC"
    echo -e "   ${YELLOW}Properties:${NC} $PROP_COUNT defined"
done

# Ask user to select a model type
echo -e "\n${YELLOW}Select a model type to create:${NC}"
read -p "Enter the number (1-${#MODEL_TYPE_ARRAY[@]}): " MODEL_CHOICE

# Validate input
if ! [[ "$MODEL_CHOICE" =~ ^[0-9]+$ ]] || [ "$MODEL_CHOICE" -lt 1 ] || [ "$MODEL_CHOICE" -gt "${#MODEL_TYPE_ARRAY[@]}" ]; then
    echo -e "${RED}Invalid choice. Exiting.${NC}"
    deactivate
    exit 1
fi

# Get the selected model type
SELECTED_MODEL_TYPE="${MODEL_TYPE_ARRAY[$((MODEL_CHOICE-1))]}"
echo -e "\n${GREEN}Selected model type: ${CYAN}$SELECTED_MODEL_TYPE${NC}"

# Get model details for display
MODEL_DETAILS=$("$VENV_PATH/bin/python" -c "
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    model = config.get('sitewise', {}).get('models', {}).get('$SELECTED_MODEL_TYPE', {})
    properties = model.get('properties', [])
    
    model_info = {
        'name': model.get('name', 'Unknown'),
        'desc': model.get('description', 'No description'),
        'properties': []
    }
    
    for prop in properties:
        prop_type = 'Attribute' if 'attribute' in prop.get('type', {}) else 'Measurement' if 'measurement' in prop.get('type', {}) else 'Unknown'
        unit = prop.get('unit', 'None')
        unit_display = f', {unit}' if unit != 'None' else ''
        
        model_info['properties'].append({
            'name': prop.get('name', 'Unnamed'),
            'type': prop_type,
            'data_type': prop.get('dataType', 'Unknown'),
            'unit_display': unit_display
        })
    
    print(json.dumps(model_info))
except Exception as e:
    print('{\"error\": \"' + str(e) + '\"}')
")

# Extract model name and description
MODEL_NAME=$(echo "$MODEL_DETAILS" | "$VENV_PATH/bin/python" -c "import sys, json; print(json.load(sys.stdin).get('name', 'Unknown'))")
MODEL_DESC=$(echo "$MODEL_DETAILS" | "$VENV_PATH/bin/python" -c "import sys, json; print(json.load(sys.stdin).get('desc', 'No description'))")

# Display model details
echo -e "\n${CYAN}Model Details:${NC}"
echo -e "${YELLOW}Name:${NC} $MODEL_NAME"
echo -e "${YELLOW}Description:${NC} $MODEL_DESC"
echo -e "${YELLOW}Properties:${NC}"

# Display model properties
PROPERTIES=$(echo "$MODEL_DETAILS" | "$VENV_PATH/bin/python" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for i, prop in enumerate(data.get('properties', []), 1):
        print(f\"{i}. {prop['name']} ({prop['type']}, {prop['data_type']}{prop['unit_display']})\" )
except Exception as e:
    print(f'Error parsing properties: {e}')
")

echo -e "$PROPERTIES"

# Ask for confirmation
echo ""
read -p "Do you want to proceed with creating this model? (y/n): " confirm

if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    echo -e "\n${GREEN}Creating IoT SiteWise model for $MODEL_NAME...${NC}"
    
    # Run the IoT SiteWise model creation script using the Python from the virtual environment
    "$VENV_PATH/bin/python" create-iotsitewise-model.py "$SELECTED_MODEL_TYPE"
    
    # Extract the model ID from the output
    MODEL_ID=$(echo "$("$VENV_PATH/bin/python" create-iotsitewise-model.py "$SELECTED_MODEL_TYPE")" | grep -o "Model ID: [a-zA-Z0-9\-]*" | cut -d " " -f 3)
    
    # Check if the script executed successfully
    if [ $? -eq 0 ] && [ ! -z "$MODEL_ID" ]; then
        echo -e "\n${GREEN}Model creation completed successfully.${NC}"
        echo -e "${GREEN}Model ID: ${CYAN}$MODEL_ID${NC}"
        echo -e "${GREEN}To create assets based on this model, run:${NC}"
        echo -e "${CYAN}./run-sitewise-asset.sh $MODEL_ID $SELECTED_MODEL_TYPE${NC}"
    else
        echo -e "\n${RED}The script encountered an error during execution.${NC}"
    fi
else
    echo -e "${YELLOW}Model creation cancelled.${NC}"
fi

# Deactivate virtual environment
deactivate
echo -e "${CYAN}==============================================${NC}"