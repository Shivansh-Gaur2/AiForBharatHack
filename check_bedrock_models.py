import os, json, boto3
from dotenv import load_dotenv
load_dotenv('.env', override=True)

client = boto3.client('bedrock-runtime', region_name='us-east-1',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))

prompt = "In one sentence, give a friendly loan repayment tip for a small farmer."

candidates = [
    ("amazon.nova-micro-v1:0", "nova"),
    ("amazon.nova-lite-v1:0", "nova"),
    ("anthropic.claude-3-haiku-20240307-v1:0", "claude"),
    ("meta.llama3-8b-instruct-v1:0", "llama"),
    ("mistral.mistral-7b-instruct-v0:2", "mistral"),
    ("mistral.mistral-small-2402-v1:0", "mistral"),
]

def make_body(model_id, family, p):
    if family == "nova":
        return json.dumps({"messages":[{"role":"user","content":[{"text":p}]}],"inferenceConfig":{"maxTokens":80}}).encode()
    elif family == "claude":
        return json.dumps({"anthropic_version":"bedrock-2023-05-31","max_tokens":80,"messages":[{"role":"user","content":p}]}).encode()
    elif family == "llama":
        return json.dumps({"prompt":f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n{p}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n","max_gen_len":80}).encode()
    elif family == "mistral":
        return json.dumps({"prompt":f"<s>[INST]{p}[/INST]","max_tokens":80}).encode()

def parse_resp(family, body):
    if family == "nova":
        return body.get("output",{}).get("message",{}).get("content",[{}])[0].get("text","").strip()
    elif family == "claude":
        return (body.get("content",[{}])[0].get("text","")).strip()
    elif family == "llama":
        return body.get("generation","").strip()
    elif family == "mistral":
        return body.get("outputs",[{}])[0].get("text","").strip()

for model_id, family in candidates:
    try:
        resp = client.invoke_model(modelId=model_id, contentType="application/json", accept="application/json", body=make_body(model_id, family, prompt))
        result = json.loads(resp['body'].read())
        text = parse_resp(family, result)
        print(f"PASS [{model_id}]: {text[:100]}")
    except Exception as e:
        code = getattr(e, 'response', {}).get('Error', {}).get('Code', type(e).__name__)
        msg = getattr(e, 'response', {}).get('Error', {}).get('Message', str(e))[:80]
        print(f"FAIL [{model_id}]: {code} - {msg}")
