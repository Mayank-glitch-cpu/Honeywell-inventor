#!/usr/bin/env python3
import boto3
import json
import time
from botocore.exceptions import ClientError

def create_motor_model():
    """
    Creates an AWS IoT SiteWise model for a motor with serial number and speed measurement
    """
    # Initialize the AWS IoT SiteWise client
    sitewise = boto3.client('iotsitewise')
    
    print("Creating IoT SiteWise Motor model...")
    
    try:
        # Create the Motor model with properties
        response = sitewise.create_asset_model(
            assetModelName="Motor-scripted",
            assetModelDescription="Motor model with serial number and speed measurement",
            assetModelProperties=[
                # Serial Number property (string attribute)
                {
                    "name": "Serial",
                    "dataType": "STRING",
                    "type": {
                        "attribute": {
                            "defaultValue": "DEFAULT-SERIAL-00001"  # Changed from empty string to a default value
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