#!/usr/bin/env python3
import boto3
import time
import sys
import re
import argparse
from botocore.exceptions import ClientError

def is_valid_asset_id(asset_id):
    """
    Validates that asset ID is in proper format (36-char UUID format)
    Returns True if valid, False otherwise
    """
    # Check for standard UUID format (8-4-4-4-12 hex digits)
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if uuid_pattern.match(asset_id):
        return True
    
    # Secondary check for length (AWS requires minimum 36 chars)
    if len(asset_id) < 36:
        return False
    
    # If we get here, it's not a standard UUID but is at least 36 chars
    # AWS might accept some variations, so return True
    return True

def assign_aliases_to_asset(asset_id, alias_template="{model_name}/{asset_name}/{property_name}", unit_overrides=None):
    """
    Assigns aliases and enables MQTT notifications for all measurement-type properties of a SiteWise asset.
    Optionally sets property units (e.g., RPM for Speed).
    """
    sitewise = boto3.client('iotsitewise')

    # Fetch asset and model details
    try:
        asset = sitewise.describe_asset(assetId=asset_id)
        asset_name = asset['assetName']
        model_id = asset['assetModelId']
        model = sitewise.describe_asset_model(assetModelId=model_id)
        model_name = model['assetModelName']
        print(f"\n🔧 Processing asset: {asset_name} (ID: {asset_id}) based on model: {model_name}")
    except ClientError as e:
        print(f"❌ Failed to describe asset: {e}")
        return

    # Get all properties (pagination)
    paginator = sitewise.get_paginator('list_asset_properties')
    all_props = []
    for page in paginator.paginate(assetId=asset_id):
        all_props.extend(page.get('assetPropertySummaries', []))

    print(f"📦 Found {len(all_props)} properties")

    # Update each measurement-type property
    for prop in all_props:
        prop_id = prop.get("id")
        try:
            # Get full property details
            prop_details = sitewise.describe_asset_property(assetId=asset_id, propertyId=prop_id)
            asset_prop = prop_details.get("assetProperty", {})
            prop_name = asset_prop.get("name", f"property-{prop_id[:6]}")
            prop_type_keys = asset_prop.get("type", {}).keys()
            is_measurement = "measurement" in prop_type_keys

            print(f"\n📍 Property: {prop_name} (ID: {prop_id})")
            print(f"   Type: {'Measurement' if is_measurement else 'Other'}")

            if not is_measurement:
                print("   ⏩ Skipping non-measurement property")
                continue

            # Build alias
            alias = alias_template.format(
                model_name=model_name.lower(),
                asset_name=asset_name.lower(),
                property_name=prop_name.lower()
            )

            # Prepare update payload
            update_args = {
                "assetId": asset_id,
                "propertyId": prop_id,
                "propertyAlias": alias,
                "propertyNotificationState": "ENABLED"
            }

            # Optional unit override
            if unit_overrides and prop_name in unit_overrides:
                update_args["propertyUnit"] = unit_overrides[prop_name]
                print(f"   📏 Setting unit: {unit_overrides[prop_name]}")

            # Apply the update
            sitewise.update_asset_property(**update_args)
            print(f"   ✅ Alias set to: {alias}")
            print(f"   ✅ MQTT Notification: ENABLED")

        except ClientError as e:
            print(f"   ❌ Failed to update property {prop_id}: {e}")

    print("\n✅ All applicable aliases and notifications updated.\n")

# ---------- Entry point ----------
if __name__ == "__main__":
    # Parse arguments to handle both positional and named (--asset-id) formats
    parser = argparse.ArgumentParser(description='Set aliases and configure properties for IoT SiteWise assets')
    parser.add_argument('asset_id', nargs='?', help='Asset ID (positional argument)')
    parser.add_argument('--asset-id', dest='asset_id_flag', help='Asset ID (named argument)')
    
    args = parser.parse_args()
    
    # Get the asset ID from either the positional or named argument
    asset_id = args.asset_id or args.asset_id_flag
    
    if not asset_id:
        print("Usage: python set_aliases.py <asset_id> OR python set_aliases.py --asset-id <asset_id>")
        sys.exit(1)

    # Validate asset ID format
    if not is_valid_asset_id(asset_id):
        print(f"❌ Invalid asset ID format: {asset_id}")
        print("Asset ID should be 36 characters in UUID format (e.g., f6bbf9db-2771-480e-85cf-e22d154a1705)")
        sys.exit(1)

    # Optional: override units for specific property names
    unit_overrides = {
        "Speed": "RPM"
    }

    assign_aliases_to_asset(
        asset_id=asset_id,
        alias_template="{model_name}/{asset_name}/{property_name}",
        unit_overrides=unit_overrides
    )
