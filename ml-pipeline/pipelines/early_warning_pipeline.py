"""SageMaker Pipeline – Early Warning (IF + LightGBM).

Two-stage pipeline:
  Phase A: DataProcessing → IF Training → IF Scoring
  Phase B: LGB Training → Evaluation → ConditionalApproval
"""

from __future__ import annotations

import logging

import sagemaker
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn import SKLearn
from sagemaker.inputs import TrainingInput
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterFloat, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.step_collections import RegisterModel

logger = logging.getLogger(__name__)


def create_early_warning_pipeline(
    role: str,
    bucket: str,
    region: str = "ap-south-1",
    pipeline_name: str = "rural-credit-early-warning",
) -> Pipeline:
    """Build SageMaker Pipeline for early-warning models."""

    processing_instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge",
    )
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.large",
    )
    input_data_uri = ParameterString(
        name="InputDataUri", default_value=f"s3://{bucket}/data/early_warning/",
    )
    min_f1_threshold = ParameterFloat(name="MinF1Threshold", default_value=0.70)

    session = sagemaker.Session()
    sklearn_image = sagemaker.image_uris.retrieve("sklearn", region, version="1.2-1")

    processor = ScriptProcessor(
        role=role,
        image_uri=sklearn_image,
        instance_count=1,
        instance_type=processing_instance_type,
        command=["python3"],
        sagemaker_session=session,
    )

    # Step 1: Feature engineering
    step_process = ProcessingStep(
        name="EarlyWarningFeatureEngineering",
        processor=processor,
        inputs=[ProcessingInput(source=input_data_uri, destination="/opt/ml/processing/input")],
        outputs=[
            ProcessingOutput(output_name="features", source="/opt/ml/processing/output/features"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/output/test"),
        ],
        code="ml-pipeline/data/feature_engineering/early_warning_features.py",
    )

    # Step 2: Phase A – Isolation Forest
    if_estimator = SKLearn(
        entry_point="ml-pipeline/models/early_warning/train_isolation_forest.py",
        role=role,
        instance_count=1,
        instance_type=training_instance_type,
        framework_version="1.2-1",
        py_version="py3",
        output_path=f"s3://{bucket}/models/early_warning/if/",
        sagemaker_session=session,
        hyperparameters={"n-estimators": 200, "contamination": 0.08},
    )

    step_train_if = TrainingStep(
        name="IsolationForestTraining",
        estimator=if_estimator,
        inputs={
            "training": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["features"].S3Output.S3Uri,
            ),
        },
    )

    # Step 3: Phase B – LightGBM severity classifier
    lgb_estimator = SKLearn(
        entry_point="ml-pipeline/models/early_warning/train_lightgbm_classifier.py",
        role=role,
        instance_count=1,
        instance_type=training_instance_type,
        framework_version="1.2-1",
        py_version="py3",
        output_path=f"s3://{bucket}/models/early_warning/lgb/",
        sagemaker_session=session,
        hyperparameters={
            "n-estimators": 500,
            "learning-rate": 0.05,
            "if-model-dir": step_train_if.properties.ModelArtifacts.S3ModelArtifacts,
        },
    )

    step_train_lgb = TrainingStep(
        name="LightGBMSeverityTraining",
        estimator=lgb_estimator,
        inputs={
            "training": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["features"].S3Output.S3Uri,
            ),
        },
    )

    # Step 4: Evaluation
    evaluation_report = PropertyFile(
        name="EarlyWarningEvalReport", output_name="evaluation", path="evaluation.json",
    )

    step_eval = ProcessingStep(
        name="EarlyWarningEvaluation",
        processor=processor,
        inputs=[
            ProcessingInput(
                source=step_train_lgb.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
            ),
        ],
        outputs=[
            ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation"),
        ],
        code="ml-pipeline/evaluation/evaluate_early_warning.py",
        property_files=[evaluation_report],
    )

    # Step 5: Register
    step_register = RegisterModel(
        name="RegisterEarlyWarningModel",
        estimator=lgb_estimator,
        model_data=step_train_lgb.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name="RuralCreditEarlyWarning",
        approval_status="PendingManualApproval",
    )

    f1_condition = ConditionGreaterThanOrEqualTo(
        left=JsonGet(
            step_name=step_eval.name,
            property_file=evaluation_report,
            json_path="classification_metrics.f1_weighted",
        ),
        right=min_f1_threshold,
    )

    step_cond = ConditionStep(
        name="CheckEarlyWarningQuality",
        conditions=[f1_condition],
        if_steps=[step_register],
        else_steps=[],
    )

    return Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_type, training_instance_type,
            input_data_uri, min_f1_threshold,
        ],
        steps=[step_process, step_train_if, step_train_lgb, step_eval, step_cond],
        sagemaker_session=session,
    )
