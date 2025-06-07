#!/usr/bin/env python3
import json
import os
import sys
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv


class ConfigLoader:
    """
    Utility class to load and parse configuration from modular config files
    Provides easy access to configuration parameters for TwinMaker and SiteWise scripts
    """
    def __init__(self, config_dir: str = 'configs'):
        """Initialize the ConfigLoader with a path to the config directory"""
        # Load environment variables from .env file
        load_dotenv()
        
        self.config_dir = config_dir
        self.config_file = 'config.json'
        self.config = self._load_config()
        
    def _substitute_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute environment variables in config values"""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            env_var = config[2:-1]
            return os.getenv(env_var, config)
        return config
    
    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from the modular JSON files or fallback to config.json"""
        config = {}
        
        # Try to load modular config files first
        if os.path.exists(self.config_dir):
            # Load workspace config
            workspace_config = self._load_file(os.path.join(self.config_dir, 'workspace.config.json'))
            if workspace_config:
                config['workspace'] = workspace_config
                
                # Add environment config if present
                if 'environment' in workspace_config:
                    config['environment'] = workspace_config['environment']
                
                # Add AWS credentials if present
                if 'aws' in workspace_config:
                    config['aws'] = workspace_config['aws']
            
            # Load models config
            models_config = self._load_file(os.path.join(self.config_dir, 'models.config.json'))
            if models_config:
                config['sitewise'] = {
                    'models': models_config.get('models', {}),
                    'assets': models_config.get('assets', {})
                }
            
            # Load entities config
            entities_config = self._load_file(os.path.join(self.config_dir, 'entities.config.json'))
            if entities_config:
                config['entities'] = entities_config
            
            # Load components config
            components_config = self._load_file(os.path.join(self.config_dir, 'components.config.json'))
            if components_config:
                config['components'] = components_config
            
            if config:
                # Don't print to stdout as it will be captured by shell scripts
                # Instead write to stderr if you want to see a message
                sys.stderr.write(f"Successfully loaded configuration from {self.config_dir}\n")
                return config
        
        # Fallback to monolithic config.json if modular configs don't exist
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            sys.stderr.write(f"Successfully loaded configuration from {self.config_file}\n")
            return config
        except FileNotFoundError:
            sys.stderr.write(f"Error: No configuration files found in '{self.config_dir}' or '{self.config_file}'\n")
            return {}
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Error: Invalid JSON in configuration file: {e}\n")
            return {}
    
    def _load_file(self, file_path: str) -> Dict[str, Any]:
        """Load a specific configuration file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            sys.stderr.write(f"Warning: Could not load configuration file '{file_path}': {e}\n")
        return {}
    
    def get_aws_credentials(self) -> Dict[str, str]:
        """Get AWS credentials from config"""
        return self.config.get('aws', {}).get('credentials', {})
    
    def get_twinmaker_workspace_config(self) -> Dict[str, Any]:
        """Get TwinMaker workspace configuration"""
        return self.config.get('workspace', {}).get('twinmaker', {})
    
    def get_component_types_config(self) -> Dict[str, Any]:
        """Get TwinMaker component type definitions"""
        return self.config.get('components', {})
    
    def get_entities_config(self) -> Dict[str, Any]:
        """Get TwinMaker entity definitions"""
        return self.config.get('entities', {})
    
    def get_sitewise_model_config(self) -> Dict[str, Any]:
        """Get SiteWise model configuration"""
        return self.config.get('sitewise', {}).get('models', {})
    
    def get_sitewise_asset_config(self, model_type: str = None) -> Dict[str, Any]:
        """Get SiteWise asset configuration for a specific model type or all model types"""
        assets = self.config.get('sitewise', {}).get('assets', {})
        if model_type:
            return assets.get(model_type, {})
        return assets
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment configuration (paths, scripts, etc.)"""
        return self.config.get('environment', {})
    
    def update_config(self, new_config: Dict[str, Any], section: str = None) -> None:
        """Update the configuration and save it to file"""
        if section:
            if section not in self.config:
                self.config[section] = {}
            self.config[section].update(new_config)
        else:
            self.config.update(new_config)
        self.save_config(section)
    
    def save_config(self, section: str = None) -> None:
        """Save the current configuration to the appropriate JSON file"""
        try:
            # Create config directory if it doesn't exist
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)
            
            if section:
                # Save the specific section to its modular config file
                config_map = {
                    'workspace': 'workspace.config.json',
                    'entities': 'entities.config.json',
                    'components': 'components.config.json'
                }
                
                # Handle special cases
                if section == 'sitewise':
                    # Save sitewise config to models.config.json
                    file_path = os.path.join(self.config_dir, 'models.config.json')
                    data = {
                        'models': self.config.get('sitewise', {}).get('models', {}),
                        'assets': self.config.get('sitewise', {}).get('assets', {})
                    }
                elif section in config_map:
                    # Save other sections to their specific files
                    file_path = os.path.join(self.config_dir, config_map[section])
                    data = self.config.get(section, {})
                else:
                    # Fallback to saving the whole config
                    file_path = os.path.join(self.config_dir, 'config.json')
                    data = self.config
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                sys.stderr.write(f"Configuration saved to {file_path}\n")
            else:
                # Save the whole config to the monolithic config.json
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                sys.stderr.write(f"Configuration saved to {self.config_file}\n")
        except IOError as e:
            sys.stderr.write(f"Error saving configuration: {e}\n")
    
    def format_with_variables(self, template: str, **kwargs) -> str:
        """Format a string template with provided variables"""
        return template.format(**kwargs)
    
    def resolve_s3_bucket_resources(self, bucket_name: str) -> Dict[str, Any]:
        """Resolve S3 bucket resources and URLs"""
        region = os.environ.get('AWS_REGION', 'us-east-1')
        return {
            'bucket': bucket_name,
            'region': region,
            'url': f"s3://{bucket_name}",
            'console_url': f"https://s3.console.aws.amazon.com/s3/buckets/{bucket_name}?region={region}"
        }
    
    def save_modular_configs(self) -> None:
        """
        Split the monolithic config.json into modular config files
        This is useful for migrating from the old format to the new modular format
        """
        if not os.path.exists(self.config_file):
            sys.stderr.write(f"Error: {self.config_file} not found. Cannot split into modular configs.\n")
            return
        
        # Create config directory if it doesn't exist
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        # Load monolithic config
        with open(self.config_file, 'r') as f:
            config = json.load(f)
        
        # Create workspace config
        workspace_config = {
            'twinmaker': config.get('twinmaker', {}),
            'environment': config.get('environment', {}),
            'aws': config.get('aws', {})
        }
        with open(os.path.join(self.config_dir, 'workspace.config.json'), 'w') as f:
            json.dump(workspace_config, f, indent=2)
        
        # Create models config
        models_config = {
            'models': config.get('sitewise', {}).get('models', {}),
            'assets': config.get('sitewise', {}).get('assets', {})
        }
        with open(os.path.join(self.config_dir, 'models.config.json'), 'w') as f:
            json.dump(models_config, f, indent=2)
        
        # Create entities config
        entities_config = config.get('entities', {})
        with open(os.path.join(self.config_dir, 'entities.config.json'), 'w') as f:
            json.dump(entities_config, f, indent=2)
        
        # Create components config
        components_config = config.get('components', {})
        with open(os.path.join(self.config_dir, 'components.config.json'), 'w') as f:
            json.dump(components_config, f, indent=2)
        
        sys.stderr.write(f"Successfully split {self.config_file} into modular config files in {self.config_dir}\n")


