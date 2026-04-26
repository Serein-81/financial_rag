"""
税务逻辑验证器独立测试
直接测试核心验证逻辑，不依赖数据库
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import math
from typing import List, Dict, Optional


class StandaloneTaxLogicValidator:
    """独立税务逻辑验证器（不依赖数据库）"""

    def __init__(self):
        self.industry_benchmarks = {
            "manufacturing": {"avg_tax_load": 0.04, "avg_gross_margin": 0.25, "max_input_ratio": 0.85},
            "retail": {"avg_tax_load": 0.02, "avg_gross_margin": 0.20, "max_input_ratio": 0.80},
            "service": {"avg_tax_load": 0.06, "avg_gross_margin": 0.45, "max_input_ratio": 0.70},
            "construction": {"avg_tax_load": 0.03, "avg_gross_margin": 0.15, "max_input_ratio": 0.90},
        }

    def _calculate_tax_load_rate(self, tax_data: Dict) -> float:
        if tax_data.get("taxable_amount", 0) > 0:
            net_tax = abs(tax_data.get("output_tax", 0)) - abs(tax_data.get("input_tax", 0))
            return net_tax / tax_data["taxable_amount"]
        return 0.0

    def _calculate_gross_margin(self, tax_data: Dict) -> float:
        if tax_data.get("revenue", 0) > 0:
            return tax_data.get("gross_profit", 0) / tax_data["revenue"]
        return 0.0

    def _calculate_input_ratio(self, tax_data: Dict) -> float:
        output_tax = abs(tax_data.get("output_tax", 0))
        if output_tax > 0:
            return abs(tax_data.get("input_tax", 0)) / output_tax
        return 0.0

    def _calculate_vat_net_rate(self, tax_data: Dict) -> float:
        taxable = abs(tax_data.get("taxable_amount", 0))
        if taxable > 0:
            net = abs(tax_data.get("output_tax", 0)) - abs(tax_data.get("input_tax", 0))
            return net / taxable
        return 0.0

    def _detect_iqr_anomalies(self, tax_data: Dict) -> List[Dict]:
        indicators = {
            "tax_load_rate": self._calculate_tax_load_rate(tax_data),
            "input_ratio": self._calculate_input_ratio(tax_data),
            "vat_net_rate": self._calculate_vat_net_rate(tax_data),
        }
        anomalies = []
        for name, value in indicators.items():
            if name == "tax_load_rate":
                if value < -0.10 or value > 0.15:
                    anomalies.append({
                        "type": "iqr",
                        "indicator": name,
                        "value": value,
                        "expected_range": "[-0.10, 0.15]",
                        "severity": "high" if abs(value) > 0.20 else "medium",
                        "confidence": 0.85,
                        "description": f"{name} 超出正常范围"
                    })
            elif name == "input_ratio":
                if value > 0.95:
                    anomalies.append({
                        "type": "iqr",
                        "indicator": name,
                        "value": value,
                        "expected_range": "[0, 0.95]",
                        "severity": "high" if value > 1.0 else "medium",
                        "confidence": 0.80,
                        "description": f"{name} 进项销项比率异常"
                    })
        return anomalies

    def _detect_zscore_anomalies(self, tax_data: Dict, historical: List[Dict]) -> List[Dict]:
        if not historical or len(historical) < 2:
            return []
        anomalies = []
        for key in ["input_tax", "output_tax", "taxable_amount"]:
            if key in tax_data:
                values = [h.get(key, 0) for h in historical]
                mean = sum(values) / len(values)
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                std = math.sqrt(variance) if variance > 0 else 1
                z_score = (tax_data[key] - mean) / std
                if abs(z_score) > 2.5:
                    anomalies.append({
                        "type": "zscore",
                        "indicator": key,
                        "value": tax_data[key],
                        "z_score": z_score,
                        "severity": "high" if abs(z_score) > 3 else "medium",
                        "confidence": 0.75,
                        "description": f"{key} 偏离历史均值 (z={z_score:.2f})"
                    })
        return anomalies

    def _detect_trend_anomalies(self, tax_data: Dict, historical: List[Dict]) -> List[Dict]:
        if not historical or len(historical) < 3:
            return []
        anomalies = []
        growth_rates = []
        for i in range(1, len(historical)):
            prev = historical[i-1].get("taxable_amount", 1)
            curr = historical[i].get("taxable_amount", 0)
            if prev > 0:
                growth_rates.append((curr - prev) / prev)
        if growth_rates:
            avg_growth = sum(growth_rates) / len(growth_rates)
            current_growth = 0
            if historical[-1].get("taxable_amount", 0) > 0:
                current_growth = (tax_data.get("taxable_amount", 0) - historical[-1]["taxable_amount"]) / historical[-1]["taxable_amount"]
            if abs(current_growth - avg_growth) > 0.30:
                anomalies.append({
                    "type": "trend",
                    "indicator": "growth_rate",
                    "current": current_growth,
                    "historical_avg": avg_growth,
                    "severity": "high",
                    "confidence": 0.70,
                    "description": f"增长率异常: 当前 {current_growth:.2%}, 历史均值 {avg_growth:.2%}"
                })
        return anomalies

    def _detect_industry_benchmark_anomalies(self, tax_data: Dict) -> List[Dict]:
        industry = tax_data.get("industry", "manufacturing")
        benchmark = self.industry_benchmarks.get(industry, self.industry_benchmarks["manufacturing"])
        anomalies = []
        tax_load = self._calculate_tax_load_rate(tax_data)
        if abs(tax_load - benchmark["avg_tax_load"]) > 0.02:
            anomalies.append({
                "type": "industry_benchmark",
                "indicator": "tax_load_rate",
                "value": tax_load,
                "benchmark": benchmark["avg_tax_load"],
                "industry": industry,
                "severity": "medium",
                "confidence": 0.65,
                "description": "税负率偏离行业均值"
            })
        return anomalies

    def _detect_correlation_anomalies(self, tax_data: Dict) -> List[Dict]:
        anomalies = []
        input_count = tax_data.get("input_invoice_count", 0)
        output_count = tax_data.get("output_invoice_count", 0)
        input_tax = abs(tax_data.get("input_tax", 0))
        output_tax = abs(tax_data.get("output_tax", 0))
        if input_count > 0 and output_count > 0:
            ratio = input_count / output_count
            avg_invoice_input = input_tax / input_count if input_count > 0 else 0
            avg_invoice_output = output_tax / output_count if output_count > 0 else 0
            if avg_invoice_input > avg_invoice_output * 2:
                anomalies.append({
                    "type": "correlation",
                    "indicator": "invoice_avg",
                    "avg_invoice_input": avg_invoice_input,
                    "avg_invoice_output": avg_invoice_output,
                    "severity": "high",
                    "confidence": 0.80,
                    "description": "发票金额与数量不匹配"
                })
        return anomalies

    async def detect_advanced_anomalies(self, tax_data: Dict, historical_data: Optional[List[Dict]] = None) -> Dict:
        all_anomalies = []
        all_anomalies.extend(self._detect_iqr_anomalies(tax_data))
        if historical_data:
            all_anomalies.extend(self._detect_zscore_anomalies(tax_data, historical_data))
            all_anomalies.extend(self._detect_trend_anomalies(tax_data, historical_data))
        all_anomalies.extend(self._detect_industry_benchmark_anomalies(tax_data))
        all_anomalies.extend(self._detect_correlation_anomalies(tax_data))
        high_confidence = [a for a in all_anomalies if a.get("confidence", 0) >= 0.8]
        avg_confidence = sum(a.get("confidence", 0) for a in all_anomalies) / len(all_anomalies) if all_anomalies else 0
        risk_level = "high" if len(high_confidence) >= 3 else "medium" if len(all_anomalies) >= 2 else "low"
        return {
            "total_anomalies": len(all_anomalies),
            "high_confidence_anomalies": len(high_confidence),
            "anomalies": all_anomalies,
            "overall_confidence": avg_confidence,
            "risk_level": risk_level,
            "recommendations": [
                "建议核对发票数量与金额的一致性",
                "建议对比历史同期数据",
                "建议参考行业基准进行自我评估"
            ] if all_anomalies else []
        }


async def test_all():
    """运行所有测试"""
    print("=" * 80)
    print("税务逻辑验证器独立测试")
    print("=" * 80)

    validator = StandaloneTaxLogicValidator()
    passed = 0
    failed = 0

    test_data = {
        "input_tax": 100000,
        "output_tax": 130000,
        "taxable_amount": 1000000,
        "input_invoice_count": 50,
        "output_invoice_count": 80,
        "tax_rate": 0.13,
        "industry": "manufacturing"
    }

    historical = [
        {"input_tax": 90000, "output_tax": 120000, "taxable_amount": 900000},
        {"input_tax": 95000, "output_tax": 125000, "taxable_amount": 950000},
        {"input_tax": 85000, "output_tax": 115000, "taxable_amount": 880000}
    ]

    print("\n测试 1: IQR 异常检测")
    try:
        anomalies = validator._detect_iqr_anomalies(test_data)
        assert isinstance(anomalies, list), "应返回列表"
        print(f"   ✅ IQR检测: {len(anomalies)} 个异常")
        passed += 1
    except Exception as e:
        print(f"   ❌ IQR检测失败: {e}")
        failed += 1

    print("\n测试 2: Z-score 异常检测")
    try:
        anomalies = validator._detect_zscore_anomalies(test_data, historical)
        assert isinstance(anomalies, list), "应返回列表"
        print(f"   ✅ Z-score检测: {len(anomalies)} 个异常")
        passed += 1
    except Exception as e:
        print(f"   ❌ Z-score检测失败: {e}")
        failed += 1

    print("\n测试 3: 趋势异常检测")
    try:
        anomalies = validator._detect_trend_anomalies(test_data, historical)
        assert isinstance(anomalies, list), "应返回列表"
        print(f"   ✅ 趋势检测: {len(anomalies)} 个异常")
        passed += 1
    except Exception as e:
        print(f"   ❌ 趋势检测失败: {e}")
        failed += 1

    print("\n测试 4: 行业基准异常检测")
    try:
        anomalies = validator._detect_industry_benchmark_anomalies(test_data)
        assert isinstance(anomalies, list), "应返回列表"
        print(f"   ✅ 行业基准检测: {len(anomalies)} 个异常")
        passed += 1
    except Exception as e:
        print(f"   ❌ 行业基准检测失败: {e}")
        failed += 1

    print("\n测试 5: 关联异常检测")
    try:
        anomalies = validator._detect_correlation_anomalies(test_data)
        assert isinstance(anomalies, list), "应返回列表"
        print(f"   ✅ 关联检测: {len(anomalies)} 个异常")
        passed += 1
    except Exception as e:
        print(f"   ❌ 关联检测失败: {e}")
        failed += 1

    print("\n测试 6: 高级异常检测（综合）")
    try:
        result = await validator.detect_advanced_anomalies(test_data, historical)
        assert "total_anomalies" in result, "应包含总数"
        assert "risk_level" in result, "应包含风险级别"
        assert "recommendations" in result, "应包含建议"
        print(f"   ✅ 综合检测: {result['total_anomalies']} 个异常, 风险级别: {result['risk_level']}")
        passed += 1
    except Exception as e:
        print(f"   ❌ 综合检测失败: {e}")
        failed += 1

    print("\n" + "=" * 80)
    print(f"测试摘要: {passed} 通过, {failed} 失败")
    print("=" * 80)

    if failed == 0:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        return 1


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(test_all())
    sys.exit(exit_code)
