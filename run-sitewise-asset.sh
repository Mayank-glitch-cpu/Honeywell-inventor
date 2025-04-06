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

# Get model property information to help with alias configuration
echo -e "\n${YELLOW}Fetching properties from the selected model...${NC}"
MODEL_PROPERTIES=$("$VENV_PATH/bin/python" -c "
import boto3
import json
try:
    client = boto3.client('iotsitewise')
    response = client.describe_asset_model(assetModelId='$MODEL_ID')
    properties = response.get('assetModelProperties', [])
    property_list = []
    for prop in properties:
        prop_type = 'attribute' if 'attribute' in prop.get('type', {}) else 'measurement' if 'measurement' in prop.get('type', {}) else 'unknown'
        property_list.append({
            'name': prop.get('name', 'Unknown'),
            'type': prop_type,
            'dataType': prop.get('dataType', 'Unknown'),
            'unit': prop.get('unit', 'None')
        })
    print(json.dumps(property_list))
except Exception as e:
    print(f'Error fetching model properties: {e}')
    print('[]')
" 2>/dev/null)

# Process the model properties JSON
MODEL_PROPERTIES_PARSED=$(echo "$MODEL_PROPERTIES" | "$VENV_PATH/bin/python" -c "
import sys
import json
try:
    data = json.load(sys.stdin)
    if data:
        print('Available properties:')
        for i, prop in enumerate(data, 1):
            unit_display = f\", {prop['unit']}\" if prop['unit'] != 'None' else ''
            # Ensure Speed property is properly marked as using RPM
            if prop['name'] == 'Speed' and prop['unit'] == 'None':
                unit_display = ', RPM (will be configured)'
            print(f\"{i}. {prop['name']} ({prop['type']}, {prop['dataType']}{unit_display})\")
    else:
        print('No properties found or error fetching properties')
except Exception as e:
    print(f'Error parsing properties: {e}')
")

# Check if we actually got properties - if not, likely the model ID is incorrect
if [[ "$MODEL_PROPERTIES" == *"Error fetching model properties"* ]]; then
    echo -e "${RED}Failed to fetch model properties. This suggests the model ID may be incorrect.${NC}"
    echo -e "${YELLOW}Would you like to:${NC}"
    echo -e "1. Try another model ID"
    echo -e "2. Proceed anyway (not recommended)"
    echo -e "3. Quit"
    
    read -p "Enter your choice (1-3): " model_error_choice
    
    case $model_error_choice in
        1)
            echo -e "${YELLOW}Please enter a new model ID:${NC}"
            read -p "> " MODEL_ID
            if ! validate_aws_id "Model" "$MODEL_ID"; then
                echo -e "${RED}The new model ID also appears invalid. Exiting.${NC}"
                deactivate
                exit 1
            fi
            ;;
        2)
            echo -e "${YELLOW}Proceeding with the original ID, but this will likely fail.${NC}"
            ;;
        *)
            echo -e "${YELLOW}Exiting.${NC}"
            deactivate
            exit 1
            ;;
    esac
else
    echo -e "${CYAN}$MODEL_PROPERTIES_PARSED${NC}"
fi

