#!/usr/bin/env python3
import boto3
import time
import json
import sys
import os
from botocore.exceptions import ClientError

# Import the configuration loader
from config_loader import ConfigLoader, initialize_env_from_config

def delete_entity(workspace_id, entity_id, twinmaker_client=None):
    """
    Delete an entity to allow for clean recreation
    
    Parameters:
    workspace_id (str): The ID of the workspace
    entity_id (str): The ID of the entity to delete
    twinmaker_client: Optional boto3 twinmaker client
    
    Returns:
    bool: True if successful, False otherwise
    """
    if twinmaker_client is None:
        twinmaker_client = boto3.client('iottwinmaker')
    
    try:
        print(f"\nAttempting to delete entity {entity_id} from workspace {workspace_id}...")
        twinmaker_client.delete_entity(
            workspaceId=workspace_id,
            entityId=entity_id
        )
        print(f"Successfully deleted entity {entity_id}")
        
        # Wait a bit for the deletion to propagate
        print("Waiting for deletion to propagate...")
        time.sleep(5)
        return True
    except ClientError as e:
        print(f"Error deleting entity: {e}")
        return False

def delete_component_type(workspace_id, component_type_id, twinmaker_client=None):
    """
    Delete a component type to allow for clean recreation
    
    Parameters:
    workspace_id (str): The ID of the workspace
    component_type_id (str): The ID of the component type to delete
    twinmaker_client: Optional boto3 twinmaker client
    
    Returns:
    bool: True if successful, False otherwise
    """
    if twinmaker_client is None:
        twinmaker_client = boto3.client('iottwinmaker')
    
    try:
        print(f"\nAttempting to delete component type {component_type_id} from workspace {workspace_id}...")
        twinmaker_client.delete_component_type(
            workspaceId=workspace_id,
            componentTypeId=component_type_id
        )
        print(f"Successfully deleted component type {component_type_id}")
        
        # Wait a bit for the deletion to propagate
        print("Waiting for deletion to propagate...")
        time.sleep(5)
        return True
    except ClientError as e:
        print(f"Error deleting component type: {e}")
        return False

