"""Quick verification of all production data."""
import requests, json

URLS = {
    "profile":       "https://femujje0hj.execute-api.us-east-1.amazonaws.com",
    "loan":          "https://068aqecn2j.execute-api.us-east-1.amazonaws.com",
    "risk":          "https://54t4r7xt4k.execute-api.us-east-1.amazonaws.com",
    "cashflow":      "https://0d90oqcz5c.execute-api.us-east-1.amazonaws.com",
    "early_warning": "https://l9u8ls8k0f.execute-api.us-east-1.amazonaws.com",
    "guidance":      "https://77qr8f1p10.execute-api.us-east-1.amazonaws.com",
}

def get(url):
    r = requests.get(url, timeout=30)
    return r.status_code, r.json()

print("=" * 60)
print("PRODUCTION DATA VERIFICATION")
print("=" * 60)

# 1. Profiles
code, data = get(f"{URLS['profile']}/api/v1/profiles/")
profiles = data.get("items", [])
print(f"\nPROFILES: {len(profiles)}")
for p in profiles:
    pid = p["profile_id"]
    name = p["name"]
    loc = p["location"]
    print(f"  {name:16s} | {loc:10s} | {pid}")

    # Loans
    try:
        c, d = get(f"{URLS['loan']}/api/v1/loans/profile/{pid}")
        loans = d if isinstance(d, list) else d.get("items", d.get("loans", []))
        loan_info = ", ".join(l.get("lender_name", "?")[:25] for l in loans)
        print(f"    Loans:        {len(loans):2d}  [{loan_info}]")
    except Exception as e:
        print(f"    Loans:        ERROR — {e}")

    # Cashflow
    try:
        c, d = get(f"{URLS['cashflow']}/api/v1/cashflow/records/{pid}")
        records = d if isinstance(d, list) else d.get("items", d.get("records", []))
        print(f"    Cashflow:     {len(records):2d} records")
    except Exception as e:
        print(f"    Cashflow:     ERROR — {e}")

    # Risk
    try:
        c, d = get(f"{URLS['risk']}/api/v1/risk/profile/{pid}")
        if c == 200:
            items = d if isinstance(d, list) else d.get("items", d.get("assessments", [d]))
            if isinstance(items, list) and items:
                latest = items[0] if isinstance(items[0], dict) else items
                score = latest.get("risk_score", "?") if isinstance(latest, dict) else "?"
                cat = latest.get("risk_category", "?") if isinstance(latest, dict) else "?"
                print(f"    Risk:         score={score}, category={cat}")
            else:
                print(f"    Risk:         {d}")
        else:
            print(f"    Risk:         {c}")
    except Exception as e:
        print(f"    Risk:         ERROR — {e}")

    # Early Warning
    try:
        c, d = get(f"{URLS['early_warning']}/api/v1/early-warning/alerts/profile/{pid}")
        if c == 200:
            alerts = d if isinstance(d, list) else d.get("items", d.get("alerts", [d]))
            if isinstance(alerts, list):
                print(f"    EarlyWarning: {len(alerts)} alert(s)")
            else:
                print(f"    EarlyWarning: present")
        else:
            print(f"    EarlyWarning: {c}")
    except Exception as e:
        print(f"    EarlyWarning: ERROR — {e}")

    # Guidance
    try:
        c, d = get(f"{URLS['guidance']}/api/v1/guidance/profile/{pid}")
        if c == 200:
            items = d if isinstance(d, list) else d.get("items", d.get("recommendations", [d]))
            if isinstance(items, list):
                print(f"    Guidance:     {len(items)} recommendation(s)")
            else:
                print(f"    Guidance:     present")
        else:
            print(f"    Guidance:     {c}")
    except Exception as e:
        print(f"    Guidance:     ERROR — {e}")

    print()

print("=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
