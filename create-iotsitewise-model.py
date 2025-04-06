#!/usr/bin/env python3
import boto3
import json
import time
import os
from botocore.exceptions import ClientError

# Import the configuration loader if available
try:
    from config_loader import ConfigLoader
    has_config_loader = True
except ImportError:
    has_config_loader = False

def load_config():
    """Load configuration from config.json file"""
    if has_config_loader:
        # Use the config loader if available
        config_loader = ConfigLoader()
        model_config = config_loader.get_sitewise_model_config()
        return model_config
    else:
        # Fall back to direct file loading
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                return config.get('sitewise', {}).get('model', {})
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            return {}

def create_motor_model():
    """
    Creates an AWS IoT SiteWise model for a motor with serial number and speed measurement
    Uses configuration from config.json if available
    """
    # Initialize the AWS IoT SiteWise client
    sitewise = boto3.client('iotsitewise')
    
    print("Creating IoT SiteWise Motor model...")
    
    # Load configuration
    config = load_config()
    
    # Use configuration or fallbacks
    model_name = config.get('name', "Motor-scripted")
    model_description = config.get('description', "Motor model with serial number and speed measurement")
    properties = config.get('properties', [])
    
    # Store aliases for later reference but don't include in model creation
    property_aliases = {}
    
    # Prepare the properties list - either from config or defaults
    asset_model_properties = []
    
    if properties:
        print("Using properties from configuration...")
        for prop in properties:
            # Convert config property to SiteWise API format
            property_def = {
                "name": prop.get('name'),
                "dataType": prop.get('dataType')
            }
            
            # Add unit if specified
            if 'unit' in prop:
                property_def["unit"] = prop.get('unit')
                
            # Add property type (attribute or measurement)
            if 'type' in prop:
                property_def["type"] = prop.get('type')
                
            # Store alias separately - don't include in property_def
            if 'alias' in prop:
                property_aliases[prop.get('name')] = prop.get('alias')
                print(f"Found alias '{prop.get('alias')}' for property '{prop.get('name')}' - will be applied during asset creation")
                
            asset_model_properties.append(property_def)
    else:
        # Use hardcoded defaults if no config is available
        print("No property configuration found, using default properties...")
        asset_model_properties = [
            # Serial Number property (string attribute)
            {
                "name": "Serial",
                "dataType": "STRING",
                "type": {
                    "attribute": {
                        "defaultValue": "DEFAULT-SERIAL-00001"
                    }
                }
            },
            # Speed measurement property (double with unit RPM)
            {
                "name": "Speed",
                "dataType": "DOUBLE",
                "unit": "RPM",
                "type": {
                    "measurement": {}
                }
            }
        ]
        
        # Store default aliases
        property_aliases = {
            "Speed": "motor_scripted_1/motor_speed",
            "Serial": "motor_scripted_1/serial_number"
        }
    
    try:
        # Create the Motor model with properties
        response = sitewise.create_asset_model(
            assetModelName=model_name,
            assetModelDescription=model_description,
            assetModelProperties=asset_model_properties
        )
        
        asset_model_id = response['assetModelId']
        print(f"Motor model created with ID: {asset_model_id}")
        
        # Wait for the model to be active
        print("Waiting for model to become active...")
        model_status = "CREATING"
        
        while model_status == "CREATING":
            time.sleep(5)
            model = sitewise.describe_asset_model(assetModelId=asset_model_id)
            model_status = model['assetModelStatus']['state']
            
            if model_status == "ACTIVE":
                print("Motor model is now active and ready to use!")
                
                # Store property aliases in config for asset creation step
                if property_aliases:
                    try:
                        if has_config_loader:
                            # Use config_loader to update the config
                            config_loader = ConfigLoader()
                            sitewise_config = config_loader.config.get('sitewise', {})
                            if 'asset' not in sitewise_config:
                                sitewise_config['asset'] = {}
                            sitewise_config['asset']['property_aliases'] = property_aliases
                            config_loader.save_config()
                            print("Property aliases stored in config for asset creation")
                        else:
                            # Manually update config file
                            try:
                                with open('config.json', 'r') as f:
                                    config = json.load(f)
                                if 'sitewise' not in config:
                                    config['sitewise'] = {}
                                if 'asset' not in config['sitewise']:
                                    config['sitewise']['asset'] = {}
                                config['sitewise']['asset']['property_aliases'] = property_aliases
                                with open('config.json', 'w') as f:
                                    json.dump(config, f, indent=2)
                                print("Property aliases stored in config for asset creation")
                            except Exception as e:
                                print(f"Could not update config file with aliases: {e}")
                    except Exception as e:
                        print(f"Error saving property aliases to config: {e}")
                
                return asset_model_id
            elif model_status == "FAILED":
                error = model['assetModelStatus'].get('error', {}).get('message', 'Unknown error')
                print(f"Model creation failed: {error}")
                return None
            else:
                print(f"Current status: {model_status}...")
        
    except ClientError as e:
        print(f"Error creating IoT SiteWise model: {e}")
        return None

if __name__ == "__main__":
    print("AWS IoT SiteWise Motor Model Creator")
    print("====================================")
    
    # Create the model
    asset_model_id = create_motor_model()
    
    if asset_model_id:
        print("\nModel setup complete!")
        print(f"Model ID: {asset_model_id}")
        print("\nYou can now access your model in the AWS IoT SiteWise console.")
        print("Navigate to Models section to view your new Motor-scripted model")
    else:
        print("\nFailed to create the Motor model.")