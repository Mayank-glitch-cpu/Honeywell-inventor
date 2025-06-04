#!/usr/bin/env python3
import boto3
import json
import time
import sys
import os
import re
import argparse
from botocore.exceptions import ClientError

# Import the configuration loader if available
try:
    from config_loader import ConfigLoader
    has_config_loader = True
except ImportError:
    has_config_loader = False

def load_config(model_type=None):
    """
    Load configuration from modular config files
    If model_type is specified, return configuration for that specific asset type
    """
    if has_config_loader:
        # Use the config loader if available
        config_loader = ConfigLoader()
        if model_type:
            return config_loader.get_sitewise_asset_config(model_type)
        return config_loader.get_sitewise_asset_config()
    else:
        # Fall back to direct file loading
        try:
            config_dir = 'configs'
            model_config_path = os.path.join(config_dir, 'models.config.json')
            
            if os.path.exists(model_config_path):
                with open(model_config_path, 'r') as f:
                    config = json.load(f)
                    assets = config.get('assets', {})
                    if model_type:
                        return assets.get(model_type, {})
                    return assets
            
            # Legacy fallback to config.json
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    sitewise_config = config.get('sitewise', {})
                    
                    if model_type:
                        return sitewise_config.get('assets', {}).get(model_type, {})
                    return sitewise_config.get('assets', {})
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            return {}

def get_model_type_from_id(asset_model_id):
    """Determine model type from asset model ID by querying AWS"""
    try:
        # Create AWS IoT SiteWise client
        client = boto3.client('iotsitewise')
        
        # Get the model details
        response = client.describe_asset_model(assetModelId=asset_model_id)
        model_name = response.get('assetModelName', '')
        
        # Get all model types from config
        if has_config_loader:
            config_loader = ConfigLoader()
            all_models = config_loader.get_sitewise_model_config()
        else:
            config_dir = 'configs'
            model_config_path = os.path.join(config_dir, 'models.config.json')
            
            if os.path.exists(model_config_path):
                with open(model_config_path, 'r') as f:
                    config = json.load(f)
                    all_models = config.get('models', {})
            else:
                # Legacy fallback to config.json
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    all_models = config.get('sitewise', {}).get('models', {})
        
        # Find matching model type
        for model_type, model_data in all_models.items():
            if model_data.get('name') == model_name:
                return model_type
        
        # If no exact match found, try to infer from name
        for model_type in all_models.keys():
            if model_type.replace('_', '').lower() in model_name.replace(' ', '').lower():
                return model_type
        
        return None
    except Exception as e:
        print(f"Error determining model type: {e}")
        return None

