"""Clean duplicate profiles from DynamoDB, then verify all data."""
import boto3
import requests

REGION = "us-east-1"
URLS = {
    "profile":       "https://femujje0hj.execute-api.us-east-1.amazonaws.com",
    "loan":          "https://068aqecn2j.execute-api.us-east-1.amazonaws.com",
    "risk":          "https://54t4r7xt4k.execute-api.us-east-1.amazonaws.com",
    "cashflow":      "https://0d90oqcz5c.execute-api.us-east-1.amazonaws.com",
    "early_warning": "https://l9u8ls8k0f.execute-api.us-east-1.amazonaws.com",
    "guidance":      "https://77qr8f1p10.execute-api.us-east-1.amazonaws.com",
}

GOOD_IDS = {
    "639bbf1f-e022-431c-aa2d-c61565e4ab50",
    "c0366df2-b3e5-4c21-b6d9-db8a91bd905c",
    "816eb6b1-d8f9-46f0-9143-473444ad46ee",
    "66e97b96-d15a-45b7-925a-46382869744c",
    "894208ef-6f9c-4e63-b62c-b714ad32c19f",
}

# Step 1: Clean duplicates from DynamoDB
print("=" * 60)
print("STEP 1: Cleaning duplicate profiles")
print("=" * 60)

dynamodb = boto3.resource("dynamodb", region_name=REGION)

for tbl_name in ["rural-credit-profiles", "rural-credit-loans", "rural-credit-cashflow",
                  "rural-credit-risk", "rural-credit-early-warning", "rural-credit-guidance"]:
    tbl = dynamodb.Table(tbl_name)
    resp = tbl.scan()
    items = resp["Items"]
    while resp.get("LastEvaluatedKey"):
        resp = tbl.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp["Items"])

    deleted = 0
    for item in items:
        pk = item.get("PK", "")
        sk = item.get("SK", "")
        # Try to find profile_id from various fields
        pid = item.get("profile_id", "")
        if not pid and pk.startswith("PROFILE#"):
            pid = pk.replace("PROFILE#", "")
        if not pid:
            # Try to extract from other PK patterns
            for prefix in ["LOAN#", "CASHFLOW#", "RISK#", "ALERT#", "GUIDANCE#"]:
                if pk.startswith(prefix):
                    # profile_id might be in SK or another field
                    pid = item.get("borrower_profile_id", "")
                    break

        if pid and pid not in GOOD_IDS:
            tbl.delete_item(Key={"PK": pk, "SK": sk})
            deleted += 1

    print(f"  {tbl_name}: deleted {deleted} orphaned items")

# Step 2: Verify
print("\n" + "=" * 60)
print("STEP 2: Full Verification")
print("=" * 60)

def get(url):
    try:
        r = requests.get(url, timeout=30)
        return r.status_code, r.json()
    except Exception as e:
        return 0, str(e)

r = requests.get(f"{URLS['profile']}/api/v1/profiles/", timeout=30)
profiles = r.json().get("items", [])
print(f"\nProfiles: {len(profiles)}")

for p in profiles:
    pid = p["profile_id"]
    name = p["name"]
    print(f"\n  {name} — {pid}")

    # Loans (correct: /borrower/)
    c, d = get(f"{URLS['loan']}/api/v1/loans/borrower/{pid}")
    if c == 200:
        loans = d if isinstance(d, list) else d.get("items", d.get("loans", []))
        print(f"    Loans: {len(loans) if isinstance(loans, list) else '?'}")
    else:
        print(f"    Loans: HTTP {c}")

    # Cashflow
    c, d = get(f"{URLS['cashflow']}/api/v1/cashflow/records/{pid}")
    if c == 200:
        records = d if isinstance(d, list) else d.get("items", d.get("records", []))
        print(f"    Cashflow: {len(records) if isinstance(records, list) else '?'} records")
    else:
        print(f"    Cashflow: HTTP {c}")

    # Risk
    c, d = get(f"{URLS['risk']}/api/v1/risk/profile/{pid}")
    if c == 200:
        items_list = d if isinstance(d, list) else d.get("items", d.get("assessments", [d]))
        if isinstance(items_list, list) and items_list:
            latest = items_list[0]
            score = latest.get("risk_score", "?") if isinstance(latest, dict) else "?"
            print(f"    Risk: score={score}")
        else:
            print(f"    Risk: present")
    else:
        print(f"    Risk: HTTP {c}")

    # Early Warning
    c, d = get(f"{URLS['early_warning']}/api/v1/early-warning/alerts/profile/{pid}")
    if c == 200:
        alerts = d if isinstance(d, list) else d.get("items", d.get("alerts", []))
        print(f"    EarlyWarning: {len(alerts) if isinstance(alerts, list) else 1} alert(s)")
    else:
        print(f"    EarlyWarning: HTTP {c}")

    # Guidance (correct: /profile/{pid}/history)
    c, d = get(f"{URLS['guidance']}/api/v1/guidance/profile/{pid}/history")
    if c == 200:
        items_list = d if isinstance(d, list) else d.get("items", d.get("recommendations", []))
        print(f"    Guidance: {len(items_list) if isinstance(items_list, list) else 1} rec(s)")
    else:
        print(f"    Guidance: HTTP {c}")

# DynamoDB counts
print("\n" + "=" * 60)
print("DynamoDB Table Counts (after cleanup):")
client = boto3.client("dynamodb", region_name=REGION)
for t in ["rural-credit-profiles", "rural-credit-loans", "rural-credit-cashflow",
           "rural-credit-risk", "rural-credit-early-warning", "rural-credit-guidance"]:
    r = client.scan(TableName=t, Select="COUNT")
    print(f"  {t:35s} {r['Count']:>5} items")
print("=" * 60)
