#!/usr/bin/env python3
import boto3
import time
import random
import datetime
import argparse
import json
import sys
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

def get_asset_by_alias(alias):
    """Find asset and property details by alias"""
    client = boto3.client('iotsitewise')
    try:
        # Look up property by alias
        response = client.describe_asset_property_by_external_id(
            externalId=alias
        )
        return {
            'asset_id': response.get('assetId'),
            'property_id': response.get('propertyId'),
            'alias': alias
        }
    except Exception as e:
        print(f"Error finding asset by alias {alias}: {e}")
        return None

def send_random_data(target, min_val=600.0, max_val=3600.0, interval=1.0, duration=None):
    """Send random RPM data to a SiteWise asset property"""
    client = boto3.client('iotsitewise')
    start_time = time.time()
    count = 0
    
    print(f"Starting data transmission to {target.get('alias') or ('asset ID: ' + target.get('asset_id'))}")
    print(f"Range: {min_val} to {max_val} RPM, interval: {interval}s")
    if duration:
        print(f"Will run for {duration} seconds")
    else:
        print("Will run until interrupted (Ctrl+C)")
    
    try:
        while True:
            current_time = time.time()
            if duration and (current_time - start_time > duration):
                print(f"\nDuration of {duration}s reached. Stopping.")
                break
                
            # Generate a random RPM value within the specified range
            rpm = random.uniform(min_val, max_val)
            
            # Create timestamp (seconds since epoch with nanoseconds)
            timestamp_seconds = int(time.time())
            timestamp_offset_nanos = int((time.time() - timestamp_seconds) * 1e9)
            
            # Prepare the data entry
            entry = {
                'entryId': str(count),
                'propertyValues': [
                    {
                        'value': {
                            'doubleValue': rpm
                        },
                        'timestamp': {
                            'timeInSeconds': timestamp_seconds,
                            'offsetInNanos': timestamp_offset_nanos
                        },
                        'quality': 'GOOD'
                    }
                ]
            }
            
            if 'property_id' in target and 'asset_id' in target:
                entry['propertyAlias'] = target.get('alias')
                entry['propertyId'] = target['property_id']
                entry['assetId'] = target['asset_id']
            elif 'alias' in target:
                entry['propertyAlias'] = target['alias']
            else:
                print("Error: Invalid target specification")
                break
            
            # Send the data
            try:
                response = client.batch_put_asset_property_value(
                    entries=[entry]
                )
                
                # Get current timestamp for display
                time_now = datetime.datetime.now().strftime("%H:%M:%S")
                
                # Check for errors
                if 'errorEntries' in response and response['errorEntries']:
                    print(f"[{time_now}] Error: {response['errorEntries'][0].get('errorMessage', 'Unknown error')}")
                else:
                    count += 1
                    if count % 10 == 0:  # Print status every 10 values
                        print(f"[{time_now}] Sent {count} values. Last value: {rpm:.2f} RPM")
                    else:
                        # Simple progress indicator
                        print(".", end="", flush=True)
                        
            except ClientError as e:
                print(f"\nError sending data: {e}")
                time.sleep(5)  # Wait before retry on error
            
            # Wait for the next interval
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nData sending interrupted by user.")
    
    print(f"Total values sent: {count}")
    return count

def main():
    """Main function to parse arguments and execute actions"""
    parser = argparse.ArgumentParser(description='Send random RPM data to AWS IoT SiteWise')
    parser.add_argument('--alias', type=str, help='Property alias to send data to')
    parser.add_argument('--asset-id', type=str, help='Asset ID to send data to')
    parser.add_argument('--min', type=float, help='Minimum RPM value')
    parser.add_argument('--max', type=float, help='Maximum RPM value')
    parser.add_argument('--interval', type=float, help='Interval between data points in seconds')
    parser.add_argument('--duration', type=float, help='Duration to run in seconds')
    parser.add_argument('--list-assets', action='store_true', help='List all assets and their properties')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    # Get default values from config or use hardcoded defaults
    min_val = args.min if args.min is not None else config.get('min_rpm', 600.0)
    max_val = args.max if args.max is not None else config.get('max_rpm', 3600.0)
    interval = args.interval if args.interval is not None else config.get('interval', 1.0)
    duration = args.duration if args.duration is not None else config.get('duration')
    
    # List all assets if requested
    if args.list_assets:
        from senddata import get_asset_info
        assets = get_asset_info()
        if assets:
            print("\nAvailable assets and properties:")
            for asset in assets:
                print(f"Asset: {asset['name']} (ID: {asset['id']})")
                for prop in asset['properties']:
                    alias = prop.get('alias', 'No alias')
                    print(f"  - {prop['name']} ({prop['dataType']}): {alias}")
        return
    
    # Handle sending data based on alias or asset ID
    if args.alias:
        target = get_asset_by_alias(args.alias)
        if target:
            send_random_data(target, min_val, max_val, interval, duration)
        else:
            print(f"Could not find a property with alias: {args.alias}")
    elif args.asset_id:
        # Try to find or set alias for Speed property
        from senddata import assign_alias_if_missing
        client = boto3.client('iotsitewise')
        alias = assign_alias_if_missing(client, args.asset_id)
        
        if alias:
            target = get_asset_by_alias(alias)
            if target:
                send_random_data(target, min_val, max_val, interval, duration)
            else:
                print(f"Could not find a property with the assigned alias: {alias}")
        else:
            print("Could not find or assign an alias for the Speed property")
    else:
        print("Please provide either --alias or --asset-id")
        parser.print_help()

if __name__ == "__main__":
    main()