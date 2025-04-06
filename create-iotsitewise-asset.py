#!/usr/bin/env python3
import boto3
import json
import time
import sys
from botocore.exceptions import ClientError

def create_motor_asset(asset_model_id):
    """
    Creates an AWS IoT SiteWise asset based on the motor model
    """
    if not asset_model_id:
        print("Error: No asset model ID provided")
        return None
        
    # Initialize the AWS IoT SiteWise client
    sitewise = boto3.client('iotsitewise')
    
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
        asset_name = f"{model_name.lower()}-1"
        
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
                    # Update the properties and enable MQTT notifications
                    print("Fetching asset properties...")
                    property_details = sitewise.list_asset_properties(assetId=asset_id)
                    
                    # Debug: Print the structure of the response to understand the keys
                    print("Property structure for debugging:")
                    for prop in property_details.get('assetPropertySummaries', []):
                        print(f"Property keys: {list(prop.keys())}")
                        break
                    
                    # Enable MQTT notifications for all properties
                    print("Enabling MQTT notifications for all properties...")
                    for property_item in property_details.get('assetPropertySummaries', []):
                        property_id = property_item.get('id')
                        property_name = property_item.get('propertyName', property_item.get('name', 'Unknown'))
                        
                        if property_id:
                            try:
                                print(f"Enabling notifications for property: {property_name}")
                                sitewise.update_asset_property(
                                    assetId=asset_id,
                                    propertyId=property_id,
                                    propertyNotificationState='ENABLED'
                                )
                                print(f"Notifications enabled for {property_name}")
                            except ClientError as e:
                                print(f"Warning: Could not enable notifications for {property_name}: {e}")
                    
                    # Update the serial number property with a unique value (if it exists)
                    serial_updated = False
                    for property_item in property_details.get('assetPropertySummaries', []):
                        # Check for 'propertyName' for the Serial property
                        property_name = property_item.get('propertyName', property_item.get('name', ''))
                        if property_name == 'Serial':
                            print("Found Serial property, updating with a unique value...")
                            try:
                                sitewise.update_asset_property(
                                    assetId=asset_id,
                                    propertyId=property_item['id'],
                                    propertyNotificationState='ENABLED',
                                    propertyValue={
                                        'value': {
                                            'stringValue': f"MOTOR-SN-{asset_id[-8:]}"
                                        }
                                    }
                                )
                                print("Serial property updated!")
                                serial_updated = True
                                break
                            except ClientError as e:
                                print(f"Warning: Could not update Serial property: {e}")
                    
                    if not serial_updated:
                        print("Note: Serial property not found or could not be updated")
                        # Print available properties for debugging
                        print("Available properties:")
                        for prop in property_details.get('assetPropertySummaries', []):
                            prop_name = prop.get('propertyName', prop.get('name', 'Unknown'))
                            print(f"- {prop_name} (ID: {prop.get('id', 'Unknown')})")
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