def create_twinmaker_entities(workspace_id=None, config_loader=None, sitewise_asset_id=None, sitewise_model_id=None, force_recreate=False):
    """
    Creates a single motor-scripted-1 AWS IoT TwinMaker entity with IoT SiteWise connector
    
    Parameters:
    workspace_id (str): The ID of an existing TwinMaker workspace (default: SimpleFactoryTwin)
    config_loader (ConfigLoader): Configuration loader instance
    sitewise_asset_id (str): The ID of the SiteWise asset to connect (optional)
    sitewise_model_id (str): The ID of the SiteWise model to connect (optional)
    force_recreate (bool): Whether to delete and recreate the entity if it exists
    
    Returns:
    dict: Dictionary containing created entity ID
    """
    # Initialize configuration if not provided
    if config_loader is None:
        config_loader = ConfigLoader()
    
    # Initialize the AWS IoT TwinMaker client
    twinmaker = boto3.client('iottwinmaker')
    
    # Use default workspace_id if none provided
    if not workspace_id:
        workspace_config = config_loader.get_twinmaker_workspace_config()
        workspace_id = os.environ.get('WORKSPACE_ID', workspace_config.get('id', 'SimpleFactoryTwin'))
    
    print(f"Creating TwinMaker entity in workspace: {workspace_id}")
    
    # First verify that the workspace exists
    try:
        workspace = twinmaker.get_workspace(workspaceId=workspace_id)
        print(f"Found workspace: {workspace['workspaceId']}")
    except ClientError as e:
        print(f"Error: Workspace '{workspace_id}' not found. Please create it first using run.sh.")
        return None
    
    created_entities = {}
    
    # Step 1: Create motor component type from configuration
    try:
        components_config = config_loader.get_component_types_config()
        
        # Create Motor component type
        print("\nCreating Motor component type...")
        motor_config = components_config.get('motor', {})
        motor_properties = {}
        
        # Convert configuration format to API format
        for prop_name, prop_def in motor_config.get('properties', {}).items():
            if isinstance(prop_def.get('dataType'), str):
                data_type = {"type": prop_def.get('dataType')}
            else:
                data_type = prop_def.get('dataType', {})
                if isinstance(data_type, dict) and not "type" in data_type:
                    data_type = {"type": "STRING"}  # Default type
            
            if prop_def.get('unitOfMeasure'):
                data_type["unitOfMeasure"] = prop_def.get('unitOfMeasure')
                
            prop_config = {
                "dataType": data_type
            }
            
            if prop_def.get('isTimeSeries'):
                prop_config["isTimeSeries"] = prop_def.get('isTimeSeries')
                
            if prop_def.get('isStoredExternally'):
                prop_config["isStoredExternally"] = prop_def.get('isStoredExternally')
                
            if prop_def.get('isRequiredInEntity'):
                prop_config["isRequiredInEntity"] = prop_def.get('isRequiredInEntity')
                
            # Handle relationship type if present
            if prop_def.get('dataType') == "RELATIONSHIP" and prop_def.get('relationship'):
                prop_config["dataType"]["relationship"] = prop_def.get('relationship')
            elif isinstance(prop_def.get('dataType'), dict) and prop_def.get('dataType').get('type') == "RELATIONSHIP":
                prop_config["dataType"]["relationship"] = prop_def.get('relationship')
            
            motor_properties[prop_name] = prop_config
        
        # Create component type with optional extendsFrom parameter
        component_type_params = {
            "workspaceId": workspace_id,
            "componentTypeId": motor_config.get('id', 'MotorComponentType'),
            "description": motor_config.get('description', 'Industrial motor component'),
            "propertyDefinitions": motor_properties
        }
        
        # Add extendsFrom if specified in the configuration
        if 'extendsFrom' in motor_config:
            component_type_params["extendsFrom"] = motor_config.get('extendsFrom')
            print(f"Component type extends from: {motor_config.get('extendsFrom')}")
        
        try:
            motor_component_type = twinmaker.create_component_type(**component_type_params)
            # Fix: Use the componentTypeId from the input parameters since it's not in the response
            component_type_id = component_type_params["componentTypeId"]
            print(f"Created Motor component type: {component_type_id}")
        except ClientError as e:
            if "ConflictException" in str(e):
                print(f"Component type {component_type_params['componentTypeId']} already exists. Continuing...")
                component_type_id = component_type_params["componentTypeId"]
            else:
                raise
        
        # Wait a bit for component type to be fully registered
        print("Waiting for component type to be fully registered...")
        time.sleep(5)
        
    except ClientError as e:
        print(f"Error creating component type: {e}")
        # If it's a conflict error, we can continue since component type might already exist
        if "ConflictException" not in str(e):
            return None

    # Step 2: Create motor-scripted-1 entity from configuration
    try:
        entities_config = config_loader.get_entities_config()
        
        # Create Motor entity
        print("\nCreating motor-scripted-1 entity...")
        motor_config = entities_config.get('motor', {})
        entity_id = motor_config.get('entityId', 'motor-scripted-1')
        
        # Check if entity exists and delete if force_recreate is True
        try:
            existing_entity = twinmaker.get_entity(workspaceId=workspace_id, entityId=entity_id)
            if force_recreate:
                print(f"Entity {entity_id} exists and force_recreate is True.")
                if not delete_entity(workspace_id, entity_id, twinmaker):
                    print("Failed to delete existing entity. Aborting creation.")
                    return None
            else:
                print(f"Entity {entity_id} already exists.")
                print(f"Use --force-recreate to delete and recreate the entity.")
                # Check entity status 
                check_entity_status(workspace_id, entity_id, twinmaker)
                return {"motor": entity_id}
        except ClientError as e:
            if "ResourceNotFoundException" not in str(e):
                print(f"Unexpected error checking if entity exists: {e}")
        
        # Format the properties according to TwinMaker API requirements
        components = format_entity_components(motor_config.get('components', {}), sitewise_asset_id, sitewise_model_id)
        
        try:
            motor_entity = twinmaker.create_entity(
                workspaceId=workspace_id,
                entityName=motor_config.get('entityName', 'motor-scripted-1'),
                entityId=entity_id,
                description=motor_config.get('description', 'Motor entity synchronized with SiteWise asset'),
                components=components
            )
            created_entities["motor"] = motor_entity['entityId']
            print(f"Created Motor entity: {motor_entity['entityId']}")
            
            # Check entity status after creation
            check_entity_status(workspace_id, motor_entity['entityId'], twinmaker)
            
        except ClientError as e:
            if "ConflictException" in str(e):
                print(f"Entity {motor_config.get('entityId')} already exists.")
                print(f"Attempting to update the existing entity instead...")
                
                # Update the entity instead
                updated_entity = twinmaker.update_entity(
                    workspaceId=workspace_id,
                    entityId=motor_config.get('entityId', 'motor-scripted-1'),
                    description=motor_config.get('description', 'Motor entity synchronized with SiteWise asset'),
                    componentUpdates=components_to_updates(components)
                )
                created_entities["motor"] = motor_config.get('entityId', 'motor-scripted-1')
                print(f"Updated Motor entity: {motor_config.get('entityId')}")
                
                # Check entity status after update
                check_entity_status(workspace_id, motor_config.get('entityId', 'motor-scripted-1'), twinmaker)
            else:
                raise

        print("\nEntity created/updated successfully!")
        return created_entities
    
    except ClientError as e:
        print(f"Error creating/updating entity: {e}")
        return None

