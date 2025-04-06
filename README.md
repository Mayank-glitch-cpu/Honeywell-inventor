# AWS IoT TwinMaker & SiteWise Integration

This repository provides scripts to set up and configure an AWS IoT TwinMaker workspace with IoT SiteWise assets for industrial digital twin applications.

## Overview

This project enables the creation of digital twins for industrial systems using AWS IoT TwinMaker and AWS IoT SiteWise. The pipeline includes:

1. **TwinMaker Workspace Creation**: Set up a TwinMaker workspace with necessary IAM roles and S3 storage
2. **IoT SiteWise Model Creation**: Define asset models with properties, measurements, and attributes
3. **IoT SiteWise Asset Creation**: Instantiate assets from models and configure MQTT notifications
4. **Integration Flow**: Connect TwinMaker with SiteWise assets for comprehensive digital twin capabilities

## Prerequisites

- AWS Account with appropriate permissions
- Python 3.6+
- AWS CLI configured locally (or use the provided credentials)
- `boto3` Python SDK

## Project Structure

```
Honeywell-inventor/
├── master-setup.sh              # Master script to orchestrate the entire flow
├── run.sh                       # Script to create TwinMaker workspace
├── twin-maker-script.py         # Python implementation for TwinMaker workspace
├── run-twinmaker-cdk.py         # CDK implementation for TwinMaker (alternative)
├── run-cdk.sh                   # Script to run CDK deployment
├── run-sitewise-model.sh        # Script to create IoT SiteWise model
├── create-iotsitewise-model.py  # Python implementation for SiteWise model creation
├── run-sitewise-asset.sh        # Script to create IoT SiteWise asset
├── create-iotsitewise-asset.py  # Python implementation for SiteWise asset creation
├── requirements.txt             # Python dependencies
└── rootkey.csv                  # AWS credentials (included for convenience)
```

## Installation

1. Clone this repository
2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Option 1: Using the Master Script (Recommended)

The master script provides a unified interface for all functionality:

```bash
./master-setup.sh
```

The script will present options to:
1. Create TwinMaker workspace
2. Create IoT SiteWise model
3. Create IoT SiteWise asset
4. Run the full setup process end-to-end

### Option 2: Running Individual Scripts

#### TwinMaker Workspace Setup

```bash
./run.sh
```

This creates:
- AWS IoT TwinMaker workspace named "SimpleFactoryTwin"
- Required IAM roles with appropriate permissions
- S3 bucket for storing workspace data

#### IoT SiteWise Model Creation

```bash
./run-sitewise-model.sh
```

This creates a model named "Motor-scripted" with:
- String attribute: "Serial" (with default value)
- Double measurement: "Speed" (with unit RPM)

#### IoT SiteWise Asset Creation

```bash
./run-sitewise-asset.sh <model-id>
```

This creates:
- Asset based on the specified model
- Enables MQTT notifications for all properties
- Sets a unique serial number for the asset

## Workflow Details

### TwinMaker Setup Flow

1. Create or validate virtual environment
2. Install required dependencies
3. Configure AWS credentials
4. Create/validate S3 bucket for asset storage
5. Create/validate IAM role for TwinMaker
6. Create TwinMaker workspace
7. (Optional) Configure component types and entities

### SiteWise Model Creation Flow

1. Create virtual environment with required dependencies
2. Configure AWS credentials and region
3. Create SiteWise asset model with defined properties
4. Wait for the model to become active
5. Return the model ID for asset creation

### SiteWise Asset Creation Flow

1. Use existing virtual environment
2. Verify model exists and is active
3. Create asset based on the model
4. Wait for asset to become active
5. Enable MQTT notifications for all properties
6. Update asset property values (e.g., unique serial number)

## Integration with AWS IoT TwinMaker

After creating both the TwinMaker workspace and SiteWise assets:

1. In the TwinMaker console, navigate to the workspace
2. Create a connection to SiteWise in the workspace settings
3. Import the SiteWise model and assets as component types and entities
4. Create scenes to visualize the digital twin

## Security Notes

- The repository includes AWS credentials for demonstration purposes
- In production, use more secure methods (IAM roles, environment variables, AWS Secrets Manager)
- Remove hardcoded credentials and use AWS best practices for credential management

## Troubleshooting

### Common Issues

1. **AWS Credential Errors**:
   - Confirm credentials in `.env` or `rootkey.csv` are valid
   - Verify AWS CLI configuration with `aws configure`

2. **Virtual Environment Issues**:
   - Ensure Python 3.6+ is installed
   - Install `python3-venv` if missing (`sudo apt-get install python3-venv`)

3. **SiteWise Model/Asset Creation Failures**:
   - Check for proper IAM permissions
   - Verify region compatibility for SiteWise
   - Check the status of created resources in AWS console

### Specific Error Solutions

- **"Externally managed environment" Error**: Scripts now handle this correctly using virtual environments
- **Asset Creation Fails**: Ensure the model ID is correct and the model is in ACTIVE state
- **TwinMaker Workspace Creation Fails**: Check IAM permissions and S3 bucket access

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

This project is licensed under the MIT License - see the LICENSE file for details.