def initialize_env_from_config(config_loader: Optional[ConfigLoader] = None) -> None:
    """Initialize environment variables from config"""
    if not config_loader:
        config_loader = ConfigLoader()
    
    # Load AWS credentials from config and set as environment variables
    aws_creds = config_loader.get_aws_credentials()
    if aws_creds:
        if 'access_key_id' in aws_creds:
            os.environ['AWS_ACCESS_KEY_ID'] = aws_creds['access_key_id']
        if 'secret_access_key' in aws_creds:
            os.environ['AWS_SECRET_ACCESS_KEY'] = aws_creds['secret_access_key']
        if 'region' in aws_creds:
            os.environ['AWS_REGION'] = aws_creds['region']
    
    # Load workspace config
    workspace_config = config_loader.get_twinmaker_workspace_config()
    
    # Set S3 bucket name if available
    if workspace_config.get('s3', {}).get('bucket_name'):
        os.environ['S3_BUCKET_NAME'] = workspace_config['s3']['bucket_name']


if __name__ == "__main__":
    # If run directly, create modular configs from the monolithic config.json
    if os.path.exists('config.json') and not os.path.exists(os.path.join('configs', 'workspace.config.json')):
        sys.stderr.write("Creating modular configuration files from config.json...\n")
        loader = ConfigLoader()
        loader.save_modular_configs()
    else:
        # Otherwise validate the configuration
        loader = ConfigLoader()
        if not loader.config:
            sys.stderr.write("Error: No valid configuration found.\n")
            sys.exit(1)
        
        sys.stderr.write("Configuration file is valid and loaded successfully\n")
        
        # Print configuration sections
        sys.stderr.write("\nConfiguration sections:\n")
        sys.stderr.write("- AWS Credentials present: {}\n".format(bool(loader.get_aws_credentials())))
        sys.stderr.write("- TwinMaker Workspace: {}\n".format(loader.get_twinmaker_workspace_config().get('id', 'Not found')))
        sys.stderr.write("- Component Types: {}\n".format(", ".join(loader.get_component_types_config().keys()) or "Not found"))
        sys.stderr.write("- Entity Definitions: {}\n".format(", ".join(loader.get_entities_config().keys()) or "Not found"))
        sys.stderr.write("- SiteWise Models: {}\n".format(", ".join(loader.get_sitewise_model_config().keys()) or "Not found"))
        sys.stderr.write("- SiteWise Assets: {}\n".format(", ".join(loader.get_sitewise_asset_config().keys()) or "Not found"))
        sys.stderr.write("- Environment config present: {}\n".format(bool(loader.get_environment_config())))