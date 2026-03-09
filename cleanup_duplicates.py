"""
Clean up duplicate entries from DynamoDB tables.
Keeps only the latest seed run (Run 3) profiles and deletes the rest.
Also removes orphan data from other tables tied to deleted profile IDs.
"""

import boto3

REGION = "us-east-1"
dynamodb = boto3.resource("dynamodb", region_name=REGION)

# ── Profiles to KEEP (Run 3 — latest seed, most complete data) ──────────────
KEEP_PROFILE_IDS = {
    "5e3ce5b3-e91b-4074-bc1b-956f5d2a0bad",  # Ramesh Kumar
    "9e2ad0fa-bfa8-4634-ae73-c8eb92769ac1",  # Sunita Devi
    "933ec649-418e-4ecc-8dfb-0fdbc464a46e",  # Arjun Singh
    "59c20cd8-56dc-4c83-8d0f-a6f2641eaf76",  # Priya Sharma
    "fdb5eb5c-fb52-4570-aabd-d6262983557f",  # Vikram Patel
}

# ── Profiles to DELETE (Run 1, Run 2, manual entries) ────────────────────────
DELETE_PROFILE_IDS = [
    "34cf9b9c-a496-40e9-8a21-0ab9a3612271",  # Sunita Devi (Run 1)
    "43b64677-e301-4ff6-a206-bab346329ac2",  # Arjun Singh (Run 1)
    "43c624ed-f988-419a-bd81-26924db00325",  # Arjun (manual)
    "49bb5f0e-36a6-4711-b088-071ead8c9e07",  # Aditya (manual)
    "566f6273-3076-4930-ad3c-303073937f59",  # Sunita Devi (Run 2)
    "836bff55-6ad0-478e-9aaa-8f44e53631ea",  # Ramesh Kumar (Run 1)
    "9af3f165-d47f-404b-97d8-ac93e15df5aa",  # Vikram Patel (Run 1)
    "ad45b141-d0c8-4e0b-859a-1d33ab2ed981",  # Ramesh Kumar (Run 2)
    "c47b44ba-04df-4afa-9fa7-015e048281cd",  # Arjun Singh (Run 2)
    "d1a43ced-6a5d-4279-bcca-4896367db43b",  # Priya Sharma (Run 1)
    "d6492a72-ed55-4e15-82ea-49dfa6f27c2e",  # Vikram Patel (Run 2)
    "ecf9c77c-b5fa-4344-b7a2-4a7b4e2dae04",  # Priya Sharma (Run 2)
]

TABLES = [
    "rural-credit-profiles",
    "rural-credit-loans",
    "rural-credit-cashflow",
    "rural-credit-risk",
    "rural-credit-early-warning",
    "rural-credit-guidance",
]


def delete_items_by_pk(table_name: str, pk_value: str):
    """Delete all items with the given PK from a table."""
    table = dynamodb.Table(table_name)
    deleted = 0

    # Query all items with this PK
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk_value)
    )
    items = response.get("Items", [])

    # Handle pagination
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk_value),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    # Batch delete
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
            deleted += 1

    return deleted


def scan_and_delete_orphans(table_name: str, delete_ids: set):
    """Scan entire table and delete items whose PK contains any of the delete IDs."""
    table = dynamodb.Table(table_name)
    deleted = 0

    response = table.scan()
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    orphans = []
    for item in items:
        pk = item.get("PK", "")
        # PK formats: PROFILE#<id>, BORROWER#<id>, etc. — check if any delete ID is in the PK
        for did in delete_ids:
            if did in pk:
                orphans.append(item)
                break

    with table.batch_writer() as batch:
        for item in orphans:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
            deleted += 1

    return deleted


def main():
    delete_ids_set = set(DELETE_PROFILE_IDS)

    print("=" * 60)
    print("CLEANING DUPLICATE ENTRIES FROM DYNAMODB")
    print("=" * 60)
    print(f"  Keeping: {len(KEEP_PROFILE_IDS)} profiles")
    print(f"  Deleting: {len(DELETE_PROFILE_IDS)} duplicate profiles + orphan data\n")

    total_deleted = 0

    for table_name in TABLES:
        print(f"  {table_name}:")
        count = scan_and_delete_orphans(table_name, delete_ids_set)
        print(f"    Deleted {count} items")
        total_deleted += count

    print(f"\n  TOTAL DELETED: {total_deleted} items across {len(TABLES)} tables")

    # Verify remaining profiles
    print("\n" + "=" * 60)
    print("VERIFICATION — Remaining profiles:")
    print("=" * 60)
    table = dynamodb.Table("rural-credit-profiles")
    response = table.scan()
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    profiles = [i for i in items if i.get("SK", "").startswith("METADATA")]
    for p in sorted(profiles, key=lambda x: x.get("name", "")):
        pid = p.get("PK", "").replace("PROFILE#", "")
        name = p.get("name", "?")
        kept = "✓ KEPT" if pid in KEEP_PROFILE_IDS else "? UNEXPECTED"
        print(f"    {kept}  {name}  ({pid[:12]}...)")

    print(f"\n  Total remaining: {len(profiles)} profiles")
    print()


if __name__ == "__main__":
    main()
