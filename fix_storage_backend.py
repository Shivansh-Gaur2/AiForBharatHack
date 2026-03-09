"""Add STORAGE_BACKEND=dynamodb to all Lambda functions."""
import subprocess, json

REGION = "us-east-1"

# All Lambda function names
functions = [
    "rural-credit-profile-servic-ProfileServiceFunction-wYPMW5BM5c6k",
    "rural-credit-loan-tracker-LoanTrackerFunction-aHFXdn0V32aH",
    "rural-credit-risk-assessmen-RiskAssessmentFunction-Rj0FKAqsaFsU",
    "rural-credit-cashflow",
    "rural-credit-early-warning-EarlyWarningFunction-Qku2vLBXEVGy",
    "rural-credit-guidance-GuidanceFunction-8ZlUIB1BGt4r",
    "rural-credit-security-SecurityFunction-go41zs5pNJDT",
    "rural-credit-ai-advisor-AIAdvisorFunction-CnvHjRhOK6wx",
]

for fn in functions:
    print(f"\n--- {fn} ---")
    
    # Get current env vars
    result = subprocess.run(
        ["aws", "lambda", "get-function-configuration",
         "--function-name", fn,
         "--region", REGION,
         "--query", "Environment",
         "--output", "json"],
        capture_output=True, text=True
    )
    env = json.loads(result.stdout)
    variables = env.get("Variables", {})
    
    # Check current value
    current = variables.get("STORAGE_BACKEND", "<missing>")
    print(f"  Current STORAGE_BACKEND: {current}")
    
    if current == "dynamodb":
        print("  Already set — skipping")
        continue
    
    # Add STORAGE_BACKEND=dynamodb
    variables["STORAGE_BACKEND"] = "dynamodb"
    env_json = json.dumps({"Variables": variables})
    
    result2 = subprocess.run(
        ["aws", "lambda", "update-function-configuration",
         "--function-name", fn,
         "--region", REGION,
         "--environment", env_json,
         "--output", "text",
         "--query", "LastUpdateStatus"],
        capture_output=True, text=True
    )
    print(f"  Updated -> {result2.stdout.strip()}")

print("\n=== DONE ===")