def check_entity_status(workspace_id, entity_id, twinmaker_client=None):
    """Check the status of an entity including any errors in its components"""
    if twinmaker_client is None:
        twinmaker_client = boto3.client('iottwinmaker')
    
    try:
        # Get entity details
        entity = twinmaker_client.get_entity(workspaceId=workspace_id, entityId=entity_id)
        
        print("\nEntity Status Check:")
        print(f"Entity {entity_id} exists in workspace {workspace_id}")
        
        # Check component status
        if 'components' in entity:
            print("\nComponent Status:")
            for comp_name, comp in entity['components'].items():
                print(f"  - {comp_name} (Type: {comp.get('componentTypeId', 'Unknown')})")
                
                # Check for errors in component properties
                if 'properties' in comp:
                    for prop_name, prop in comp['properties'].items():
                        prop_value_str = "No value"
                        error_str = ""
                        
                        # Check if there's a value for this property
                        if 'value' in prop:
                            value = prop['value']
                            if 'doubleValue' in value:
                                prop_value_str = f"Value: {value['doubleValue']}"
                            elif 'stringValue' in value:
                                prop_value_str = f"Value: '{value['stringValue']}'"
                            elif 'integerValue' in value:
                                prop_value_str = f"Value: {value['integerValue']}"
                            elif 'booleanValue' in value:
                                prop_value_str = f"Value: {value['booleanValue']}"
                            else:
                                prop_value_str = "Complex value"
                        
                        # Check if there's an error for this property
                        if 'error' in prop:
                            error_str = f"ERROR: {prop['error'].get('message', 'Unknown error')}"
                        
                        status = "OK" if not error_str else "ERROR"
                        print(f"    - {prop_name}: {status} - {prop_value_str} {error_str}")
        
        return True
    except ClientError as e:
        print(f"Error checking entity status: {e}")
        return False

def components_to_updates(components):
    """Convert components dictionary to componentUpdates format for update_entity API"""
    updates = {}
    
    for component_name, component in components.items():
        update = {
            "updateType": "UPDATE",
            "componentTypeId": component.get("componentTypeId")
        }
        
        # Add componentName if it exists
        if "componentName" in component:
            update["componentName"] = component["componentName"]
            
        # Add properties if they exist
        if "properties" in component:
            update["propertyUpdates"] = {}
            for prop_name, prop in component["properties"].items():
                update["propertyUpdates"][prop_name] = {
                    "updateType": "UPDATE",
                    "value": prop.get("value")
                }
        
        updates[component_name] = update
        
    return updates

def format_entity_components(components_config, sitewise_asset_id=None, sitewise_model_id=None):
    """
    Format component configuration for entity creation
    Transforms from the config format to the API format expected by TwinMaker
    
    Allows substitution of sitewise asset and model IDs if provided
    """
    formatted_components = {}
    
    for component_name, component_def in components_config.items():
        component = {}
        
        # Copy basic component properties
        component['componentTypeId'] = component_def.get('componentTypeId')
        if 'componentName' in component_def:
            component['componentName'] = component_def.get('componentName')
        
        # Format property values
        if 'properties' in component_def:
            properties = {}
            for prop_name, prop_value in component_def.get('properties', {}).items():
                # For each property, create a 'value' wrapper
                if isinstance(prop_value, dict):
                    # Handle placeholder substitution for SiteWise values
                    if prop_name == 'sitewiseAssetId' and sitewise_asset_id:
                        if 'stringValue' in prop_value:
                            if prop_value['stringValue'] == '${asset_id}':
                                prop_value['stringValue'] = sitewise_asset_id
                                print(f"Using SiteWise asset ID: {sitewise_asset_id}")
                    
                    if prop_name == 'sitewiseAssetModelId' and sitewise_model_id:
                        if 'stringValue' in prop_value:
                            if prop_value['stringValue'] == '${model_id}':
                                prop_value['stringValue'] = sitewise_model_id
                                print(f"Using SiteWise model ID: {sitewise_model_id}")
                    
                    if any(key in prop_value for key in ['doubleValue', 'stringValue', 'integerValue', 'booleanValue', 'relationshipValue']):
                        properties[prop_name] = {
                            'value': prop_value
                        }
                    else:
                        properties[prop_name] = {
                            'value': prop_value
                        }
            
            component['properties'] = properties
        
        formatted_components[component_name] = component
    
    return formatted_components

