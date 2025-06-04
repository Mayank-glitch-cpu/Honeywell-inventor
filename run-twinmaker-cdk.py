#!/usr/bin/env python3
from aws_cdk import (
    App, Stack, RemovalPolicy,
    aws_s3 as s3,
    aws_iam as iam,
    aws_iottwinmaker as twinmaker
)
from constructs import Construct

# Configurable parameters for reuse
WORKSPACE_ID = "SimpleFactoryTwin"  # TwinMaker workspace name (ID)
# If you have an existing S3 bucket to use for TwinMaker assets, set its name here:
EXISTING_BUCKET_NAME = None  # e.g., "my-twinmaker-assets-bucket"

class SimpleFactoryTwinStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # 1. Create or reference an S3 bucket to store TwinMaker assets (models, scenes, etc.)
        if EXISTING_BUCKET_NAME:
            # Use an existing bucket by name
            bucket = s3.Bucket.from_bucket_name(self, "TwinMakerAssetsBucket", EXISTING_BUCKET_NAME)
        else:
            # Create a new S3 bucket for TwinMaker assets (unique name including account and region)
            bucket = s3.Bucket(self, "TwinMakerAssetsBucket",
                               bucket_name="simplefactorytwin-assets-" + Stack.of(self).account + "-" + Stack.of(self).region,
                               removal_policy=RemovalPolicy.RETAIN,  # Retain bucket when stack is deleted (avoid accidental data loss)
                               block_public_access=s3.BlockPublicAccess.BLOCK_ALL)
            # (For development/testing, you could use RemovalPolicy.DESTROY with auto_delete_objects=True to clean up automatically)

        # 2. Create an IAM role with appropriate TwinMaker permissions (assumed by TwinMaker service)
        twinmaker_role = iam.Role(self, "TwinMakerWorkspaceRole",
                                  assumed_by=iam.ServicePrincipal("iottwinmaker.amazonaws.com"),
                                  description="Execution role for AWS IoT TwinMaker workspace")
        # Attach S3 access permissions (restricting to the TwinMaker assets bucket)
        twinmaker_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetBucket*", "s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"]
        ))
        # Allow TwinMaker to delete its workspace marker file in the bucket upon workspace deletion
        twinmaker_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:DeleteObject"],
            resources=[bucket.arn_for_objects("DO_NOT_DELETE_WORKSPACE_*")]
        ))

        # 3. Create the TwinMaker workspace
        workspace = twinmaker.CfnWorkspace(self, "SimpleFactoryTwinWorkspace",
            workspace_id=WORKSPACE_ID,
            role=twinmaker_role.role_arn,
            s3_location=bucket.bucket_arn,
            description="TwinMaker workspace for the Simple Factory digital twin"
        )

        # 4. Define component types for Conveyor, Robot Arm, and Inspection Station
        # Conveyor component type with properties: Speed (double), Status (string), Next (relationship to RobotArmType)
        conveyor_type = twinmaker.CfnComponentType(self, "ConveyorTypeDef",
            workspace_id=WORKSPACE_ID,
            component_type_id="ConveyorType",
            description="Component type for a conveyor belt",
            property_definitions={
                "Speed": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(type="DOUBLE", unit_of_measure="m/s")
                ),
                "Status": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(type="STRING")
                ),
                "Next": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(
                        type="RELATIONSHIP",
                        relationship=twinmaker.CfnComponentType.RelationshipProperty(
                            relationship_type="CONNECTS_TO",
                            target_component_type_id="RobotArmType"  # target component type for the relationship
                        )
                    )
                )
            }
        )
        # Robotic Arm component type with properties: ArmAngle (double), Status (string), Next (relationship to InspectionStationType)
        robot_type = twinmaker.CfnComponentType(self, "RobotArmTypeDef",
            workspace_id=WORKSPACE_ID,
            component_type_id="RobotArmType",
            description="Component type for a robotic arm",
            property_definitions={
                "ArmAngle": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(type="DOUBLE", unit_of_measure="degrees")
                ),
                "Status": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(type="STRING")
                ),
                "Next": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(
                        type="RELATIONSHIP",
                        relationship=twinmaker.CfnComponentType.RelationshipProperty(
                            relationship_type="CONNECTS_TO",
                            target_component_type_id="InspectionStationType"
                        )
                    )
                )
            }
        )
        # Inspection Station component type with properties: QualityScore (double), Status (string)
        inspection_type = twinmaker.CfnComponentType(self, "InspectionStationTypeDef",
            workspace_id=WORKSPACE_ID,
            component_type_id="InspectionStationType",
            description="Component type for a quality inspection station",
            property_definitions={
                "QualityScore": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(type="DOUBLE")
                ),
                "Status": twinmaker.CfnComponentType.PropertyDefinitionProperty(
                    data_type=twinmaker.CfnComponentType.DataTypeProperty(type="STRING")
                )
                # No "Next" property here, as this is the final station in the chain
            }
        )
        # Ensure component types are created in order (target types exist before referencing types)
        robot_type.add_dependency(inspection_type)
        conveyor_type.add_dependency(robot_type)

        # 5. Create entities for MainConveyor, AssemblyRobot, and QualityStation, attaching the corresponding component types
        # QualityStation entity (InspectionStationType component)
        quality_station_entity = twinmaker.CfnEntity(self, "QualityStationEntity",
            workspace_id=WORKSPACE_ID,
            entity_name="QualityStation",
            entity_id="QualityStationEntity",  # explicit entity ID for reference in relationships
            components={
                "InspectionComponent": twinmaker.CfnEntity.ComponentProperty(
                    component_name="InspectionComponent",
                    component_type_id="InspectionStationType",
                    properties={
                        "QualityScore": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(double_value=0.0)
                        ),
                        "Status": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(string_value="IDLE")
                        )
                    }
                )
            }
        )
        # AssemblyRobot entity (RobotArmType component) – CONNECTS_TO QualityStation
        assembly_robot_entity = twinmaker.CfnEntity(self, "AssemblyRobotEntity",
            workspace_id=WORKSPACE_ID,
            entity_name="AssemblyRobot",
            entity_id="AssemblyRobotEntity",
            components={
                "RobotComponent": twinmaker.CfnEntity.ComponentProperty(
                    component_name="RobotComponent",
                    component_type_id="RobotArmType",
                    properties={
                        "ArmAngle": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(double_value=0.0)
                        ),
                        "Status": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(string_value="IDLE")
                        ),
                        # Next property defines CONNECTS_TO relationship to QualityStation entity
                        "Next": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(
                                relationship_value=twinmaker.CfnEntity.RelationshipValueProperty(
                                    target_entity_id="QualityStationEntity",
                                    target_component_name="InspectionComponent"
                                )
                            )
                        )
                    }
                )
            }
        )
        # MainConveyor entity (ConveyorType component) – CONNECTS_TO AssemblyRobot
        main_conveyor_entity = twinmaker.CfnEntity(self, "MainConveyorEntity",
            workspace_id=WORKSPACE_ID,
            entity_name="MainConveyor",
            entity_id="MainConveyorEntity",
            components={
                "ConveyorComponent": twinmaker.CfnEntity.ComponentProperty(
                    component_name="ConveyorComponent",
                    component_type_id="ConveyorType",
                    properties={
                        "Speed": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(double_value=0.0)
                        ),
                        "Status": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(string_value="STOPPED")
                        ),
                        # Next property defines CONNECTS_TO relationship to AssemblyRobot entity
                        "Next": twinmaker.CfnEntity.PropertyProperty(
                            value=twinmaker.CfnEntity.DataValueProperty(
                                relationship_value=twinmaker.CfnEntity.RelationshipValueProperty(
                                    target_entity_id="AssemblyRobotEntity",
                                    target_component_name="RobotComponent"
                                )
                            )
                        )
                    }
                )
            }
        )
        # Add dependencies to ensure target entities are created before the ones referencing them
        assembly_robot_entity.add_dependency(quality_station_entity)
        main_conveyor_entity.add_dependency(assembly_robot_entity)

        # 6. (Optional) Create a TwinMaker scene with these entities (placeholder content location)
        scene = twinmaker.CfnScene(self, "FactoryScene",
            workspace_id=WORKSPACE_ID,
            scene_id="SimpleFactoryScene",
            content_location=f"s3://{bucket.bucket_name}/scenes/SimpleFactoryScene.json",
            description="Placeholder 3D scene for the Simple Factory"
        )
        # Ensure scene is created after the workspace (and bucket)
        scene.node.add_dependency(workspace)
        scene.node.add_dependency(bucket)
        # (Upload a corresponding scene file to the S3 path above for actual 3D visualization in TwinMaker)

# Initialize app and stack
app = App()
SimpleFactoryTwinStack(app, "SimpleFactoryTwinStack")
app.synth()
