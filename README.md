# AWS IoT TwinMaker & SiteWise Integration

This repository provides scripts and a web interface to set up and configure an AWS IoT TwinMaker workspace with IoT SiteWise assets for industrial digital twin applications.

## Overview

This project enables the creation of digital twins for industrial systems using AWS IoT TwinMaker and AWS IoT SiteWise. The pipeline includes:

1. **TwinMaker Workspace Creation**: Set up a TwinMaker workspace with necessary IAM roles and S3 storage
2. **IoT SiteWise Model Creation**: Define asset models with properties, measurements, and attributes
3. **IoT SiteWise Asset Creation**: Instantiate assets from models and configure MQTT notifications
4. **TwinMaker Entity Creation**: Create component types and entities linked to SiteWise assets
5. **Integration Flow**: Connect TwinMaker with SiteWise assets for comprehensive digital twin capabilities
6. **FastAPI Web Interface**: Manage and monitor your digital twin infrastructure through a modern web UI

## Prerequisites

- AWS Account with appropriate permissions
- Python 3.6+
- AWS CLI configured locally (or use environment variables)
- `boto3` Python SDK

## Project Structure

```
Honeywell-inventor/
├── configs/                     # Modular configuration files
│   ├── workspace.config.json    # TwinMaker workspace and AWS credentials
│   ├── models.config.json       # SiteWise model definitions
│   ├── entities.config.json     # TwinMaker entity definitions
│   └── components.config.json   # TwinMaker component type definitions
├── master-setup.sh              # Master script to orchestrate the entire flow
├── run.sh                       # Script to create TwinMaker workspace
├── twin-maker-script.py         # Python implementation for TwinMaker workspace
├── run-sitewise-model.sh        # Script to create IoT SiteWise model
├── create-iotsitewise-model.py  # Python implementation for SiteWise model creation
├── run-sitewise-asset.sh        # Script to create IoT SiteWise asset
├── create-iotsitewise-asset.py  # Python implementation for SiteWise asset creation
├── run-twinmaker-entities.sh    # Script to create TwinMaker entities
├── create-twinmaker-entities.py # Python implementation for TwinMaker entities
├── config_loader.py             # Modular configuration management system
├── set_aliases.py               # Configure SiteWise asset property aliases
├── app.py                       # FastAPI web application (if present)
├── requirements.txt             # Python dependencies
└── .env                         # Environment variables (create this file)
```

## Installation

1. Clone this repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your AWS credentials:
   ```bash
   AWS_ACCESS_KEY_ID=your_access_key_here
   AWS_SECRET_ACCESS_KEY=your_secret_key_here
   AWS_REGION=us-east-1
   ```

## Configuration

The project uses a modular configuration system with JSON files in the `configs/` directory:

- **workspace.config.json**: AWS credentials, TwinMaker workspace settings, and IAM roles
- **models.config.json**: SiteWise asset model definitions with properties and measurements
- **entities.config.json**: TwinMaker entity definitions and component mappings
- **components.config.json**: TwinMaker component type definitions

## Usage

### Option 1: Using the Master Script (Recommended)

The master script provides automated end-to-end deployment:

```bash
./master-setup.sh
```

This will automatically:
1. Create TwinMaker workspace with proper IAM roles
2. Create all SiteWise models defined in configuration
3. Create SiteWise assets for each model type
4. Set up property aliases and MQTT notifications
5. Create TwinMaker entities linked to SiteWise assets
6. Generate data sender scripts for testing

### Option 2: FastAPI Web Interface

If you have the FastAPI web application, start the web server:

```bash
python app.py
```

Then access the web interface at `http://localhost:8000` to:
- Monitor deployment status
- View real-time metrics
- Manage digital twin components
- Access operational dashboards

### Option 3: Running Individual Scripts

#### TwinMaker Workspace Setup

```bash
./run.sh --workspace-id CookieFactoryTwin
```

