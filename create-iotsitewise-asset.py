#!/usr/bin/env python3
import boto3
import json
import time
import sys
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
        return {
            "model": config_loader.get_sitewise_model_config(),
            "asset": config_loader.get_sitewise_asset_config()
        }
    else:
        # Fall back to direct file loading
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                return config.get('sitewise', {})
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            return {}

def create_motor_asset(asset_model_id):
    """
    Creates an AWS IoT SiteWise asset based on the motor model
    """
    if not asset_model_id:
        print("Error: No asset model ID provided")
        return None
        
    # Initialize the AWS IoT SiteWise client
    sitewise = boto3.client('iotsitewise')
    
    # Load configuration
    config = load_config()
    asset_config = config.get('asset', {})
    
    try:
        # First verify that the model exists and is active
        try:
            model = sitewise.describe_asset_model(assetModelId=asset_model_id)
            if model['assetModelStatus']['state'] != "ACTIVE":
                print(f"Error: Asset model {asset_model_id} is not in ACTIVE state. Current state: {model['assetModelStatus']['state']}")
                return None
        except ClientError as e:
            print(f"Error: Could not find asset model with ID {asset_model_id}: {e}")
            return None
        
        # Use model name in the asset name for better identification
        model_name = model['assetModelName']
        
        # Use name template from config or fallback
        name_template = asset_config.get('name_template', "{model_name}-{index}")
        index = asset_config.get('index', 1)
        asset_name = name_template.format(model_name=model_name.lower(), index=index)
        
        print(f"Creating IoT SiteWise Asset '{asset_name}' based on model '{model_name}'...")
        
        # Create the asset based on our model
        response = sitewise.create_asset(
            assetName=asset_name,
            assetModelId=asset_model_id
        )
        
        asset_id = response['assetId']
        print(f"Asset created with ID: {asset_id}")
        
        # Wait for the asset to be active
        print("Waiting for asset to become active...")
        asset_status = "CREATING"
        
        while asset_status == "CREATING":
            time.sleep(5)
            asset = sitewise.describe_asset(assetId=asset_id)
            asset_status = asset['assetStatus']['state']
            
            if asset_status == "ACTIVE":
                print("Asset is now active and ready to use!")
                
                try:
                    # HARDCODED ALIASES - Using fixed consistent naming patterns for aliases
                    # Define the base alias pattern based on model and asset name
                    base_alias = f"{model_name.lower()}/{asset_name.lower()}"
                    print(f"Using hardcoded base alias pattern: {base_alias}")
                    
                    # Hardcoded property aliases - these will be used regardless of config
                    hardcoded_aliases = {
                        "Speed": f"{base_alias}/speed",
                        "Serial": f"{base_alias}/serial"
                    }
                    
                    print("Using the following hardcoded aliases:")
                    for prop_name, alias in hardcoded_aliases.items():
                        print(f"- {prop_name}: {alias}")

                    # Update the properties and enable MQTT notifications
                    print("Fetching asset properties...")
                    paginator = sitewise.get_paginator('list_asset_properties')
                    property_pages = paginator.paginate(assetId=asset_id)
                    all_properties = []
                    
                    # Collect all properties from pagination
                    for page in property_pages:
                        if 'assetPropertySummaries' in page:
                            all_properties.extend(page['assetPropertySummaries'])
                    
                    print(f"Found {len(all_properties)} properties")
                    
                    # Process each property
                    for property_item in all_properties:
                        # Check for id field - this is required
                        if 'id' not in property_item:
                            print(f"Warning: Property missing ID: {property_item}")
                            continue
                            
                        property_id = property_item.get('id')
                        
                        # Get full property details from AWS
                        try:
                            prop_details = sitewise.describe_asset_property(
                                assetId=asset_id,
                                propertyId=property_id
                            )
                            
                            # Get the property name from the details
                            property_name = prop_details.get('assetProperty', {}).get('name')
                            if not property_name:
                                print(f"Warning: Could not get property name for {property_id}")
                                continue
                                
                            print(f"\nProcessing property: {property_name} (ID: {property_id})")
                            
                            # Check property type
                            property_type = None
                            if 'assetProperty' in prop_details and 'type' in prop_details['assetProperty']:
                                if 'measurement' in prop_details['assetProperty']['type']:
                                    property_type = 'measurement'
                                elif 'attribute' in prop_details['assetProperty']['type']:
                                    property_type = 'attribute'
                                    
                            print(f"Property type: {property_type}")
                            
                            # Check if we have a hardcoded alias for this property
                            if property_name in hardcoded_aliases:
                                alias = hardcoded_aliases[property_name]
                                print(f"Setting hardcoded alias '{alias}' for property '{property_name}'")
                                
                                # Set alias and enable notifications
                                try:
                                    sitewise.update_asset_property(
                                        assetId=asset_id,
                                        propertyId=property_id,
                                        propertyAlias=alias,
                                        propertyNotificationState='ENABLED'
                                    )
                                    print(f"✅ Alias '{alias}' and notifications set successfully for {property_name}")
                                    
                                    # For Speed property, ensure it's in RPM
                                    if property_name == "Speed" and property_type == 'measurement':
                                        try:
                                            sitewise.update_asset_property(
                                                assetId=asset_id,
                                                propertyId=property_id,
                                                propertyUnit="RPM"
                                            )
                                            print("✅ Speed property unit set to RPM")
                                        except ClientError as e:
                                            print(f"❌ Error: Could not set unit for Speed property: {e}")
                                            
                                except ClientError as e:
                                    print(f"❌ Error setting property configuration: {e}")
                            else:
                                # Use a default alias for properties not explicitly configured
                                default_alias = f"{base_alias}/{property_name.lower()}"
                                print(f"No hardcoded alias for {property_name}. Using default: {default_alias}")
                                
                                try:
                                    sitewise.update_asset_property(
                                        assetId=asset_id,
                                        propertyId=property_id,
                                        propertyAlias=default_alias,
                                        propertyNotificationState='ENABLED'
                                    )
                                    print(f"✅ Default alias '{default_alias}' and notifications set successfully")
                                except ClientError as e:
                                    print(f"❌ Error: Could not set default alias for {property_name}: {e}")
                                    
                            # Verify the property configuration
                            try:
                                prop_details = sitewise.describe_asset_property(
                                    assetId=asset_id,
                                    propertyId=property_id
                                )
                                current_alias = prop_details.get('assetProperty', {}).get('alias', 'None')
                                current_unit = prop_details.get('assetProperty', {}).get('unit', 'None')
                                notification_state = prop_details.get('assetProperty', {}).get('notification', {}).get('state', 'DISABLED')
                                
                                print(f"Verification: Alias = {current_alias}, Unit = {current_unit}, Notifications = {notification_state}")
                            except Exception as e:
                                print(f"Warning: Could not verify property settings: {e}")
                            
                        except Exception as e:
                            print(f"Error processing property {property_id}: {e}")
                    
                    # Update the serial number property with a unique value (if it exists)
                    serial_updated = False
                    serial_value = f"MOTOR-SN-{asset_id[-8:]}"
                    
                    for property_item in all_properties:
                        try:
                            prop_id = property_item.get('id')
                            if not prop_id:
                                continue
                                
                            prop_details = sitewise.describe_asset_property(
                                assetId=asset_id,
                                propertyId=prop_id
                            )
                            
                            property_name = prop_details.get('assetProperty', {}).get('name')
                            if property_name == 'Serial':
                                print(f"Found Serial property, updating with value: {serial_value}...")
                                try:
                                    sitewise.update_asset_property(
                                        assetId=asset_id,
                                        propertyId=prop_id,
                                        propertyNotificationState='ENABLED',
                                        propertyValue={
                                            'value': {
                                                'stringValue': serial_value
                                            }
                                        }
                                    )
                                    print("Serial property updated!")
                                    serial_updated = True
                                    break
                                except ClientError as e:
                                    print(f"Warning: Could not update Serial property: {e}")
                        except Exception:
                            continue
                    
                    if not serial_updated:
                        print("Note: Serial property not found or could not be updated")
                    
                    # Wait for aliases to propagate
                    print("\n⏱️ Waiting briefly for property configurations to fully propagate in AWS...")
                    time.sleep(5)
                    
                    # Generate code example for connecting with senddata.py
                    print("\n✅ Asset creation complete")
                    print("\nTo send data to this asset using senddata.py, use one of these commands:")
                    
                    # Find the Speed property alias
                    speed_alias = None
                    for prop in all_properties:
                        try:
                            prop_id = prop.get('id')
                            if not prop_id:
                                continue
                                
                            prop_details = sitewise.describe_asset_property(
                                assetId=asset_id,
                                propertyId=prop_id
                            )
                            
                            property_name = prop_details.get('assetProperty', {}).get('name')
                            if property_name == 'Speed':
                                speed_alias = prop_details.get('assetProperty', {}).get('alias')
                                break
                        except Exception:
                            continue
                    
                    # Create the senddata.py command example
                    if speed_alias:
                        print(f"\npython senddata.py --alias \"{speed_alias}\" --min 600 --max 3600 --interval 1.0")
                        # Also create a simple script to make it easier to run
                        with open('send-mock-data.sh', 'w') as f:
                            f.write(f'#!/bin/bash\n\n# This script sends mock RPM data to your asset\nsource venv-sitewise/bin/activate\npython senddata.py --alias "{speed_alias}" --min 600 --max 3600 --interval 1.0\n')
                        os.chmod('send-mock-data.sh', 0o755)
                        print("\nA helper script 'send-mock-data.sh' has been created for easy data sending.")
                    else:
                        print(f"\npython senddata.py --asset-id {asset_id}")
                    
                    # Update config file with index incremented for next asset creation
                    try:
                        if has_config_loader:
                            config_loader = ConfigLoader()
                            asset_config = config_loader.get_sitewise_asset_config()
                            asset_config['index'] = index + 1
                            config_loader.save_config()
                            print("\nSuccessfully updated asset index in configuration")
                        else:
                            with open('config.json', 'r') as f:
                                config = json.load(f)
                            if 'sitewise' in config and 'asset' in config['sitewise']:
                                config['sitewise']['asset']['index'] = index + 1
                                with open('config.json', 'w') as f:
                                    json.dump(config, f, indent=2)
                            print("\nConfiguration updated in config.json")
                    except Exception as e:
                        print(f"\nNote: Could not update asset index in config: {e}")
                    
                except Exception as e:
                    print(f"Error handling properties: {e}")
                
                return asset_id
            elif asset_status == "FAILED":
                error = asset['assetStatus'].get('error', {}).get('message', 'Unknown error')
                print(f"Asset creation failed: {error}")
                return None
            else:
                print(f"Current asset status: {asset_status}...")
        
    except ClientError as e:
        print(f"Error creating IoT SiteWise asset: {e}")
        return None

