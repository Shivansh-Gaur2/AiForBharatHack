"""SageMaker Pipeline – Cash Flow Prediction (Prophet).

DAG: DataProcessing → ClusterTraining → Evaluation → ConditionalApproval
"""

from __future__ import annotations

import logging

import sagemaker
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn import SKLearn
from sagemaker.inputs import TrainingInput
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterFloat, ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.step_collections import RegisterModel

logger = logging.getLogger(__name__)


def create_cashflow_pipeline(
    role: str,
    bucket: str,
    region: str = "ap-south-1",
    pipeline_name: str = "rural-credit-cashflow-prediction",
) -> Pipeline:
    """Build SageMaker Pipeline for Prophet cash-flow models."""

    processing_instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge",
    )
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.xlarge",
    )
    input_data_uri = ParameterString(
        name="InputDataUri", default_value=f"s3://{bucket}/data/cashflow/",
    )
    max_mape_threshold = ParameterFloat(name="MaxMAPEThreshold", default_value=15.0)
    n_clusters = ParameterInteger(name="NClusters", default_value=20)

    session = sagemaker.Session()

    # Use SKLearn framework estimator (Prophet is pip-installed)
    sklearn_estimator = SKLearn(
        entry_point="ml-pipeline/models/cashflow_prediction/train_prophet.py",
        role=role,
        instance_count=1,
        instance_type=training_instance_type,
        framework_version="1.2-1",
        py_version="py3",
        output_path=f"s3://{bucket}/models/cashflow/",
        sagemaker_session=session,
        hyperparameters={
            "n-clusters": n_clusters,
            "changepoint-prior-scale": 0.1,
            "seasonality-prior-scale": 10.0,
            "forecast-horizon": 12,
        },
    )

    processor = ScriptProcessor(
        role=role,
        image_uri=sagemaker.image_uris.retrieve("sklearn", region, version="1.2-1"),
        instance_count=1,
        instance_type=processing_instance_type,
        command=["python3"],
        sagemaker_session=session,
    )

    # Step 1: Data prep
    step_process = ProcessingStep(
        name="CashFlowFeatureEngineering",
        processor=processor,
        inputs=[
            ProcessingInput(source=input_data_uri, destination="/opt/ml/processing/input"),
        ],
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/output/train"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/output/test"),
        ],
        code="ml-pipeline/data/feature_engineering/cashflow_features.py",
    )

    # Step 2: Training
    step_train = TrainingStep(
        name="ProphetClusterTraining",
        estimator=sklearn_estimator,
        inputs={
            "training": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
            ),
        },
    )

    # Step 3: Evaluation
    evaluation_report = PropertyFile(
        name="CashFlowEvalReport", output_name="evaluation", path="evaluation.json",
    )

    step_eval = ProcessingStep(
        name="CashFlowModelEvaluation",
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
        code="ml-pipeline/evaluation/evaluate_cashflow.py",
        property_files=[evaluation_report],
    )

    # Step 4: Register if MAPE <= threshold
    step_register = RegisterModel(
        name="RegisterCashFlowModel",
        estimator=sklearn_estimator,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name="RuralCreditCashFlowPrediction",
        approval_status="PendingManualApproval",
    )

    mape_condition = ConditionLessThanOrEqualTo(
        left=JsonGet(
            step_name=step_eval.name,
            property_file=evaluation_report,
            json_path="regression_metrics.mape",
        ),
        right=max_mape_threshold,
    )

    step_cond = ConditionStep(
        name="CheckCashFlowModelQuality",
        conditions=[mape_condition],
        if_steps=[step_register],
        else_steps=[],
    )

    return Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_type, training_instance_type,
            input_data_uri, max_mape_threshold, n_clusters,
        ],
        steps=[step_process, step_train, step_eval, step_cond],
        sagemaker_session=session,
    )