# Function to create or update config.json with aliases
update_config_with_aliases() {
    local config_file="config.json"
    local temp_file=$(mktemp)
    local property_name="$1"
    local alias_value="$2"
    local model_name="$3"
    local asset_name="$4"
    
    # Create config file if it doesn't exist
    if [ ! -f "$config_file" ]; then
        echo "{}" > "$config_file"
    fi
    
    # Use python to update the config file with new alias
    "$VENV_PATH/bin/python" -c "
import json
import os

config_file = '$config_file'
property_name = '$property_name'
alias_value = '$alias_value'
model_name = '$model_name'
asset_name = '$asset_name'

try:
    # Load existing config
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Ensure the structure exists
    if 'sitewise' not in config:
        config['sitewise'] = {}
    if 'asset' not in config['sitewise']:
        config['sitewise']['asset'] = {}
    if 'property_aliases' not in config['sitewise']['asset']:
        config['sitewise']['asset']['property_aliases'] = {}
        
    # Add or update the basic alias pattern template
    config['sitewise']['asset']['alias_template'] = '{model_name}/{asset_name}'
    config['sitewise']['asset']['asset_alias'] = '{model_name}/{asset_name}'
    
    # Update or add the alias with the model_name/asset_name pattern
    # Use lowercase for property name in the alias path for better compatibility
    config['sitewise']['asset']['property_aliases'][property_name] = alias_value
    
    # If this is the Speed property, ensure it's set to RPM in the model config
    if property_name == 'Speed' and 'model' in config['sitewise']:
        for prop in config['sitewise']['model'].get('properties', []):
            if prop.get('name') == 'Speed':
                prop['unit'] = 'RPM'
                break
    
    # Write back to the config file
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f'Updated config.json with alias for {property_name}: {alias_value.format(model_name=model_name.lower(), asset_name=asset_name.lower())}')
except Exception as e:
    print(f'Error updating config: {e}')
"
}

# Function to ensure that Speed is set to RPM in config.json
ensure_speed_has_rpm_unit() {
    "$VENV_PATH/bin/python" -c "
import json
import os

config_file = 'config.json'

try:
    # Load existing config
    if not os.path.exists(config_file):
        with open(config_file, 'w') as f:
            json.dump({}, f)
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Ensure the structure exists
    if 'sitewise' not in config:
        config['sitewise'] = {}
    if 'model' not in config['sitewise']:
        config['sitewise']['model'] = {'properties': []}
    
    # Find Speed property in model config
    speed_prop = None
    for prop in config['sitewise']['model'].get('properties', []):
        if prop.get('name') == 'Speed':
            speed_prop = prop
            break
    
    # If Speed property exists, set its unit to RPM
    if speed_prop:
        speed_prop['unit'] = 'RPM'
        print('✅ Updated Speed property unit to RPM in config')
    else:
        # Create a default Speed property if not found
        new_prop = {
            'name': 'Speed',
            'dataType': 'DOUBLE',
            'unit': 'RPM',
            'type': {
                'measurement': {}
            }
        }
        config['sitewise']['model']['properties'].append(new_prop)
        print('✅ Added Speed property with RPM unit to config')
    
    # Write back to the config file
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
except Exception as e:
    print(f'Error updating Speed property in config: {e}')
"
}

# Function to verify and update notification status for Speed property
ensure_speed_notification_enabled() {
    "$VENV_PATH/bin/python" -c "
import json

config_file = 'config.json'

try:
    # Load existing config
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Add notification enabled flag
    if 'sitewise' in config:
        if 'asset' not in config['sitewise']:
            config['sitewise']['asset'] = {}
        
        # Explicitly set notification_state to ENABLED
        config['sitewise']['asset']['notification_state'] = 'ENABLED'
        
        # Write back to the config file
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print('✅ Set notification state to ENABLED in config')
except Exception as e:
    print(f'Error setting notification state in config: {e}')
"
}

