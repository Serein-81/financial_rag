import requests
import json

url = "http://localhost:8000/api/v1/a2a/dispatch"
payload = {"query": "企业税务合规性审查", "agent_name": "tax_specialist"}

response = requests.post(url, json=payload, timeout=60)
data = response.json()

print(json.dumps(data, ensure_ascii=False, indent=2))
