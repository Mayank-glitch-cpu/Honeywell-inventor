#!/usr/bin/env python3
import json
import os
import sys
from typing import Dict, Any, Optional


class ConfigLoader:
    """
    Utility class to load and parse configuration from config.json file
    Provides easy access to configuration parameters for TwinMaker and SiteWise scripts
    """
    def __init__(self, config_file: str = 'config.json'):
        """Initialize the ConfigLoader with a path to the config file"""
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from the JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            print(f"Successfully loaded configuration from {self.config_file}")
            return config
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.config_file}' not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in configuration file: {e}")
            sys.exit(1)
    
    def get_aws_credentials(self) -> Dict[str, str]:
        """Get AWS credentials from config"""
        return self.config.get('aws', {}).get('credentials', {})
    
    def get_twinmaker_workspace_config(self) -> Dict[str, Any]:
        """Get TwinMaker workspace configuration"""
        return self.config.get('twinmaker', {}).get('workspace', {})
    
    def get_component_types_config(self) -> Dict[str, Any]:
        """Get TwinMaker component type definitions"""
        return self.config.get('twinmaker', {}).get('components', {})
    
    def get_entities_config(self) -> Dict[str, Any]:
        """Get TwinMaker entity definitions"""
        return self.config.get('twinmaker', {}).get('entities', {})
    
    def get_sitewise_model_config(self) -> Dict[str, Any]:
        """Get SiteWise model configuration"""
        return self.config.get('sitewise', {}).get('model', {})
    
    def get_sitewise_asset_config(self) -> Dict[str, Any]:
        """Get SiteWise asset configuration"""
        return self.config.get('sitewise', {}).get('asset', {})
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment configuration (paths, scripts, etc.)"""
        return self.config.get('environment', {})
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update the configuration and save it to file"""
        self.config.update(new_config)
        self.save_config()
    
    def save_config(self) -> None:
        """Save the current configuration to the JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"Configuration saved to {self.config_file}")
        except IOError as e:
            print(f"Error saving configuration: {e}")
    
    def format_with_variables(self, template: str, **kwargs) -> str:
        """Format a string template with provided variables"""
        return template.format(**kwargs)
    
    def resolve_s3_bucket_resources(self, bucket_name: str) -> Dict[str, Any]:
        """
        Updates resource entries in IAM policies that reference {bucket_name}
        with the actual bucket name
        """
        role_config = self.config.get('twinmaker', {}).get('workspace', {}).get('role', {})
        
        for policy in role_config.get('access_policies', []):
            document = policy.get('document', {})
            for statement in document.get('Statement', []):
                resources = statement.get('Resource', [])
                for i, resource in enumerate(resources):
                    if '{bucket_name}' in resource:
                        resources[i] = resource.replace('{bucket_name}', bucket_name)
                        
        return role_config


def initialize_env_from_config(config_loader: Optional[ConfigLoader] = None) -> None:
    """
    Initialize environment variables from configuration
    This is useful for scripts that rely on environment variables
    """
    if config_loader is None:
        config_loader = ConfigLoader()
    
    # Get AWS credentials
    aws_creds = config_loader.get_aws_credentials()
    
    # Set environment variables
    os.environ['AWS_ACCESS_KEY_ID'] = aws_creds.get('access_key_id', '')
    os.environ['AWS_SECRET_ACCESS_KEY'] = aws_creds.get('secret_access_key', '')
    os.environ['AWS_REGION'] = aws_creds.get('region', 'us-east-1')
    os.environ['AWS_DEFAULT_REGION'] = aws_creds.get('region', 'us-east-1')
    
    # Set workspace ID for TwinMaker
    workspace_config = config_loader.get_twinmaker_workspace_config()
    os.environ['WORKSPACE_ID'] = workspace_config.get('id', 'SimpleFactoryTwin')
    
    # Set bucket name if provided
    if workspace_config.get('s3', {}).get('bucket_name'):
        os.environ['S3_BUCKET_NAME'] = workspace_config['s3']['bucket_name']


if __name__ == "__main__":
    # If run directly, validate the configuration file
    loader = ConfigLoader()
    print("Configuration file is valid and loaded successfully")
    
    # Print configuration sections
    print("\nConfiguration sections:")
    print("- AWS Credentials present:", bool(loader.get_aws_credentials()))
    print("- TwinMaker Workspace:", loader.get_twinmaker_workspace_config().get('id'))
    print("- Component Types:", ", ".join(loader.get_component_types_config().keys()))
    print("- Entity Definitions:", ", ".join(loader.get_entities_config().keys()))
    print("- SiteWise Model:", loader.get_sitewise_model_config().get('name'))
    print("- Environment config present:", bool(loader.get_environment_config()))