def create_verification_script(asset_id):
    """Create a fixed verification script that handles property structures correctly"""
    script_content = """#!/usr/bin/env python3
import boto3
import sys
import json
import time
from botocore.exceptions import ClientError

def load_config():
    \"\"\"Load configuration from config.json file\"\"\"
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config.get('sitewise', {})
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
        return {}

def verify_and_fix_property_settings(asset_id):
    \"\"\"Verify and fix property settings for an asset\"\"\"
    client = boto3.client('iotsitewise')
    success = True
    
    try:
        # Get asset properties 
        paginator = client.get_paginator('list_asset_properties')
        property_pages = paginator.paginate(assetId=asset_id)
        all_properties = []
        
        # Collect all properties from pagination
        for page in property_pages:
            if 'assetPropertySummaries' in page:
                all_properties.extend(page['assetPropertySummaries'])
        
        config = load_config()
        asset_config = config.get('asset', {})
        property_aliases = asset_config.get('property_aliases', {})
        notification_state = asset_config.get('notification_state', 'ENABLED')
        
        print(f"\\nVerifying configuration for {len(all_properties)} properties...")
        
        for prop in all_properties:
            # Check if we have the ID, which is the minimum required field
            if 'id' not in prop:
                print(f"Warning: Property missing ID field: {prop}")
                continue
                
            prop_id = prop['id']
            
            # Get detailed property information
            try:
                prop_details = client.describe_asset_property(
                    assetId=asset_id,
                    propertyId=prop_id
                )
                
                # Get property name from the full details if not in the summary
                prop_name = prop.get('name') if 'name' in prop else prop_details.get('assetProperty', {}).get('name', f"Property-{prop_id[-8:]}")
                property_alias = prop_details.get('assetProperty', {}).get('alias')
                property_unit = prop_details.get('assetProperty', {}).get('unit')
                property_notification = prop_details.get('assetProperty', {}).get('notification', {}).get('state')
                
                print(f"\\nProperty: {prop_name}")
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
                if property_notification != 'ENABLED':
                    print(f"  Fixing notification state: {property_notification} -> ENABLED")
                    try:
                        client.update_asset_property(
                            assetId=asset_id,
                            propertyId=prop_id,
                            propertyNotificationState='ENABLED'
                        )
                        print("  ✅ Notification state updated to ENABLED")
                    except ClientError as e:
                        print(f"  ❌ Error updating notification state: {e}")
                        success = False
                        
            except ClientError as e:
                print(f"Error getting property details for property ID {prop_id}: {e}")
                success = False
                
        # Double-check all properties again after updates
        if success:
            print("\\nVerifying final configuration...")
            verification_pages = client.get_paginator('list_asset_properties').paginate(assetId=asset_id)
            verification_properties = []
            for page in verification_pages:
                if 'assetPropertySummaries' in page:
                    verification_properties.extend(page['assetPropertySummaries'])
                    
            for prop in verification_properties:
                if 'id' not in prop:
                    continue
                    
                prop_details = client.describe_asset_property(
                    assetId=asset_id,
                    propertyId=prop['id']
                )
                
                prop_name = prop.get('name') if 'name' in prop else prop_details.get('assetProperty', {}).get('name', f"Property-{prop['id'][-8:]}")
                property_alias = prop_details.get('assetProperty', {}).get('alias', 'None')
                property_unit = prop_details.get('assetProperty', {}).get('unit', 'None')
                property_notification = prop_details.get('assetProperty', {}).get('notification', {}).get('state', 'DISABLED')
                
                print(f"- {prop_name}: Alias = {property_alias}, Unit = {property_unit}, Notification = {property_notification}")
                
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
        print("\\n✅ All property settings have been verified and fixed if necessary")
    else:
        print("\\n⚠️ Some property settings could not be fixed. Check the messages above for details.")
"""
    
    # Write the script to a file
    with open('verify_asset_config.py', 'w') as f:
        f.write(script_content)
    
    # Make it executable
    os.chmod('verify_asset_config.py', 0o755)
    print("Created fixed verification script: verify_asset_config.py")

if __name__ == "__main__":
    print("AWS IoT SiteWise Asset Creator")
    print("==============================")
    
    # Check if model ID was provided as argument
    if len(sys.argv) > 1:
        asset_model_id = sys.argv[1]
    else:
        # Ask for model ID if not provided as argument
        asset_model_id = input("Enter the asset model ID: ")
    
    if not asset_model_id:
        print("Error: No asset model ID provided. Exiting.")
        sys.exit(1)
    
    # Create the asset based on the model
    asset_id = create_motor_asset(asset_model_id)
    
    if asset_id:
        print("\nAsset setup complete!")
        print(f"Asset ID: {asset_id}")
        print("\nYou can now access your asset in the AWS IoT SiteWise console.")
        print("Navigate to Assets section to view your new asset")
        print("\nMQTT notifications have been enabled for all asset properties.")
    else:
        print("\nFailed to create the asset.")