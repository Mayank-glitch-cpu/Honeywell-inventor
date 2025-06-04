import boto3
import time
import json
import argparse
from botocore.exceptions import ClientError

def create_twinmaker_workspace(workspace_id=None, non_interactive=False):
    """
    Creates an AWS IoT TwinMaker workspace for a factory digital twin
    
    Parameters:
    workspace_id (str): Optional workspace ID to use (defaults to SimpleFactoryTwin)
    non_interactive (bool): If True, use defaults without prompting
    """
    # Initialize the AWS IoT TwinMaker client
    twinmaker = boto3.client('iottwinmaker')
    
    # Initialize IAM client to check if role exists
    iam = boto3.client('iam')
    
    # Initialize S3 client to check if bucket exists
    s3 = boto3.client('s3')
    
    # Parameters
    if not workspace_id:
        workspace_id = "SimpleFactoryTwin"
    description = f"{workspace_id} factory digital twin"
    
    if non_interactive:
        bucket_name = ""
    else:
        bucket_name = input("Enter your S3 bucket name (or leave empty to create one): ").strip()
    
    # Create or validate S3 bucket
    if not bucket_name:
        # Generate a unique bucket name
        account_id = boto3.client('sts').get_caller_identity().get('Account')
        region = boto3.session.Session().region_name
        bucket_name = f"twinmaker-workspace-{account_id}-{region}-{int(time.time())}"
        
        try:
            print(f"Creating new S3 bucket: {bucket_name}")
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            print(f"S3 bucket '{bucket_name}' created successfully")
        except ClientError as e:
            print(f"Error creating bucket: {e}")
            return
    else:
        # Check if the bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Using existing S3 bucket: {bucket_name}")
        except ClientError as e:
            print(f"Error accessing bucket '{bucket_name}': {e}")
            return
            
    # Create prefix for TwinMaker assets
    prefix = workspace_id.lower()
    
    # Create or check service role
    role_name = "TwinMakerWorkspaceRole"
    role_arn = None
    
    try:
        # Check if the role already exists
        role = iam.get_role(RoleName=role_name)
        role_arn = role['Role']['Arn']
        print(f"Using existing IAM role: {role_arn}")
        
        # Update the role's permissions to make sure it has proper S3 access
        print("Updating role permissions...")
        
        # Attach policies for S3 access
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iottwinmaker:*",
                        "iotsitewise:*",
                        "s3:*"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                }
            ]
        }
        
        policy_name = "TwinMakerS3Access"
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        
        # Wait for role policy to propagate
        print("Waiting for IAM role policy to propagate...")
        time.sleep(15)
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            # Create a new service role
            print(f"Creating new IAM role: {role_name}")
            
            # Define the trust policy that allows TwinMaker to assume this role
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "iottwinmaker.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            # Create the role
            try:
                role_response = iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Role for AWS IoT TwinMaker workspace access"
                )
                role_arn = role_response['Role']['Arn']
                
                # Attach policies for S3 access
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket"
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{bucket_name}",
                                f"arn:aws:s3:::{bucket_name}/*"  # Using /* instead of /prefix* to grant access to all objects
                            ]
                        }
                    ]
                }
                
                policy_name = "TwinMakerS3Access"
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document)
                )
                
                print(f"IAM role created with ARN: {role_arn}")
                
                # Wait for role to propagate
                print("Waiting for IAM role to propagate...")
                time.sleep(15)
                
            except ClientError as e:
                print(f"Error creating IAM role: {e}")
                return
        else:
            print(f"Error checking IAM role: {e}")
            return
    
    # Create the TwinMaker workspace
    try:
        print(f"Creating TwinMaker workspace: {workspace_id}")
        
        # Remove trailing slash from prefix if present
        if prefix.endswith('/'):
            prefix = prefix.rstrip('/')
        
        response = twinmaker.create_workspace(
            workspaceId=workspace_id,
            description=description,
            s3Location=f"arn:aws:s3:::{bucket_name}",  # Just the bucket ARN without the prefix
            role=role_arn  # Note: using role instead of roleArn
        )
        print(f"Workspace created successfully with ARN: {response['arn']}")
        return response['arn']
    except ClientError as e:
        print(f"Error creating TwinMaker workspace: {e}")
        return None

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="AWS IoT TwinMaker Workspace Creator")
    parser.add_argument("--workspace-id", type=str, help="ID for the TwinMaker workspace", default="SimpleFactoryTwin")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode")
    args = parser.parse_args()
    
    print("AWS IoT TwinMaker Workspace Creator")
    print("===================================")
    workspace_arn = create_twinmaker_workspace(workspace_id=args.workspace_id, non_interactive=args.non_interactive)
    if workspace_arn:
        print("\nWorkspace setup complete!")
        print("You can now access your workspace in the AWS IoT TwinMaker console.")