#!/usr/bin/env python3
import boto3
import json
import time
import os
import sys
import argparse
from botocore.exceptions import ClientError

# Import the configuration loader if available
try:
    from config_loader import ConfigLoader, initialize_env_from_config
    has_config_loader = True
except ImportError:
    has_config_loader = False

def load_config(model_type=None):
    """
    Load configuration from modular config files
    If model_type is specified, return configuration for that specific model
    """
    if has_config_loader:
        # Use the config loader if available
        config_loader = ConfigLoader()
        if model_type:
            return config_loader.get_sitewise_model_config().get(model_type, {})
        return config_loader.get_sitewise_model_config()
    else:
        # Fall back to direct file loading
        try:
            # Try modular config first
            if os.path.exists(os.path.join('configs', 'models.config.json')):
                with open(os.path.join('configs', 'models.config.json'), 'r') as f:
                    config = json.load(f)
                    if model_type:
                        return config.get('models', {}).get(model_type, {})
                    return config.get('models', {})
            # Fall back to monolithic config
            elif os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    sitewise_config = config.get('sitewise', {})
                    if model_type:
                        return sitewise_config.get('models', {}).get(model_type, {})
                    return sitewise_config.get('models', {})
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            return {}

def create_sitewise_model(model_type, auto_mode=False):
    """Create a SiteWise asset model based on configuration"""
    # Initialize environment variables
    if has_config_loader:
        initialize_env_from_config()
        
    model_config = load_config(model_type)
    if not model_config:
        print(f"Error: No configuration found for model type '{model_type}'")
        return None
    
    print(f"\nCreating IoT SiteWise model: {model_config.get('name')}")
    print(f"Description: {model_config.get('description', 'No description provided')}")
    
    # Skip confirmation if in auto mode
    if not auto_mode:
        confirm = input("\nDo you want to proceed with creating this model? (y/n): ")
        if confirm.lower() != 'y':
            print("Model creation aborted.")
            return None
    
    client = boto3.client('iotsitewise')
    
    try:
        # Extract model properties from configuration
        model_name = model_config.get('name')
        model_description = model_config.get('description', '')
        properties = model_config.get('properties', [])
        
        # Prepare property definitions
        property_definitions = []
        property_aliases = {}
        
        for prop in properties:
            data_type = prop.get('dataType', 'DOUBLE')
            
            # Ensure unit is never empty
            # If a unit is not provided or empty, use "none" as a default
            unit = prop.get('unit', 'none')
            if not unit:  # If empty string, use a default
                unit = 'none'
            
            property_def = {
                'name': prop.get('name'),
                'dataType': data_type,
                'unit': unit,
                'type': {
                    'measurement': {}
                }
            }
            
            # Handle different property types
            if prop.get('type') and 'attribute' in prop.get('type', {}):
                # Handle attribute type
                property_def['type'] = {
                    'attribute': {
                        'defaultValue': prop.get('type', {}).get('attribute', {}).get('defaultValue', '')
                    }
                }
                # Attribute properties don't need a unit
                if 'unit' in property_def:
                    del property_def['unit']
            elif prop.get('type', 'measurement') == 'transform':
                property_def['type'] = {
                    'transform': {
                        'expression': prop.get('expression', ''),
                        'variables': [
                            {
                                'name': var.get('name'),
                                'value': {
                                    'propertyId': var.get('propertyId', '')
                                }
                            } for var in prop.get('variables', [])
                        ]
                    }
                }
            elif prop.get('type', 'measurement') == 'metric':
                window = prop.get('window', 'TEN_MINUTES')
                property_def['type'] = {
                    'metric': {
                        'expression': prop.get('expression', ''),
                        'variables': [
                            {
                                'name': var.get('name'),
                                'value': {
                                    'propertyId': var.get('propertyId', '')
                                }
                            } for var in prop.get('variables', [])
                        ],
                        'window': {
                            'tumbling': {
                                'interval': window
                            }
                        }
                    }
                }
            
            property_definitions.append(property_def)
            
            # Store alias if defined
            if 'alias' in prop:
                property_aliases[prop.get('name')] = prop.get('alias')
        
        print(f"Creating asset model with {len(property_definitions)} properties")
        
        # Create the asset model
        response = client.create_asset_model(
            assetModelName=model_name,
            assetModelDescription=model_description,
            assetModelProperties=property_definitions
        )
        
        asset_model_id = response.get('assetModelId')
        print(f"\nModel creation initiated. Asset Model ID: {asset_model_id}")
        
        # Wait for the asset model to be active
        print("Waiting for model to become active...")
        while True:
            time.sleep(2)
            model = client.describe_asset_model(assetModelId=asset_model_id)
            model_status = model['assetModelStatus']['state']
            
            if model_status == "ACTIVE":
                print(f"\nModel successfully created!")
                print(f"Model ID: {asset_model_id}")
                print(f"Model Name: {model_name}")
                
                # Save property aliases to config for asset creation
                try:
                    # Get property IDs
                    property_ids = {}
                    for prop in model['assetModelProperties']:
                        property_ids[prop['name']] = prop['id']
                    
                    # Update property aliases with IDs
                    complete_aliases = {}
                    for prop_name, alias_template in property_aliases.items():
                        if prop_name in property_ids:
                            alias = alias_template.format(model_type=model_type)
                            complete_aliases[property_ids[prop_name]] = alias
                    
                    # Update configuration
                    try:
                        if has_config_loader:
                            config_loader = ConfigLoader()
                            sitewise_config = config_loader.config.get('sitewise', {})
                            if 'assets' not in sitewise_config:
                                sitewise_config['assets'] = {}
                            if model_type not in sitewise_config['assets']:
                                sitewise_config['assets'][model_type] = {}
                            sitewise_config['assets'][model_type]['model_id'] = asset_model_id
                            sitewise_config['assets'][model_type]['property_aliases'] = complete_aliases
                            config_loader.update_config(sitewise_config, 'sitewise')
                            print("Property aliases stored in config for asset creation")
                        else:
                            # Try to update modular config first
                            config_path = os.path.join('configs', 'models.config.json')
                            if os.path.exists(config_path):
                                with open(config_path, 'r') as f:
                                    config = json.load(f)
                                
                                if 'assets' not in config:
                                    config['assets'] = {}
                                if model_type not in config['assets']:
                                    config['assets'][model_type] = {}
                                
                                config['assets'][model_type]['model_id'] = asset_model_id
                                config['assets'][model_type]['property_aliases'] = complete_aliases
                                
                                with open(config_path, 'w') as f:
                                    json.dump(config, f, indent=2)
                                print("Property aliases stored in modular config for asset creation")
                            else:
                                # Fallback to monolithic config.json
                                with open('config.json', 'r') as f:
                                    config = json.load(f)
                                
                                if 'sitewise' not in config:
                                    config['sitewise'] = {}
                                if 'assets' not in config['sitewise']:
                                    config['sitewise']['assets'] = {}
                                if model_type not in config['sitewise']['assets']:
                                    config['sitewise']['assets'][model_type] = {}
                                
                                config['sitewise']['assets'][model_type]['model_id'] = asset_model_id
                                config['sitewise']['assets'][model_type]['property_aliases'] = complete_aliases
                                
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