# Get the model name for alias creation
MODEL_NAME=$("$VENV_PATH/bin/python" -c "
import boto3
try:
    client = boto3.client('iotsitewise')
    response = client.describe_asset_model(assetModelId='$MODEL_ID')
    print(response.get('assetModelName', 'UnknownModel'))
except Exception as e:
    print('UnknownModel')
" 2>/dev/null)

# If model name couldn't be fetched, double-check the problem
if [[ "$MODEL_NAME" == "UnknownModel" ]]; then
    echo -e "${RED}Could not retrieve the model name. This suggests the model ID is incorrect.${NC}"
    read -p "Do you want to proceed anyway? (y/n): " proceed_unknown
    
    if [[ "$proceed_unknown" != "y" && "$proceed_unknown" != "Y" ]]; then
        echo -e "${YELLOW}Exiting.${NC}"
        deactivate
        exit 1
    fi
fi

# Configure aliases for properties
echo -e "\n${YELLOW}Would you like to configure aliases for the asset properties? (y/n): ${NC}"
read -p "" configure_aliases

if [[ "$configure_aliases" == "y" || "$configure_aliases" == "Y" ]]; then
    # Check if properties were fetched successfully
    if [[ "$MODEL_PROPERTIES" != *"Error"* && "$MODEL_PROPERTIES" != "[]" ]]; then
        # Convert the JSON to Python list for processing
        PROPERTIES_ARRAY=($("$VENV_PATH/bin/python" -c "
import json
try:
    props = json.loads('$MODEL_PROPERTIES')
    for prop in props:
        print(prop['name'])
except Exception as e:
    print(f'Error processing properties: {e}')
"))
        
        echo -e "\n${CYAN}Configure aliases for asset properties${NC}"
        echo -e "${YELLOW}Aliases are used to identify properties in AWS IoT Core and other services${NC}"
        echo -e "${YELLOW}Using alias format: model_name/asset_name/property_name${NC}"
        
        # Get asset name for aliases
        echo -e "\n${CYAN}Enter a name for this asset (e.g., 'motor1'): ${NC}"
        read -p "" asset_name
        
        if [ -z "$asset_name" ]; then
            asset_name="motor-scripted-1"
            echo -e "${YELLOW}Using default asset name: '$asset_name'${NC}"
        fi
        
        # Update the asset name template in config.json
        "$VENV_PATH/bin/python" -c "
import json
import os

config_file = 'config.json'
asset_name = '$asset_name'

try:
    # Load existing config
    if not os.path.exists(config_file):
        with open(config_file, 'w') as f:
            json.dump({}, f)
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Ensure the structure exists
    if 'sitewise' not in config:
        config['sitewise'] = {}
    if 'asset' not in config['sitewise']:
        config['sitewise']['asset'] = {}
    
    # Update or add the asset name template
    config['sitewise']['asset']['name_template'] = asset_name + '-{index}'
    config['sitewise']['asset']['index'] = 1
    config['sitewise']['asset']['asset_alias'] = '{model_name}/{asset_name}'
    config['sitewise']['asset']['notification_state'] = 'ENABLED'
    
    # Write back to the config file
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f'Updated config.json with asset name template: {asset_name}-{{index}}')
except Exception as e:
    print(f'Error updating config: {e}')
"
        
        # Configure aliases for each property
        for property_name in "${PROPERTIES_ARRAY[@]}"; do
            # Skip any error messages that might have been printed
            if [[ "$property_name" == *"Error"* ]]; then
                continue
            fi
            
            # Generate a standardized alias using model_name/asset_name pattern
            # Use lowercase property name in the path for better compatibility
            alias_template="{model_name}/{asset_name}/${property_name,,}"
            
            echo -e "\n${CYAN}Property: ${YELLOW}$property_name${NC}"
            echo -e "${CYAN}Using alias format: ${GREEN}$alias_template${NC}"
            
            # Update the config.json with the alias
            update_config_with_aliases "$property_name" "$alias_template" "$MODEL_NAME" "$asset_name"
            
            # Special handling for Speed property to ensure it's in RPM
            if [[ "$property_name" == "Speed" ]]; then
                echo -e "${GREEN}✅ Speed property will be configured with RPM units${NC}"
                ensure_speed_has_rpm_unit
                ensure_speed_notification_enabled
            fi
        done
        
        echo -e "\n${GREEN}All aliases have been configured and saved to config.json${NC}"
    else
        echo -e "${RED}Could not fetch property information from the model. Manual alias configuration required.${NC}"
        
        echo -e "\n${YELLOW}Would you like to manually configure aliases? (y/n): ${NC}"
        read -p "" manual_aliases
        
        if [[ "$manual_aliases" == "y" || "$manual_aliases" == "Y" ]]; then
            echo -e "\n${CYAN}Enter a name for this asset (e.g., 'motor1'): ${NC}"
            read -p "" asset_name
            
            if [ -z "$asset_name" ]; then
                asset_name="motor-scripted-1"
                echo -e "${YELLOW}Using default asset name: '$asset_name'${NC}"
            fi
            
            while true; do
                echo -e "\n${CYAN}Enter property name (or leave empty to finish): ${NC}"
                read -p "" property_name
                
                if [ -z "$property_name" ]; then
                    break
                fi
                
                # Generate a standardized alias using model_name/asset_name pattern
                # Use lowercase property name in the path for better compatibility
                alias_template="{model_name}/{asset_name}/${property_name,,}"
                
                echo -e "${CYAN}Using alias format: ${GREEN}$alias_template${NC}"
                
                update_config_with_aliases "$property_name" "$alias_template" "$MODEL_NAME" "$asset_name"
                
                # Special handling for Speed property to ensure it's in RPM
                if [[ "$property_name" == "Speed" ]]; then
                    echo -e "${GREEN}✅ Speed property will be configured with RPM units${NC}"
                    ensure_speed_has_rpm_unit
                    ensure_speed_notification_enabled
                fi
            done
            
            echo -e "\n${GREEN}Manual alias configuration completed${NC}"
        else
            echo -e "${YELLOW}Skipping alias configuration${NC}"
        fi
    fi
else
    # Even if user skips configuration, ensure we have a basic asset alias set up
    echo -e "${YELLOW}Setting up default configuration...${NC}"
    "$VENV_PATH/bin/python" -c "
import json
import os

config_file = 'config.json'

try:
    # Load existing config
    if not os.path.exists(config_file):
        with open(config_file, 'w') as f:
            json.dump({}, f)
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Ensure the structure exists
    if 'sitewise' not in config:
        config['sitewise'] = {}
    if 'asset' not in config['sitewise']:
        config['sitewise']['asset'] = {}
    
    # Always ensure we have an asset alias format defined
    config['sitewise']['asset']['asset_alias'] = '{model_name}/{asset_name}'
    config['sitewise']['asset']['notification_state'] = 'ENABLED'
    
    # Set default property aliases if not already defined
    if 'property_aliases' not in config['sitewise']['asset']:
        config['sitewise']['asset']['property_aliases'] = {
            'Speed': '{model_name}/{asset_name}/speed',
            'Serial': '{model_name}/{asset_name}/serial'
        }
    
    # Make sure Speed is set to RPM units if it exists
    if 'model' in config['sitewise'] and 'properties' in config['sitewise']['model']:
        speed_found = False
        for prop in config['sitewise']['model']['properties']:
            if prop.get('name') == 'Speed':
                prop['unit'] = 'RPM'
                speed_found = True
                break
        
        # If Speed property doesn't exist, add it
        if not speed_found:
            if 'properties' not in config['sitewise']['model']:
                config['sitewise']['model']['properties'] = []
            
            config['sitewise']['model']['properties'].append({
                'name': 'Speed',
                'dataType': 'DOUBLE',
                'unit': 'RPM',
                'type': {
                    'measurement': {}
                }
            })
    
    # Write back to the config file
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print('✅ Updated config.json with basic asset and property settings')
except Exception as e:
    print(f'Error updating config: {e}')
"
    echo -e "${YELLOW}Using default configuration with model_name/asset_name alias pattern and RPM units for Speed${NC}"
fi

# Create a special Python script to verify and fix property configuration after asset creation
cat > verify_asset_config.py << 'EOL'
#!/usr/bin/env python3
import boto3
import sys
import json
import time
from botocore.exceptions import ClientError

def load_config():
    """Load configuration from config.json file"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config.get('sitewise', {})
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
        return {}

def verify_and_fix_property_settings(asset_id):
    """Verify and fix property settings for an asset"""
    client = boto3.client('iotsitewise')
    success = True
    
    try:
        # Get asset properties
        response = client.list_asset_properties(assetId=asset_id)
        properties = response.get('assetPropertySummaries', [])
        
        config = load_config()
        asset_config = config.get('asset', {})
        property_aliases = asset_config.get('property_aliases', {})
        notification_state = asset_config.get('notification_state', 'ENABLED')
        
        print(f"\nVerifying configuration for {len(properties)} properties...")
        
        for prop in properties:
            prop_id = prop.get('id')
            # Safely get property name or fetch it from detailed property info
            if 'name' in prop:
                prop_name = prop['name']
            else:
                # Get detailed property information to find the name
                try:
                    prop_details = client.describe_asset_property(
                        assetId=asset_id,
                        propertyId=prop_id
                    )
                    prop_name = prop_details.get('assetProperty', {}).get('name', f"Property-{prop_id[-8:]}")
                except Exception as e:
                    prop_name = f"Property-{prop_id[-8:]}"  # Use a default name with part of the ID
                    print(f"Warning: Could not get property name for ID {prop_id}: {e}")
            
            # Get detailed property information
            try:
                prop_details = client.describe_asset_property(
                    assetId=asset_id,
                    propertyId=prop_id
                )
                
                property_alias = prop_details.get('assetProperty', {}).get('alias')
                property_unit = prop_details.get('assetProperty', {}).get('unit')
                property_notification = prop_details.get('assetProperty', {}).get('notification', {}).get('state')
                
                print(f"\nProperty: {prop_name}")
                print(f"  Current alias: {property_alias}")
                print(f"  Current unit: {property_unit}")
                print(f"  Current notification state: {property_notification}")
                
                # For Speed property, verify it has RPM unit
                if prop_name == 'Speed':
                    expected_unit = 'RPM'
                    if property_unit != expected_unit:
                        print(f"  Fixing unit: {property_unit} -> {expected_unit}")
                        try:
                            client.update_asset_property(
                                assetId=asset_id,
                                propertyId=prop_id,
                                propertyUnit=expected_unit
                            )
                            print("  ✅ Unit updated to RPM")
                        except ClientError as e:
                            print(f"  ❌ Error updating unit: {e}")
                            success = False
                
                # Verify it has the expected alias
                if prop_name in property_aliases:
                    # Get the expected alias from config
                    asset_details = client.describe_asset(assetId=asset_id)
                    asset_name = asset_details['assetName']
                    model_details = client.describe_asset_model(assetModelId=asset_details['assetModelId'])
                    model_name = model_details['assetModelName']
                    
                    expected_alias = property_aliases[prop_name].format(
                        model_name=model_name.lower(),
                        asset_name=asset_name.lower()
                    )
                    
                    if property_alias != expected_alias:
                        print(f"  Fixing alias: {property_alias} -> {expected_alias}")
                        try:
                            client.update_asset_property(
                                assetId=asset_id,
                                propertyId=prop_id,
                                propertyAlias=expected_alias
                            )
                            print(f"  ✅ Alias updated to {expected_alias}")
                        except ClientError as e:
                            print(f"  ❌ Error updating alias: {e}")
                            success = False
                
                # Verify notification state is ENABLED
                if property_notification != notification_state:
                    print(f"  Fixing notification state: {property_notification} -> {notification_state}")
                    try:
                        client.update_asset_property(
                            assetId=asset_id,
                            propertyId=prop_id,
                            propertyNotificationState=notification_state
                        )
                        print(f"  ✅ Notification state updated to {notification_state}")
                    except ClientError as e:
                        print(f"  ❌ Error updating notification state: {e}")
                        success = False
                
            except ClientError as e:
                print(f"  ❌ Error getting property details for {prop_name}: {e}")
                success = False
                
        # Double-check all properties again after updates
        if success:
            print("\nVerifying final configuration...")
            properties = client.list_asset_properties(assetId=asset_id).get('assetPropertySummaries', [])
            for prop in properties:
                prop_details = client.describe_asset_property(
                    assetId=asset_id,
                    propertyId=prop['id']
                )
                property_alias = prop_details.get('assetProperty', {}).get('alias', 'None')
                property_unit = prop_details.get('assetProperty', {}).get('unit', 'None')
                property_notification = prop_details.get('assetProperty', {}).get('notification', {}).get('state', 'DISABLED')
                
                print(f"- {prop['name']}: Alias = {property_alias}, Unit = {property_unit}, Notification = {property_notification}")
                
        return success
            
    except ClientError as e:
        print(f"Error verifying asset properties: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_asset_config.py <asset_id>")
        sys.exit(1)
    
    asset_id = sys.argv[1]
    print(f"Verifying and fixing property settings for asset ID: {asset_id}")
    
    success = verify_and_fix_property_settings(asset_id)
    
    if success:
        print("\n✅ All property settings have been verified and fixed if necessary")
    else:
        print("\n⚠️ Some property settings could not be fixed. Check the messages above for details.")
EOL

# Make the verification script executable
chmod +x verify_asset_config.py

# Explain what will happen
echo -e "\n${CYAN}This script will create a new IoT SiteWise asset based on the model with ID ${YELLOW}$MODEL_ID${NC}"
echo -e "The asset will be assigned a unique serial number automatically."
echo -e "The asset will have an alias in the format: ${GREEN}model_name/asset_name${NC}"
echo -e "Property aliases will follow the pattern: ${GREEN}model_name/asset_name/property_name${NC}"
echo -e "The Speed property will be configured with ${GREEN}RPM${NC} units."
echo -e "MQTT notifications will be ${GREEN}ENABLED${NC} for all properties."

# Ask for confirmation
echo ""
read -p "Do you want to proceed? (y/n): " confirm

if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    echo -e "\n${GREEN}Creating IoT SiteWise asset...${NC}"
    
    # Run the IoT SiteWise asset creation script using Python from the virtual environment
    ASSET_OUTPUT=$("$VENV_PATH/bin/python" create-iotsitewise-asset.py "$MODEL_ID")
    echo "$ASSET_OUTPUT"
    
    # Extract the asset ID from the output
    ASSET_ID=$(echo "$ASSET_OUTPUT" | grep -o "Asset ID: [a-zA-Z0-9\-]*" | cut -d " " -f 3)
    
    # Check if the script executed successfully
    if [ $? -eq 0 ] && [ -n "$ASSET_ID" ]; then
        echo -e "\n${GREEN}Asset creation completed with ID: ${CYAN}$ASSET_ID${NC}"
        
        # Run the verification script to ensure all properties are configured correctly
        echo -e "\n${YELLOW}Running additional verification to ensure all properties are configured correctly...${NC}"
        "$VENV_PATH/bin/python" verify_asset_config.py "$ASSET_ID"
        
        # Run the set_aliases script to set all the aliases
        echo -e "\n${YELLOW}Configuring aliases for asset properties using set_aliases.py...${NC}"
        if [ -f "set_aliases.py" ]; then
            "$VENV_PATH/bin/python" set_aliases.py --asset-id "$ASSET_ID"
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Successfully set aliases using set_aliases.py${NC}"
            else
                echo -e "${RED}Failed to set aliases using set_aliases.py${NC}"
            fi
        else
            echo -e "${RED}set_aliases.py script not found. Skipping alias configuration with this script.${NC}"
        fi
        
        echo -e "\n${GREEN}The asset and its properties have been configured with the model_name/asset_name alias pattern.${NC}"
        echo -e "${GREEN}Speed property has been configured with RPM units.${NC}"
        echo -e "${GREEN}MQTT notifications have been ENABLED for all properties.${NC}"
        echo -e "\n${YELLOW}Note: If aliases don't appear in AWS console immediately, it may take a few minutes for them to propagate.${NC}"
    else
        echo -e "\n${RED}The script encountered an error during execution or asset ID could not be determined.${NC}"
    fi
else
    echo -e "${YELLOW}Asset creation cancelled.${NC}"
fi

# Clean up temporary verification script
rm -f verify_asset_config.py

# Deactivate virtual environment
deactivate

echo -e "${CYAN}==============================================${NC}"