def list_workspace_entities(workspace_id=None, config_loader=None):
    """List all entities in the specified TwinMaker workspace"""
    if config_loader is None:
        config_loader = ConfigLoader()
    
    if not workspace_id:
        workspace_config = config_loader.get_twinmaker_workspace_config()
        workspace_id = os.environ.get('WORKSPACE_ID', workspace_config.get('id', 'SimpleFactoryTwin'))
    
    twinmaker = boto3.client('iottwinmaker')
    try:
        print(f"\nListing entities in workspace '{workspace_id}':")
        response = twinmaker.list_entities(workspaceId=workspace_id)
        
        if not response.get('entitySummaries'):
            print("No entities found in the workspace.")
            return
        
        print("\n{:<20} {:<30} {:<40}".format("ENTITY ID", "ENTITY NAME", "DESCRIPTION"))
        print("-" * 90)
        
        for entity in response.get('entitySummaries', []):
            print("{:<20} {:<30} {:<40}".format(
                entity.get('entityId', 'N/A')[:18], 
                entity.get('entityName', 'N/A')[:28], 
                entity.get('description', 'N/A')[:38]
            ))
            
            # Get detailed entity information for status check
            try:
                check_entity_status(workspace_id, entity.get('entityId'), twinmaker)
            except Exception as e:
                print(f"  Error checking entity status: {e}")
            
        print("\nTo view details of a specific entity, use the AWS IoT TwinMaker console.")
            
    except ClientError as e:
        print(f"Error listing entities: {e}")

def get_sitewise_asset_info():
    """Get IoT SiteWise asset and model IDs for integration"""
    try:
        sitewise = boto3.client('iotsitewise')
        
        print("Fetching IoT SiteWise models first...")
        models_response = sitewise.list_asset_models(maxResults=10)
        
        if not models_response.get('assetModelSummaries'):
            print("No asset models found in IoT SiteWise")
            return None, None
            
        print("\nAvailable IoT SiteWise models:")
        print("{:<5} {:<40} {:<40}".format("NUM", "MODEL NAME", "MODEL ID"))
        print("-" * 85)
        
        model_choices = {}
        for i, model in enumerate(models_response.get('assetModelSummaries', []), 1):
            model_name = model.get('name', 'Unnamed')
            model_id = model.get('id', 'Unknown')
            print(f"{i:<5} {model_name:<40} {model_id}")
            model_choices[i] = {
                'name': model_name,
                'id': model_id
            }
            
        if not model_choices:
            print("No IoT SiteWise models available")
            return None, None
            
        # Let the user choose which model to use
        print("\nWhich SiteWise model do you want to use?")
        model_choice = input("Enter the number (or press Enter to skip): ")
        
        if not model_choice.strip():
            print("Skipping SiteWise integration")
            return None, None
            
        try:
            model_num = int(model_choice)
            if model_num not in model_choices:
                print("Invalid choice. Skipping SiteWise integration")
                return None, None
                
            selected_model = model_choices[model_num]
            model_id = selected_model['id']
            print(f"\nSelected model: {selected_model['name']} ({model_id})")
            
            # Now list assets for this model
            print(f"Fetching assets for model {selected_model['name']}...")
            assets_response = sitewise.list_assets(maxResults=10, assetModelId=model_id)
            
            if not assets_response.get('assetSummaries'):
                print(f"No assets found for model {selected_model['name']}")
                # Return just the model ID, no asset ID
                return None, model_id
                
            print("\nAvailable assets for this model:")
            print("{:<5} {:<40} {:<40}".format("NUM", "ASSET NAME", "ASSET ID"))
            print("-" * 85)
            
            asset_choices = {}
            for i, asset in enumerate(assets_response.get('assetSummaries', []), 1):
                asset_name = asset.get('name', 'Unnamed')
                asset_id = asset.get('id', 'Unknown')
                print(f"{i:<5} {asset_name:<40} {asset_id}")
                asset_choices[i] = {
                    'name': asset_name,
                    'id': asset_id
                }
                
            if not asset_choices:
                print("No assets available for this model")
                # Return just the model ID, no asset ID
                return None, model_id
                
            # Let the user choose which asset to connect
            print("\nWhich asset do you want to connect to the TwinMaker entity?")
            asset_choice = input("Enter the number (or press Enter to skip asset connection): ")
            
            if not asset_choice.strip():
                print("Skipping asset connection, using only model ID")
                return None, model_id
                
            try:
                asset_num = int(asset_choice)
                if asset_num not in asset_choices:
                    print("Invalid choice. Using only model ID")
                    return None, model_id
                    
                selected_asset = asset_choices[asset_num]
                print(f"\nSelected asset: {selected_asset['name']} ({selected_asset['id']})")
                return selected_asset['id'], model_id
                
            except ValueError:
                print("Invalid input. Using only model ID")
                return None, model_id
                
        except ValueError:
            print("Invalid input. Skipping SiteWise integration")
            return None, None
            
    except Exception as e:
        print(f"Error fetching SiteWise information: {e}")
        return None, None