def list_available_models():
    """List available model types from config.json"""
    config = load_config()
    
    if not config:
        print("No model definitions found in configuration")
        return []
    
    print("\nAvailable models in configuration:")
    print("---------------------------------")
    for i, (model_key, model_data) in enumerate(config.items(), 1):
        print(f"{i}. {model_key}: {model_data.get('name')}")
        print(f"   {model_data.get('description', 'No description')}")
        
    return list(config.keys())

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AWS IoT SiteWise Model Creator")
    parser.add_argument("--model-type", type=str, help="Model type to create")
    parser.add_argument("--auto", action="store_true", help="Run in non-interactive mode")
    parser.add_argument("--list", action="store_true", help="List available model types")
    
    # Also accept positional argument for backward compatibility
    parser.add_argument("model_type_positional", nargs="?", type=str, help="Model type (positional argument)")
    
    args = parser.parse_args()
    
    # If positional argument is provided but not the --model-type flag, use the positional one
    if args.model_type_positional and not args.model_type:
        args.model_type = args.model_type_positional
    
    return args

if __name__ == "__main__":
    print("AWS IoT SiteWise Model Creator")
    print("============================================")
    
    args = parse_arguments()
    
    # List available models if requested
    if args.list:
        list_available_models()
        sys.exit(0)
    
    # Get model type from arguments or prompt user
    model_type = None
    if args.model_type:
        model_type = args.model_type.lower()
    
    # If no model type provided, list available models and prompt user
    if not model_type:
        available_models = list_available_models()
        
        if not available_models:
            print("\nNo model configurations found. Please ensure your configuration is set up correctly.")
            sys.exit(1)
        
        while True:
            choice = input("\nEnter the number or name of the model type to create: ")
            try:
                # Check if input is a number
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(available_models):
                    model_type = available_models[choice_idx]
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                # Input is not a number, check if it's a valid model name
                if choice.lower() in available_models:
                    model_type = choice.lower()
                    break
                else:
                    print("Invalid model type. Please try again.")
    
    # Create the model
    if model_type:
        asset_model_id = create_sitewise_model(model_type, args.auto)
        if asset_model_id:
            print(f"\nNext step: Create assets using this model")
            print(f"Example: python create-iotsitewise-asset.py {asset_model_id} {model_type}")
        else:
            print("\nModel creation failed or was aborted.")
            sys.exit(1)
    else:
        print("No model type selected. Exiting.")
        sys.exit(1)