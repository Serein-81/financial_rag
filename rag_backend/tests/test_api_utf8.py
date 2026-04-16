import requests
import json

url = "http://localhost:8000/api/v1/a2a/dispatch"
payload = {
    "query": "分析公司财务报表",
    "agent_name": "finance_specialist"
}

response = requests.post(url, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
