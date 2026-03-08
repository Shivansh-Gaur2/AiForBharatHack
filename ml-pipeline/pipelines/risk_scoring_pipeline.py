"""SageMaker Pipeline – Risk Scoring (XGBoost).

Defines the ML pipeline DAG for the risk scoring model:
  DataProcessing → Training → Evaluation → ConditionalApproval → Registration
"""

from __future__ import annotations

import json
import logging
from typing import Any

import sagemaker
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterFloat, ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.step_collections import RegisterModel

logger = logging.getLogger(__name__)


def create_risk_scoring_pipeline(
    role: str,
    bucket: str,
    region: str = "ap-south-1",
    pipeline_name: str = "rural-credit-risk-scoring",
) -> Pipeline:
    """Build and return the SageMaker Pipeline for risk scoring."""

    # -----------------------------------------------------------------------
    # Pipeline parameters
    # -----------------------------------------------------------------------
    processing_instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge",
    )
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.xlarge",
    )
    input_data_uri = ParameterString(
        name="InputDataUri", default_value=f"s3://{bucket}/data/risk/",
    )
    min_f1_threshold = ParameterFloat(name="MinF1Threshold", default_value=0.78)
    min_auc_threshold = ParameterFloat(name="MinAUCThreshold", default_value=0.85)
    max_depth = ParameterInteger(name="MaxDepth", default_value=6)
    eta = ParameterFloat(name="Eta", default_value=0.1)
    num_round = ParameterInteger(name="NumRound", default_value=300)

    session = sagemaker.Session()
    image_uri = sagemaker.image_uris.retrieve("xgboost", region, version="1.7-1")

    # -----------------------------------------------------------------------
    # Step 1: Data processing / feature engineering
    # -----------------------------------------------------------------------
    processor = ScriptProcessor(
        role=role,
        image_uri=image_uri,
        instance_count=1,
        instance_type=processing_instance_type,
        command=["python3"],
        sagemaker_session=session,
    )

    step_process = ProcessingStep(
        name="RiskFeatureEngineering",
        processor=processor,
        inputs=[
            ProcessingInput(source=input_data_uri, destination="/opt/ml/processing/input"),
        ],
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/output/train"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/output/test"),
        ],
        code="ml-pipeline/data/feature_engineering/risk_features.py",
    )

    # -----------------------------------------------------------------------
    # Step 2: Training
    # -----------------------------------------------------------------------
    estimator = Estimator(
        image_uri=image_uri,
        role=role,
        instance_count=1,
        instance_type=training_instance_type,
        output_path=f"s3://{bucket}/models/risk/",
        sagemaker_session=session,
        hyperparameters={
            "max_depth": max_depth,
            "eta": eta,
            "num_round": num_round,
            "objective": "multi:softprob",
            "num_class": 4,
            "eval_metric": "mlogloss",
        },
    )

    step_train = TrainingStep(
        name="RiskXGBoostTraining",
        estimator=estimator,
        inputs={
            "train": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                content_type="text/csv",
            ),
        },
    )

    # -----------------------------------------------------------------------
    # Step 3: Evaluation
    # -----------------------------------------------------------------------
    evaluation_report = PropertyFile(
        name="EvaluationReport", output_name="evaluation", path="evaluation.json",
    )

    step_eval = ProcessingStep(
        name="RiskModelEvaluation",
        processor=processor,
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
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
        code="ml-pipeline/evaluation/evaluate_risk.py",
        property_files=[evaluation_report],
    )

    # -----------------------------------------------------------------------
    # Step 4: Conditional model registration
    # -----------------------------------------------------------------------
    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri="{}/evaluation.json".format(
                step_eval.arguments["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"]
            ),
            content_type="application/json",
        )
    )

    step_register = RegisterModel(
        name="RegisterRiskModel",
        estimator=estimator,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["application/json", "text/csv"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large", "ml.t2.medium"],
        transform_instances=["ml.m5.large"],
        model_package_group_name="RuralCreditRiskScoring",
        approval_status="PendingManualApproval",
        model_metrics=model_metrics,
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
        name="CheckRiskModelQuality",
        conditions=[f1_condition],
        if_steps=[step_register],
        else_steps=[],
    )

    # -----------------------------------------------------------------------
    # Assemble pipeline
    # -----------------------------------------------------------------------
    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_type,
            training_instance_type,
            input_data_uri,
            min_f1_threshold,
            min_auc_threshold,
            max_depth,
            eta,
            num_round,
        ],
        steps=[step_process, step_train, step_eval, step_cond],
        sagemaker_session=session,
    )

    return pipeline


if __name__ == "__main__":
    import boto3

    role = sagemaker.get_execution_role()
    bucket = sagemaker.Session().default_bucket()
    pipeline = create_risk_scoring_pipeline(role, bucket)
    pipeline.upsert(role_arn=role)
    logger.info("Pipeline created/updated: %s", pipeline.name)
