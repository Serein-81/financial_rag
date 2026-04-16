import requests
import json

url = "http://localhost:8000/api/v1/a2a/dispatch"
payload = {"query": "合同审查与风险评估", "agent_name": "legal_specialist"}

response = requests.post(url, json=payload, timeout=90)
data = response.json()

print(json.dumps(data, ensure_ascii=False, indent=2))
