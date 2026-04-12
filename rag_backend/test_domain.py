import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')

from app.multi_agent_system.agents.finance_specialist import FinanceSpecialist, FinancialDomain

text = "分析公司财务报表"
print(f"Input: {text}", file=sys.stderr)
print(f"Input repr: {repr(text)}", file=sys.stderr)

domain_keywords = {
    "财务报表": FinancialDomain.FINANCIAL_STATEMENT,
    "资产负债表": FinancialDomain.FINANCIAL_STATEMENT,
}

for keyword, domain in domain_keywords.items():
    print(f"Checking: {repr(keyword)} in {repr(text)}", file=sys.stderr)
    if keyword in text:
        print(f"MATCH: {keyword} -> {domain}", file=sys.stderr)
        break
else:
    print("NO MATCH", file=sys.stderr)

print(f"Direct test: {'财务报表' in text}", file=sys.stderr)
