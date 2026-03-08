"""Shared AWS helpers for ML model artifact loading.

Usage (in each service's _ensure_loaded()):

    from services.shared.ml_utils import download_model

    prefix = os.getenv("RISK_MODEL_S3_PREFIX", "")
    if prefix:
        model_path = download_model(f"{prefix}/risk_model.joblib")
    else:
        model_path = Path("ml-pipeline/saved_models/risk_model.joblib")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# /tmp on Lambda; override via MODEL_CACHE_DIR for local/ECS use
_LOCAL_CACHE = Path(os.getenv("MODEL_CACHE_DIR", "/tmp/models"))


def download_model(s3_key: str) -> Path:
    """Download an S3 model artifact to the local disk cache on first call.

    Subsequent calls within the same process return immediately (file already
    present).  This gives one S3 download per cold-start per artifact.

    Parameters
    ----------
    s3_key : str
        Full S3 key relative to the bucket root.
        Example: ``"risk/v1/risk_model.joblib"``

    Returns
    -------
    Path
        Absolute local path of the downloaded artifact.

    Raises
    ------
    KeyError
        If ``MODEL_S3_BUCKET`` environment variable is not set.
    botocore.exceptions.ClientError
        If the S3 object does not exist or IAM permissions are missing.
    """
    bucket = os.environ["MODEL_S3_BUCKET"]
    local_path = _LOCAL_CACHE / s3_key
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if local_path.exists():
        logger.debug("Model cache hit: %s", local_path)
        return local_path

    import boto3  # imported lazily so services without boto3 installed still work locally

    region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    logger.info("Downloading s3://%s/%s → %s", bucket, s3_key, local_path)

    s3 = boto3.client("s3", region_name=region)
    s3.download_file(bucket, s3_key, str(local_path))

    logger.info("Downloaded %s (%.1f KB)", s3_key, local_path.stat().st_size / 1024)
    return local_path


def is_running_on_aws() -> bool:
    """Return True when executing inside an AWS Lambda or ECS environment."""
    return bool(
        os.getenv("AWS_LAMBDA_FUNCTION_NAME")        # Lambda
        or os.getenv("ECS_CONTAINER_METADATA_URI")   # ECS/Fargate
    )