This creates:
- AWS IoT TwinMaker workspace with configured ID
- Required IAM roles with appropriate permissions
- S3 bucket for storing workspace data

#### IoT SiteWise Model Creation

```bash
./run-sitewise-model.sh
```

This creates models based on your configuration with:
- Defined properties, measurements, and attributes
- Proper data types and units
- Hierarchical model relationships

#### IoT SiteWise Asset Creation

```bash
./run-sitewise-asset.sh <model-id> <model-type>
```

This creates:
- Asset based on the specified model
- Enables MQTT notifications for all properties
- Configures property aliases for easy data access

#### TwinMaker Entity Creation

```bash
./run-twinmaker-entities.sh <workspace-id>
```

This creates:
- Component types linked to SiteWise models
- Entities synchronized with SiteWise assets
- Property mappings for real-time data flow

## Workflow Details

### Complete Setup Flow

1. **Environment Setup**: Create virtual environment and install dependencies
2. **Configuration Loading**: Parse modular configuration files
3. **AWS Credential Validation**: Verify and configure AWS access
4. **TwinMaker Workspace**: Create workspace with IAM roles and S3 storage
5. **SiteWise Models**: Create asset models based on configuration
6. **SiteWise Assets**: Instantiate assets from models with notifications
7. **Property Aliases**: Configure MQTT-friendly property paths
8. **TwinMaker Entities**: Create digital twin entities linked to physical assets
9. **Data Generators**: Set up scripts for testing and simulation

### Configuration Management

The `ConfigLoader` class provides:
- Environment variable substitution
- Modular configuration file loading
- Fallback to monolithic config.json
- Validation and error handling
- Dynamic configuration updates

## Integration with AWS IoT TwinMaker

After deployment:

1. **TwinMaker Console**: Navigate to your workspace to view entities and scenes
2. **SiteWise Integration**: Entities are automatically linked to SiteWise assets
3. **Real-time Data**: Property values flow from SiteWise to TwinMaker
4. **3D Visualization**: Create scenes to visualize your digital twin
5. **Monitoring Dashboards**: Use the web interface for operational insights

## Security Notes

- Store AWS credentials in `.env` file (never commit to git)
- Use IAM roles with least privilege principles
- Environment variables are substituted in configuration files
- The project supports both credential files and environment variables
- In production, use AWS IAM roles or AWS Secrets Manager

## Troubleshooting

### Common Issues

1. **AWS Credential Errors**:
   - Verify credentials in `.env` file are valid
   - Check AWS CLI configuration with `aws configure`
   - Ensure proper IAM permissions for TwinMaker and SiteWise

2. **Virtual Environment Issues**:
   - Ensure Python 3.6+ is installed
   - Install `python3-venv` if missing (`sudo apt-get install python3-venv`)

3. **Configuration Errors**:
   - Validate JSON syntax in config files
   - Check environment variable substitution
   - Verify model and entity definitions

4. **SiteWise Model/Asset Creation Failures**:
   - Check for proper IAM permissions
   - Verify region compatibility for SiteWise
   - Ensure model IDs are correctly formatted

### Specific Error Solutions

- **"Externally managed environment" Error**: Scripts use isolated virtual environments
- **Asset Creation Fails**: Verify model ID format and model ACTIVE state
- **TwinMaker Workspace Creation Fails**: Check IAM permissions and S3 bucket access
- **Entity Creation Fails**: Ensure SiteWise assets exist and are properly configured

## Data Generation and Testing

After setup, use the generated scripts to send test data:

```bash
# Example for different model types
./send-motor-data.sh
./send-sensor-data.sh
./send-conveyor-data.sh
```

## Monitoring and Metrics

The system provides:
- Real-time asset property monitoring
- MQTT notification tracking
- Entity status validation
- Configuration drift detection
- Performance metrics via web interface

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

This project is licensed under the MIT License - see the LICENSE file for details.