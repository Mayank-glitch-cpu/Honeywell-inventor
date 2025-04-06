#!/bin/bash

# Exit on error
set -e

echo "======================================================================"
echo "Setting up environment for AWS IoT TwinMaker CDK deployment"
echo "======================================================================"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "Error: npm is not installed. Please install Node.js and npm first."
    exit 1
fi

# Check if AWS CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "AWS CDK not found. Installing AWS CDK globally..."
    npm install -g aws-cdk
fi

# Set up virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements from requirements.txt
echo "Installing base requirements..."
pip install -r requirements.txt

# Install CDK related dependencies
echo "Installing AWS CDK Python dependencies..."
pip install aws-cdk-lib constructs

# Verify AWS credentials
echo "Verifying AWS credentials..."
if ! aws sts get-caller-identity &>/dev/null; then
    echo "Error: AWS credentials not properly configured!"
    echo "Please run 'aws configure' to set up your credentials."
    exit 1
fi

# Check if CDK is bootstrapped for the current account/region
echo "Checking if CDK is bootstrapped for your account/region..."
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $AWS_REGION &>/dev/null; then
    echo "CDK is not bootstrapped for account $AWS_ACCOUNT in region $AWS_REGION"
    echo "Bootstrapping CDK..."
    cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION
else
    echo "CDK is already bootstrapped for account $AWS_ACCOUNT in region $AWS_REGION"
fi

# Run the TwinMaker CDK script
echo "Synthesizing CloudFormation template..."
cdk synth

echo "Do you want to deploy the stack to AWS now? (y/n)"
read -r deploy_choice

if [[ "$deploy_choice" == "y" || "$deploy_choice" == "Y" ]]; then
    echo "Deploying SimpleFactoryTwinStack..."
    cdk deploy --require-approval never
    echo "Deployment completed successfully!"
else
    echo "Deployment skipped. You can deploy later by running 'cdk deploy'."
fi

# Deactivate virtual environment
deactivate

echo "======================================================================"
echo "Process completed"
echo "======================================================================"