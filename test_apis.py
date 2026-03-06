"""Quick integration test for all 3rd-party APIs.

Run from the workspace root:
    python test_apis.py
"""
import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv(".env", override=True)

WEATHER_KEY    = os.getenv("WEATHER_API_KEY", "")
MARKET_KEY     = os.getenv("MARKET_API_KEY", "")
BEDROCK_MODEL  = os.getenv("BEDROCK_MODEL_ID", "")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "ap-south-1")
AWS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET     = os.getenv("AWS_SECRET_ACCESS_KEY", "")


def _masked(val: str, n: int = 8) -> str:
    return f"SET ({val[:n]}...)" if val and val not in ("local", "") else "MISSING / not set"


print("=" * 55)
print("ENV CHECK")
print("=" * 55)
print(f"  WEATHER_API_KEY   : {_masked(WEATHER_KEY)}")
print(f"  MARKET_API_KEY    : {_masked(MARKET_KEY)}")
print(f"  BEDROCK_MODEL_ID  : {BEDROCK_MODEL or 'MISSING'}")
print(f"  BEDROCK_REGION    : {BEDROCK_REGION}")
print(f"  AWS_ACCESS_KEY_ID : {_masked(AWS_KEY_ID)}")
print()


# ── Test 1: OpenWeatherMap ────────────────────────────────────────────────
async def test_weather() -> bool:
    import httpx

    print("-" * 55)
    print("TEST 1 — OpenWeatherMap")
    print("-" * 55)
    if not WEATHER_KEY:
        print("  SKIP: WEATHER_API_KEY not set")
        return False
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            r = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "Pune,IN", "appid": WEATHER_KEY, "units": "metric"},
            )
            r.raise_for_status()
            d = r.json()
        city = d["name"]
        temp = d["main"]["temp"]
        desc = d["weather"][0]["description"]
        print(f"  PASS  {city}: {temp}°C, {desc}")
        return True
    except Exception as exc:
        print(f"  FAIL  {exc}")
        return False


# ── Test 2: data.gov.in Agmarknet ─────────────────────────────────────────
async def test_market() -> bool:
    import httpx

    print("-" * 55)
    print("TEST 2 — data.gov.in Agmarknet (Rice prices)")
    print("-" * 55)
    if not MARKET_KEY:
        print("  SKIP: MARKET_API_KEY not set")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
                params={
                    "api-key": MARKET_KEY,
                    "format": "json",
                    "limit": "3",
                    "filters[Commodity]": "Rice",
                },
            )
            r.raise_for_status()
            d = r.json()
        records = d.get("records", [])
        if records:
            rec = records[0]
            commodity = rec.get("Commodity", "?")
            market    = rec.get("Market", rec.get("District", "?"))
            modal     = rec.get("Modal_Price", "?")
            total     = d.get("total", "?")
            print(f"  PASS  {commodity} @ {market} — Modal price: Rs {modal}")
            print(f"        Total records in dataset: {total}")
        else:
            print(f"  WARN  API responded but 0 records returned.")
            print(f"        Raw: {json.dumps(d)[:300]}")
        return True
    except Exception as exc:
        print(f"  FAIL  {exc}")
        return False


# ── Test 3: Amazon Bedrock ────────────────────────────────────────────────
def test_bedrock() -> bool:
    import boto3
    from botocore.exceptions import ClientError

    print("-" * 55)
    print(f"TEST 3 — Amazon Bedrock ({BEDROCK_MODEL})")
    print("-" * 55)
    if not BEDROCK_MODEL or not AWS_KEY_ID or AWS_KEY_ID == "local":
        print("  SKIP: BEDROCK_MODEL_ID or AWS credentials not set")
        return False
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=BEDROCK_REGION,
            aws_access_key_id=AWS_KEY_ID,
            aws_secret_access_key=AWS_SECRET,
        )
        # Detect model family (handle cross-region us./global. prefixes)
        base = BEDROCK_MODEL.split("/")[-1]
        is_nova   = "amazon.nova" in base
        is_claude = "anthropic."  in base

        prompt = "In one sentence, give a friendly repayment tip for a small farmer."

        if is_claude:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 80,
                "messages": [{"role": "user", "content": prompt}],
            })
        elif is_nova:
            body = json.dumps({
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                "inferenceConfig": {"maxTokens": 80, "temperature": 0.4},
            })
        else:  # Titan
            body = json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {"maxTokenCount": 80, "temperature": 0.4},
            })

        resp = client.invoke_model(
            modelId=BEDROCK_MODEL,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(resp["body"].read())

        if is_claude:
            text = result.get("content", [{}])[0].get("text", "").strip()
        elif is_nova:
            text = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "").strip()
        else:
            text = result.get("results", [{}])[0].get("outputText", "").strip()

        print(f"  PASS  AI response: {text[:250]}")
        return True
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg  = exc.response["Error"]["Message"]
        print(f"  FAIL  AWS {code}: {msg}")
        if code == "AccessDeniedException":
            print("        → Check that AmazonBedrockFullAccess policy is attached to the IAM user")
            print(f"        → Also confirm model '{BEDROCK_MODEL}' is enabled in Bedrock Model Access")
        return False
    except Exception as exc:
        print(f"  FAIL  {exc}")
        return False


async def main() -> None:
    w = await test_weather()
    print()
    m = await test_market()
    print()
    b = test_bedrock()
    print()
    print("=" * 55)
    results = {
        "OpenWeatherMap": "PASS" if w else "FAIL/SKIP",
        "Agmarknet":      "PASS" if m else "FAIL/SKIP",
        "Bedrock":        "PASS" if b else "FAIL/SKIP",
    }
    for name, status in results.items():
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon}  {name:<20} {status}")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