def create_cookie_factory_asset(asset_model_id, model_type=None, non_interactive=False):
    """
    Create an AWS IoT SiteWise asset based on the specified model ID and type
    """
    # Determine model type if not provided
    if not model_type:
        model_type = get_model_type_from_id(asset_model_id)
        
        if not model_type:
            model_type = 'generic'
            print(f"Warning: Could not determine model type for ID: {asset_model_id}")
            print("Using generic approach for asset creation")
    
    # Get asset configuration for this model type
    asset_config = load_config(model_type)
    
    if not asset_config and model_type != 'generic':
        print(f"Warning: No asset configuration found for model type '{model_type}'")
        if not non_interactive:
            proceed = input("Do you want to proceed with generic asset creation? (y/n): ")
            if proceed.lower() != 'y':
                print("Asset creation cancelled")
                return None
        model_type = 'generic'
        print("Using generic approach for asset creation")
    
    # Create AWS IoT SiteWise client
    client = boto3.client('iotsitewise')
    
    # Get the model name
    try:
        model_response = client.describe_asset_model(assetModelId=asset_model_id)
        model_name = model_response.get('assetModelName', 'Unknown')
    except ClientError as e:
        print(f"Error retrieving model information: {e}")
        return None
    
    print(f"Creating asset based on model: {model_name} (ID: {asset_model_id})")
    
    # Determine asset name and other parameters
    if model_type != 'generic' and asset_config:
        # Get the index from config
        index = asset_config.get('index', 1)
        
        # Generate asset name using template
        name_template = asset_config.get('name_template', '{model_name}-{index}')
        asset_name = name_template.format(model_name=model_name.replace(' ', '-').lower(), index=index)
        
        # Get notification state preference
        notification_state = asset_config.get('notification_state', 'ENABLED')
        
        print(f"Using configuration for model type: {model_type}")
        print(f"Asset name: {asset_name}")
    else:
        # Generic approach without configuration
        index = 1
        asset_name = f"{model_name.replace(' ', '-').lower()}-{index}"
        notification_state = 'ENABLED'
        
        print(f"Using generic asset creation")
        print(f"Asset name: {asset_name}")
    
    if not non_interactive:
        # Ask for confirmation before proceeding
        confirm = input("Do you want to proceed with asset creation? (y/n): ")
        if confirm.lower() != 'y':
            print("Asset creation cancelled")
            return None
    
    # Create the asset
    try:
        print("Creating IoT SiteWise asset...")
        response = client.create_asset(
            assetName=asset_name,
            assetModelId=asset_model_id,
            assetProperties=[{
                'id': prop_id,
                'notification': {'state': notification_state}
            } for prop_id in ['*']]  # Use '*' for all properties
        )
        
        asset_id = response.get('assetId')
        print(f"Asset creation initiated. Asset ID: {asset_id}")
        
        # Wait for asset creation to complete
        print("Waiting for asset to be active...")
        status = "CREATING"
        while status in ["CREATING", "UPDATING"]:
            time.sleep(2)
            asset = client.describe_asset(assetId=asset_id)
            status = asset['assetStatus']['state']
            
            if status == "ACTIVE":
                print("\nAsset is now active!")
                
                # Configure asset properties with aliases
                # This helps with data ingestion by allowing data to be sent to aliases
                try:
                    if model_type != 'generic' and asset_config:
                        property_aliases = asset_config.get('property_aliases', {})
                        
                        if property_aliases:
                            print("Configuring property aliases...")
                            
                            # Get all asset properties
                            properties = client.list_asset_properties(assetId=asset_id)
                            
                            # Configure each property with an alias
                            for prop in properties.get('assetPropertySummaries', []):
                                prop_id = prop.get('id')
                                prop_name = prop.get('name')
                                
                                if prop_name in property_aliases:
                                    # Get the alias template
                                    alias_template = property_aliases[prop_name]
                                    
                                    # Format the alias with variables
                                    alias = alias_template
                                    if '{model_name}' in alias_template:
                                        alias = alias.replace('{model_name}', model_name.replace(' ', '_').lower())
                                    if '{asset_name}' in alias_template:
                                        alias = alias.replace('{asset_name}', asset_name.replace('-', '_'))
                                    
                                    try:
                                        # Update the property with the alias
                                        client.update_asset_property(
                                            assetId=asset_id,
                                            propertyId=prop_id,
                                            propertyAlias=alias,
                                            propertyNotificationState=notification_state
                                        )
                                        print(f"Set alias for {prop_name}: {alias}")
                                        
                                        # Example command for data ingestion
                                        example_range = f"--min {80} --max {120}"
                                        print(f"Example command: python senddata.py --alias \"{alias}\" {example_range} --interval 1.0")
                                    except Exception:
                                        continue
                    
                    # Update config file with index incremented for next asset creation
                    try:
                        if has_config_loader and model_type != 'generic':
                            config_loader = ConfigLoader()
                            sitewise_config = config_loader.config.get('sitewise', {})
                            if 'assets' in sitewise_config and model_type in sitewise_config['assets']:
                                sitewise_config['assets'][model_type]['index'] = index + 1
                                config_loader.save_config('sitewise')
                                print("\nSuccessfully updated asset index in configuration")
                        elif model_type != 'generic':
                            config_path = os.path.join('configs', 'models.config.json')
                            if os.path.exists(config_path):
                                with open(config_path, 'r') as f:
                                    config = json.load(f)
                                
                                if 'assets' in config and model_type in config['assets']:
                                    config['assets'][model_type]['index'] = index + 1
                                    with open(config_path, 'w') as f:
                                        json.dump(config, f, indent=2)
                                    print("\nConfiguration updated in models.config.json")
                    except Exception as e:
                        print(f"\nNote: Could not update asset index in config: {e}")
                    
                except Exception as e:
                    print(f"Error handling properties: {e}")
                
                return asset_id
            elif status == "FAILED":
                error = asset['assetStatus'].get('error', {}).get('message', 'Unknown error')
                print(f"Asset creation failed: {error}")
                return None
            else:
                print(f"Current asset status: {status}...")
        
    except ClientError as e:
        print(f"Error creating IoT SiteWise asset: {e}")
        return None

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Create AWS IoT SiteWise asset')
    parser.add_argument('asset_model_id', nargs='?', help='The SiteWise model ID to create an asset from')
    parser.add_argument('model_type', nargs='?', help='The model type (e.g., dough_mixer)')
    parser.add_argument('--non-interactive', action='store_true', help='Run in non-interactive mode (no prompts)')
    return parser.parse_args()

if __name__ == "__main__":
    print("AWS IoT SiteWise Cookie Factory Asset Creator")
    print("============================================")
    
    args = parse_args()
    
    if not args.asset_model_id:
        print("\nError: Asset model ID is required.")
        print("Usage: python create-iotsitewise-asset.py <asset_model_id> [model_type]")
        sys.exit(1)
    
    # Create the asset
    asset_id = create_cookie_factory_asset(args.asset_model_id, args.model_type, args.non_interactive)
    
    if asset_id:
        print(f"\nAsset creation completed successfully.")
        print(f"Asset ID: {asset_id}")
        
        # Show instructions for alias setup
        if os.path.exists('set_aliases.py'):
            if args.model_type:
                print(f"\nTo set up aliases for the asset, run:")
                print(f"python set_aliases.py --asset-id {asset_id} --model-type {args.model_type}")
            else:
                print(f"\nTo set up aliases for the asset, run:")
                print(f"python set_aliases.py --asset-id {asset_id}")
        
        # Show instructions for sending data
        print(f"\nTo send data to this asset, you can use the senddata.py script.")
        sys.exit(0)
    else:
        print("\nAsset creation failed.")
        sys.exit(1)