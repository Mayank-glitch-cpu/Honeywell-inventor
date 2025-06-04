#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}==============================================${NC}"
echo -e "${CYAN}     Cookie Factory Deployment Automation     ${NC}"
echo -e "${CYAN}==============================================${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check script execution status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Success: $1${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed: $1${NC}"
        if [ "$2" == "true" ]; then
            echo -e "${RED}Exiting due to critical error.${NC}"
            exit 1
        fi
        return 1
    fi
}

# Function to get configuration values, redirecting stderr to avoid message output
get_config_value() {
    local result=$(python3 -c "$1" 2>/dev/null)
    echo "$result"
}

# Check for required commands
echo -e "\n${CYAN}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.${NC}"
    exit 1
fi

# Set the virtual environment path from config
CONFIG_DIR="configs"
VENV_PATH="venv-sitewise"  # Default if not found in config

if [ -f "${CONFIG_DIR}/workspace.config.json" ]; then
    VENV_PATH=$(get_config_value "import json; f=open('${CONFIG_DIR}/workspace.config.json'); data=json.load(f); print(data.get('environment', {}).get('venv_path', 'venv-sitewise')); f.close()")
    if [ -z "$VENV_PATH" ]; then
        VENV_PATH="venv-sitewise"  # Fallback to default
    fi
fi

echo -e "${YELLOW}Using virtual environment: ${VENV_PATH}${NC}"

# Check if virtual environment exists, create if not
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Setting up Python virtual environment at ${VENV_PATH}...${NC}"
    
    # Ensure venv module is available
    if ! python3 -c "import venv" &>/dev/null; then
        echo -e "${YELLOW}Python venv module not available. Attempting to install...${NC}"
        sudo apt-get update && sudo apt-get install -y python3-venv python3-full
        check_status "Installing python3-venv" "true"
    fi
    
    python3 -m venv "$VENV_PATH"
    check_status "Creating virtual environment" "true"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "${VENV_PATH}/bin/activate"
check_status "Activating virtual environment" "true"

# Install required packages in the virtual environment
echo -e "${YELLOW}Installing required packages...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    check_status "Installing packages from requirements.txt"
else
    echo -e "${YELLOW}No requirements.txt found, installing boto3...${NC}"
    pip install -q boto3
    check_status "Installing boto3"
    
    # Create a basic requirements.txt file
    echo "boto3>=1.26.0" > requirements.txt
    echo "python-dotenv>=1.0.0" >> requirements.txt
    echo -e "${YELLOW}Created basic requirements.txt${NC}"
fi

# Initialize AWS credentials from config
echo -e "\n${CYAN}Setting up AWS credentials...${NC}"
python3 -c "from config_loader import initialize_env_from_config; initialize_env_from_config()" 2>/dev/null
check_status "Loading AWS credentials from config"

# Check AWS credentials
echo -e "${YELLOW}Verifying AWS credentials...${NC}"
if ! python3 -c "import boto3; boto3.client('sts').get_caller_identity()" &>/dev/null; then
    echo -e "${RED}Error: AWS credentials not found or not properly configured!${NC}"
    echo -e "${YELLOW}Checking for rootkey.csv...${NC}"
    
    if [ -f "rootkey.csv" ]; then
        echo -e "${YELLOW}Found rootkey.csv. Extracting credentials...${NC}"
        AWS_ACCESS_KEY_ID=$(grep -o 'AWSAccessKeyId=.*' rootkey.csv | cut -d= -f2)
        AWS_SECRET_ACCESS_KEY=$(grep -o 'AWSSecretKey=.*' rootkey.csv | cut -d= -f2)
        
        # Export credentials for this session
        export AWS_ACCESS_KEY_ID
        export AWS_SECRET_ACCESS_KEY
        
        echo -e "${GREEN}Credentials from rootkey.csv have been configured for this session.${NC}"
        
        # Verify credentials are working
        if ! python3 -c "import boto3; boto3.client('sts').get_caller_identity()" &>/dev/null; then
            echo -e "${RED}Error: AWS credentials from rootkey.csv are invalid. Please check the file.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: No valid AWS credentials found. Please configure AWS credentials before running this script.${NC}"
        exit 1
    fi
fi

# Get AWS region from config or set a default
AWS_REGION=$(get_config_value "import boto3; import os; print(boto3.session.Session().region_name or os.environ.get('AWS_REGION', 'us-east-1'))")
export AWS_REGION
echo -e "${GREEN}Using AWS region: ${CYAN}$AWS_REGION${NC}"

# Make sure all scripts are executable
echo -e "\n${CYAN}Preparing scripts...${NC}"
chmod +x *.py
chmod +x *.sh
check_status "Making scripts executable"

# Step 1: Create TwinMaker Workspace
echo -e "\n${CYAN}Step 1: Creating AWS IoT TwinMaker Workspace...${NC}"

# Get workspace ID from config
WORKSPACE_ID=$(get_config_value "from config_loader import ConfigLoader; print(ConfigLoader().get_twinmaker_workspace_config().get('id', 'CookieFactoryTwin'))")
echo -e "${YELLOW}Using workspace ID: ${WORKSPACE_ID}${NC}"

