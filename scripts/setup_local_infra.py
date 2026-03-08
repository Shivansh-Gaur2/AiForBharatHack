"""
setup_local_infra.py — idempotent LocalStack/DynamoDB setup script.

Run this after starting Docker infra (DynamoDB Local + LocalStack) to ensure
all tables and SNS topics exist. Safe to re-run — all operations are idempotent.

Usage:
    python scripts/setup_local_infra.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load .env from workspace root
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")
SNS_ENDPOINT = os.getenv("SNS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Use fake creds for LocalStack/DynamoDB Local if real ones aren't set
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")

print(f"DynamoDB endpoint : {DYNAMODB_ENDPOINT}")
print(f"SNS endpoint      : {SNS_ENDPOINT}")
print(f"AWS region        : {AWS_REGION}")
print()

# ---------------------------------------------------------------------------
# DynamoDB tables
# ---------------------------------------------------------------------------
TABLES = [
    {
        "TableName": "rural-credit-profiles",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-loans",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-risk",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-cashflow",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-early-warning",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-guidance",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-security",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "rural-credit-conversations",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
]


def setup_dynamodb():
    dynamodb = boto3.client(
        "dynamodb",
        region_name=AWS_REGION,
        endpoint_url=DYNAMODB_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    # List existing tables
    existing = set(dynamodb.list_tables()["TableNames"])
    print(f"Existing DynamoDB tables: {sorted(existing)}")

    created = []
    skipped = []
    for table_def in TABLES:
        name = table_def["TableName"]
        if name in existing:
            skipped.append(name)
            continue
        try:
            dynamodb.create_table(**table_def)
            created.append(name)
            print(f"  ✓ Created table: {name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                skipped.append(name)
            else:
                print(f"  ✗ Failed to create {name}: {e}", file=sys.stderr)

    if skipped:
        print(f"  (skipped {len(skipped)} already-existing tables)")
    print(f"DynamoDB: {len(created)} created, {len(skipped)} already existed")
    print()


# ---------------------------------------------------------------------------
# SNS topics
# ---------------------------------------------------------------------------
SNS_TOPICS = [
    "rural-credit-events",
]


def setup_sns():
    sns = boto3.client(
        "sns",
        region_name=AWS_REGION,
        endpoint_url=SNS_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    for topic_name in SNS_TOPICS:
        try:
            resp = sns.create_topic(Name=topic_name)
            print(f"  ✓ SNS topic ready: {resp['TopicArn']}")
        except ClientError as e:
            print(f"  ✗ Failed to create SNS topic {topic_name}: {e}", file=sys.stderr)

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Setting up local infrastructure (DynamoDB + SNS)")
    print("=" * 60)
    print()

    try:
        setup_dynamodb()
    except Exception as e:
        print(f"DynamoDB setup failed: {e}", file=sys.stderr)
        print("Is DynamoDB Local running? (docker-compose up)")
        sys.exit(1)

    try:
        setup_sns()
    except Exception as e:
        print(f"SNS setup failed: {e}", file=sys.stderr)
        print("Is LocalStack running? (docker-compose up)")
        sys.exit(1)

    print("=" * 60)
    print("Local infrastructure ready.")
    print("=" * 60)
