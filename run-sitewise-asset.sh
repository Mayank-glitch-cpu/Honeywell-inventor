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

# Function to validate AWS IoT SiteWise IDs
validate_aws_id() {
    local id_type="$1"
    local id_value="$2"
    local min_length=36  # AWS IoT SiteWise IDs are typically 36 characters (UUID format)
    
    # Check if the ID is empty
    if [ -z "$id_value" ]; then
        echo -e "${RED}Error: $id_type ID is required and cannot be empty.${NC}"
        return 1
    fi
    
    # Check the length
    if [ ${#id_value} -lt $min_length ]; then
        echo -e "${RED}Error: $id_type ID must be at least $min_length characters. Current length: ${#id_value}${NC}"
        echo -e "${YELLOW}Common issue: Make sure all characters are included. IDs typically look like: f6bbf9db-2771-480e-85cf-e22d154a1705${NC}"
        return 1
    fi
    
    # Check for valid UUID format (basic check for 36 chars with hyphens in the right places)
    if ! [[ $id_value =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        echo -e "${YELLOW}Warning: $id_type ID doesn't match expected UUID format. It may still work, but double-check for typos.${NC}"
    fi
    
    return 0
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

# Validate the model ID
echo -e "${YELLOW}Validating model ID format...${NC}"
if ! validate_aws_id "Model" "$MODEL_ID"; then
    echo -e "${RED}The model ID provided appears to be invalid.${NC}"
    
    # If it's exactly 35 chars, suggest adding 'f' at the beginning (common issue)
    if [ ${#MODEL_ID} -eq 35 ]; then
        echo -e "${YELLOW}The model ID is 35 characters long, but should be 36. Common fix: try adding 'f' at the beginning.${NC}"
        read -p "Would you like to try adding 'f' to the beginning of the ID? (y/n): " add_f
        
        if [[ "$add_f" == "y" || "$add_f" == "Y" ]]; then
            FIXED_MODEL_ID="f$MODEL_ID"
            echo -e "${GREEN}Updated model ID to: ${CYAN}$FIXED_MODEL_ID${NC}"
            MODEL_ID=$FIXED_MODEL_ID
        else
            echo -e "${YELLOW}Proceeding with the original ID, but it may cause errors.${NC}"
        fi
    else
        read -p "Do you want to proceed anyway? (y/n): " proceed
        if [[ "$proceed" != "y" && "$proceed" != "Y" ]]; then
            echo -e "${YELLOW}Exiting.${NC}"
            deactivate
            exit 1
        fi
        echo -e "${YELLOW}Proceeding with the provided ID, but it may cause errors.${NC}"
    fi
fi

# Check for the model type
MODEL_TYPE=""
if [ "$#" -ge 2 ]; then
    MODEL_TYPE="$2"
    echo -e "${GREEN}Using provided model type: ${CYAN}$MODEL_TYPE${NC}"
else
    # Try to determine model type from the model ID
    echo -e "${YELLOW}No model type provided, attempting to determine from model ID...${NC}"
    
    MODEL_TYPE=$("$VENV_PATH/bin/python" -c "
import boto3
try:
    client = boto3.client('iotsitewise')
    model = client.describe_asset_model(assetModelId='$MODEL_ID')
    model_name = model['assetModelName'].lower()
    
    if 'dough' in model_name or 'mixer' in model_name:
        print('dough_mixer')
    elif 'cookie' in model_name and 'cutter' in model_name:
        print('cookie_cutter')
    elif 'conveyor' in model_name or 'oven' in model_name:
        print('conveyor_oven')
    else:
        print('generic')
except Exception as e:
    print(f'Error determining model type: {e}')
" 2>/dev/null)
    
    if [[ "$MODEL_TYPE" == *"Error"* ]]; then
        echo -e "${RED}Failed to determine model type: $MODEL_TYPE${NC}"
        echo -e "${YELLOW}Available model types:${NC}"
        
        # List available model types from config
        MODEL_TYPES=$("$VENV_PATH/bin/python" -c "
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    models = config.get('sitewise', {}).get('assets', {})
    if models:
        for i, model_type in enumerate(models.keys(), 1):
            print(f'{i}. {model_type}')
    else:
        print('No model types found in config.json')
except Exception as e:
    print(f'Error reading config.json: {e}')
")
        
        echo -e "${CYAN}$MODEL_TYPES${NC}"
        read -p "Enter the model type to use: " MODEL_TYPE
        
        if [ -z "$MODEL_TYPE" ]; then
            echo -e "${YELLOW}No model type provided. Will use generic approach.${NC}"
            MODEL_TYPE="generic"
        fi
    else
        echo -e "${GREEN}Detected model type: ${CYAN}$MODEL_TYPE${NC}"
    fi
fi

# Check if we have valid model type in our config
if [ ! -z "$MODEL_TYPE" ] && [ "$MODEL_TYPE" != "generic" ]; then
    CONFIG_CHECK=$("$VENV_PATH/bin/python" -c "
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    if '$MODEL_TYPE' in config.get('sitewise', {}).get('assets', {}):
        print('valid')
    else:
        print('invalid')
except Exception as e:
    print(f'error: {e}')
")
    
    if [ "$CONFIG_CHECK" != "valid" ]; then
        echo -e "${YELLOW}Warning: Model type '$MODEL_TYPE' not found in config. Will use generic approach.${NC}"
        MODEL_TYPE="generic"
    fi
fi

# Execute the Python script to create a new asset based on the model
echo -e "\n${GREEN}Creating IoT SiteWise asset based on model ID: ${CYAN}$MODEL_ID${NC}"
if [ ! -z "$MODEL_TYPE" ] && [ "$MODEL_TYPE" != "generic" ]; then
    echo -e "${GREEN}Using model type: ${CYAN}$MODEL_TYPE${NC}"
    "$VENV_PATH/bin/python" create-iotsitewise-asset.py "$MODEL_ID" "$MODEL_TYPE"
else
    "$VENV_PATH/bin/python" create-iotsitewise-asset.py "$MODEL_ID"
fi

# Get the new asset ID from the output
ASSET_ID=$("$VENV_PATH/bin/python" create-iotsitewise-asset.py "$MODEL_ID" "$MODEL_TYPE" 2>/dev/null | grep -o "Asset ID: [a-zA-Z0-9\-]*" | cut -d " " -f 3)

if [ ! -z "$ASSET_ID" ]; then
    echo -e "\n${GREEN}Asset creation completed.${NC}"
    
    # Configure aliases for the asset
    echo -e "${YELLOW}Setting up aliases for the asset...${NC}"
    if [ -f "set_aliases.py" ]; then
        # Make it executable
        chmod +x set_aliases.py
        
        if [ ! -z "$MODEL_TYPE" ] && [ "$MODEL_TYPE" != "generic" ]; then
            echo -e "${GREEN}Running: python set_aliases.py --asset-id $ASSET_ID --model-type $MODEL_TYPE${NC}"
            "$VENV_PATH/bin/python" set_aliases.py --asset-id "$ASSET_ID" --model-type "$MODEL_TYPE"
        else
            echo -e "${GREEN}Running: python set_aliases.py --asset-id $ASSET_ID${NC}"
            "$VENV_PATH/bin/python" set_aliases.py --asset-id "$ASSET_ID"
        fi
    else
        echo -e "${YELLOW}Warning: set_aliases.py not found. Skipping alias configuration.${NC}"
    fi
    
    echo -e "\n${GREEN}Asset setup complete!${NC}"
    echo -e "${GREEN}Asset ID: ${CYAN}$ASSET_ID${NC}"
    
    # Show the user how to verify the asset properties
    if [ -f "verify_asset_config.py" ]; then
        echo -e "\n${GREEN}To verify the asset properties, run:${NC}"
        echo -e "${CYAN}python verify_asset_config.py $ASSET_ID${NC}"
    fi
    
    echo -e "\n${GREEN}You can now access your asset in the AWS IoT SiteWise console.${NC}"
    echo -e "${GREEN}Navigate to Assets section to view your new asset.${NC}"
else
    echo -e "\n${RED}Failed to create the asset or extract the asset ID.${NC}"
fi

# Deactivate virtual environment
deactivate
echo -e "${CYAN}==============================================${NC}"