# Run the workspace creation script - using python directly to avoid issues
if [ -f "twin-maker-script.py" ]; then
    python3 twin-maker-script.py --workspace-id "$WORKSPACE_ID" --non-interactive
    check_status "Creating TwinMaker workspace: ${WORKSPACE_ID}"
elif [ -f "run.sh" ]; then
    ./run.sh --workspace-id "$WORKSPACE_ID" --non-interactive
    check_status "Creating TwinMaker workspace: ${WORKSPACE_ID}"
else
    echo -e "${RED}Error: No workspace creation script found. Skipping workspace creation.${NC}"
fi

# Step 2: Create SiteWise Models
echo -e "\n${CYAN}Step 2: Creating AWS IoT SiteWise Models...${NC}"

# Get model types from config
MODEL_TYPES=$(get_config_value "from config_loader import ConfigLoader; print(','.join(ConfigLoader().get_sitewise_model_config().keys()))")
IFS=',' read -r -a MODEL_TYPE_ARRAY <<< "$MODEL_TYPES"

echo -e "${YELLOW}Found ${#MODEL_TYPE_ARRAY[@]} model types: ${MODEL_TYPES}${NC}"

# Store model IDs for later use
declare -A MODEL_IDS

# Create each model type
for MODEL_TYPE in "${MODEL_TYPE_ARRAY[@]}"; do
    echo -e "\n${YELLOW}Creating SiteWise model for: ${MODEL_TYPE}${NC}"
    
    # Run the model creation script in non-interactive mode
    RESULT=$(python3 create-iotsitewise-model.py --model-type "$MODEL_TYPE" --auto 2>&1)
    echo "$RESULT"
    
    # Extract model ID from output
    MODEL_ID=$(echo "$RESULT" | grep -o "Model ID: [a-zA-Z0-9\-]*" | cut -d " " -f 3)
    
    if [ ! -z "$MODEL_ID" ]; then
        echo -e "${GREEN}Successfully created model: ${MODEL_TYPE} (ID: ${MODEL_ID})${NC}"
        MODEL_IDS["$MODEL_TYPE"]="$MODEL_ID"
    else
        echo -e "${RED}Failed to extract model ID for ${MODEL_TYPE}. Continuing anyway...${NC}"
    fi
done

# Step 3: Create SiteWise Assets
echo -e "\n${CYAN}Step 3: Creating AWS IoT SiteWise Assets...${NC}"

# Store asset IDs for later use
declare -A ASSET_IDS

# Create assets for each model
for MODEL_TYPE in "${!MODEL_IDS[@]}"; do
    MODEL_ID="${MODEL_IDS[$MODEL_TYPE]}"
    echo -e "\n${YELLOW}Creating SiteWise asset for model type: ${MODEL_TYPE} (ID: ${MODEL_ID})${NC}"
    
    if [ -z "$MODEL_ID" ]; then
        echo -e "${RED}No model ID available for ${MODEL_TYPE}. Skipping asset creation.${NC}"
        continue
    fi
    
    # Run the asset creation script in non-interactive mode - fix the argument order
    RESULT=$(python3 create-iotsitewise-asset.py "$MODEL_ID" "$MODEL_TYPE" --non-interactive 2>&1)
    echo "$RESULT"
    
    # Extract asset ID from output
    ASSET_ID=$(echo "$RESULT" | grep -o "Asset ID: [a-zA-Z0-9\-]*" | cut -d " " -f 3)
    
    if [ ! -z "$ASSET_ID" ]; then
        echo -e "${GREEN}Successfully created asset for ${MODEL_TYPE} (ID: ${ASSET_ID})${NC}"
        ASSET_IDS["$MODEL_TYPE"]="$ASSET_ID"
        
        # Set up aliases for the asset
        if [ -f "set_aliases.py" ]; then
            echo -e "${YELLOW}Setting up aliases for the asset...${NC}"
            python3 set_aliases.py --asset-id "$ASSET_ID" --model-type "$MODEL_TYPE" --non-interactive 2>/dev/null
            check_status "Setting up aliases for ${MODEL_TYPE} asset"
        fi
    else
        echo -e "${RED}Failed to extract asset ID for ${MODEL_TYPE}. Continuing anyway...${NC}"
    fi
done

# Step 4: Create TwinMaker Entities
echo -e "\n${CYAN}Step 4: Creating AWS IoT TwinMaker Entities...${NC}"

# Get entity types from config
ENTITY_TYPES=$(get_config_value "from config_loader import ConfigLoader; config = ConfigLoader().get_entities_config(); print(','.join(config.keys() if isinstance(config, dict) else ['entities']))")
IFS=',' read -r -a ENTITY_TYPE_ARRAY <<< "$ENTITY_TYPES"

echo -e "${YELLOW}Found ${#ENTITY_TYPE_ARRAY[@]} entity types: ${ENTITY_TYPES}${NC}"