if __name__ == "__main__":
    print("AWS IoT TwinMaker Entity Creator")
    print("================================")
    
    # Initialize configuration
    config_loader = ConfigLoader()
    initialize_env_from_config(config_loader)
    
    # Process command line arguments
    force_recreate = False
    force_recreate_component_type = False
    workspace_id = None
    args = sys.argv[1:]
    
    # Process args
    for i, arg in enumerate(args):
        if arg == "--force-recreate" or arg == "-f":
            force_recreate = True
        elif arg == "--force-recreate-component" or arg == "-fc":
            force_recreate_component_type = True
        elif workspace_id is None and not arg.startswith("-"):
            workspace_id = arg
    
    if force_recreate:
        print("Force recreate mode: Will delete and recreate entity if it exists.")
        
    if force_recreate_component_type:
        print("Force recreate component type: Will delete and recreate component type if it exists.")
    
    # Get workspace ID from args or environment or use default if not specified above
    if not workspace_id:
        workspace_config = config_loader.get_twinmaker_workspace_config()
        workspace_id = os.environ.get('WORKSPACE_ID', workspace_config.get('id'))
    print(f"Using workspace ID: {workspace_id}")
    
    # Get IoT SiteWise asset and model IDs for integration
    sitewise_asset_id, sitewise_model_id = get_sitewise_asset_info()
    
    # If we're forcing component type recreation, do it now
    if force_recreate_component_type:
        # Initialize TwinMaker client
        twinmaker = boto3.client('iottwinmaker')
        component_type_id = config_loader.get_component_types_config().get('motor', {}).get('id', 'MotorComponentType')
        
        # Check if entity exists first - need to delete it before deleting component type
        entity_id = config_loader.get_entities_config().get('motor', {}).get('entityId', 'motor-scripted-1')
        try:
            # Try to get entity
            twinmaker.get_entity(workspaceId=workspace_id, entityId=entity_id)
            # If we got here, entity exists - delete it
            delete_entity(workspace_id, entity_id, twinmaker)
        except ClientError as e:
            # Entity doesn't exist, can proceed
            if "ResourceNotFoundException" not in str(e):
                print(f"Unexpected error checking if entity exists: {e}")
        
        # Now try to delete component type
        delete_component_type(workspace_id, component_type_id, twinmaker)
    
    # Create entity and components
    created = create_twinmaker_entities(
        workspace_id, 
        config_loader,
        sitewise_asset_id,
        sitewise_model_id,
        force_recreate
    )
    
    if created:
        print("\nEntity created/updated successfully:")
        for entity_type, entity_id in created.items():
            print(f"- {entity_type}: {entity_id}")
        
        # List all entities in the workspace
        list_workspace_entities(workspace_id, config_loader)
    else:
        print("\nFailed to create/update entity.")
        sys.exit(1)