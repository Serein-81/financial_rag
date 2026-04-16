import requests
import json
import time

url = "http://localhost:8000/api/v1/a2a/dispatch"

test_cases = [
    {
        "name": "FinanceSpecialist - 财务报表",
        "payload": {"query": "分析公司财务报表", "agent_name": "finance_specialist"},
        "expected_domain": "financial_statement",
        "field": "domain",
        "timeout": 60
    },
    {
        "name": "TaxSpecialist - 税务合规",
        "payload": {"query": "企业税务合规性审查", "agent_name": "tax_specialist"},
        "expected_domain": "other",
        "field": "tax_type",
        "timeout": 60
    },
    {
        "name": "LegalSpecialist - 合同审查",
        "payload": {"query": "合同审查与风险评估", "agent_name": "legal_specialist"},
        "expected_domain": "contract",
        "field": "domain",
        "timeout": 120
    }
]

all_passed = True

for test in test_cases:
    print(f"\n{'='*60}")
    print(f"Test: {test['name']}")
    print(f"Expected {test['field']}: {test['expected_domain']}")
    print(f"{'='*60}")

    try:
        response = requests.post(url, json=test["payload"], timeout=test["timeout"])
        data = response.json()

        if data.get("success"):
            result = data.get("result", {})
            actual_value = result.get(test["field"], "N/A")
            status = "[PASS]" if actual_value == test["expected_domain"] else "[FAIL]"

            if actual_value != test["expected_domain"]:
                all_passed = False

            print(f"Status: {status}")
            print(f"Actual {test['field']}: {actual_value}")
            print(f"Duration: {data.get('duration_ms', 0):.0f}ms")
        else:
            print(f"[FAIL] Request failed: {data.get('error')}")
            all_passed = False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        all_passed = False

    time.sleep(2)

print(f"\n{'='*60}")
if all_passed:
    print("All tests [PASSED]")
else:
    print("Some tests [FAILED]")
print(f"{'='*60}")