# Create each entity directly using the Python script
for ENTITY_TYPE in "${ENTITY_TYPE_ARRAY[@]}"; do
    echo -e "\n${YELLOW}Creating TwinMaker entity for: ${ENTITY_TYPE}${NC}"
    
    # Get corresponding asset ID if available
    ASSET_ID="${ASSET_IDS[$ENTITY_TYPE]}"
    MODEL_ID="${MODEL_IDS[$ENTITY_TYPE]}"
    
    # Run the entity creation script directly
    python3 create-twinmaker-entities.py "$WORKSPACE_ID" --force-recreate --non-interactive
    ENTITY_STATUS=$?
    
    if [ $ENTITY_STATUS -eq 0 ]; then
        echo -e "${GREEN}Successfully created entity: ${ENTITY_TYPE}${NC}"
    else
        echo -e "${RED}Failed to create entity: ${ENTITY_TYPE}${NC}"
    fi
done

# Step 5: Creating data generators for assets
echo -e "\n${CYAN}Step 5: Creating data generators for assets...${NC}"
for MODEL_TYPE in "${!ASSET_IDS[@]}"; do
    ASSET_ID="${ASSET_IDS[$MODEL_TYPE]}"
    SCRIPT_NAME="send-${MODEL_TYPE}-data.sh"
    
    echo -e "${YELLOW}Creating data generator script for ${MODEL_TYPE}...${NC}"
    
    # Get a relevant property alias for this asset type
    PROPERTY_ALIAS=""
    case "$MODEL_TYPE" in
        dough_mixer)
            PROP_NAME="MixerSpeed"
            MIN_VAL=80
            MAX_VAL=120
            ;;
        cookie_cutter)
            PROP_NAME="CookiesCutPerMinute"
            MIN_VAL=100
            MAX_VAL=150
            ;;
        conveyor_oven)
            PROP_NAME="OvenTemperature"
            MIN_VAL=170
            MAX_VAL=190
            ;;
        *)
            echo -e "${YELLOW}No property mapping for ${MODEL_TYPE}. Skipping data generator.${NC}"
            continue
            ;;
    esac
    
    # Attempt to get property alias
    PROPERTY_ALIAS=$(get_config_value "
import boto3
try:
    client = boto3.client('iotsitewise')
    props = client.list_asset_properties(assetId='$ASSET_ID')
    for prop in props.get('assetPropertySummaries', []):
        prop_name = prop.get('name')
        if prop_name == '$PROP_NAME':
            prop_id = prop.get('id')
            prop_details = client.describe_asset_property(assetId='$ASSET_ID', propertyId=prop_id)
            alias = prop_details.get('assetProperty', {}).get('alias')
            if alias:
                print(alias)
                break
except Exception as e:
    pass
")
    
    if [ ! -z "$PROPERTY_ALIAS" ]; then
        # Create the data generator script
        cat > "$SCRIPT_NAME" << EOL
#!/bin/bash
source ${VENV_PATH}/bin/activate
echo "Sending random data to ${MODEL_TYPE} (property: ${PROP_NAME})"
python3 senddata.py --alias "${PROPERTY_ALIAS}" --min ${MIN_VAL} --max ${MAX_VAL} --interval 1.0 "\$@"
EOL
        chmod +x "$SCRIPT_NAME"
        echo -e "${GREEN}Created data generator script: ${SCRIPT_NAME}${NC}"
    else
        echo -e "${RED}Could not find property alias for ${MODEL_TYPE}.${PROP_NAME}. Skipping data generator.${NC}"
    fi
done

# Deactivate virtual environment
deactivate

echo -e "\n${GREEN}=============================================${NC}"
echo -e "${GREEN}     Cookie Factory Deployment Complete!      ${NC}"
echo -e "${GREEN}=============================================${NC}"

# List created resources
echo -e "\n${CYAN}Summary of created resources:${NC}"

echo -e "\n${YELLOW}TwinMaker Workspace:${NC}"
echo -e "- ID: ${WORKSPACE_ID}"

echo -e "\n${YELLOW}SiteWise Models:${NC}"
for MODEL_TYPE in "${!MODEL_IDS[@]}"; do
    echo -e "- ${MODEL_TYPE}: ${MODEL_IDS[$MODEL_TYPE]}"
done

echo -e "\n${YELLOW}SiteWise Assets:${NC}"
for MODEL_TYPE in "${!ASSET_IDS[@]}"; do
    echo -e "- ${MODEL_TYPE}: ${ASSET_IDS[$MODEL_TYPE]}"
done

echo -e "\n${CYAN}Next Steps:${NC}"
echo -e "1. View your workspace in the AWS IoT TwinMaker console"
echo -e "2. View your assets in the AWS IoT SiteWise console"
echo -e "3. Generate test data using the created send-*-data.sh scripts"

echo -e "\n${CYAN}Example data generation commands:${NC}"
for MODEL_TYPE in "${!ASSET_IDS[@]}"; do
    SCRIPT_NAME="send-${MODEL_TYPE}-data.sh"
    if [ -f "$SCRIPT_NAME" ]; then
        echo -e "- ${GREEN}./${SCRIPT_NAME}${NC}"
    fi
done

echo -e "\n${CYAN}==============================================${NC}"