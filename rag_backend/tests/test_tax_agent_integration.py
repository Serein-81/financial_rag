"""
税务Agent集成测试
测试增强后的税务逻辑验证和异常检测功能

Phase 3 - Task 3.5: 集成测试：税务逻辑验证和异常检测
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import uuid

sys.path.insert(0, str(Path(__file__).parent))

from app.multi_agent_system.tax_logic_validator import TaxLogicValidator
from app.multi_agent_system.agents.tax_specialist import (
    TaxSpecialist,
    TaxAnalysisResult,
    TaxType,
    RiskLevelStr,
    TaxIssueCategory,
    VATDetail,
    VATTransaction,
    TaxIssue
)


class TaxAgentIntegrationTester:
    """税务Agent集成测试器"""
    
    def __init__(self):
        self.validator = TaxLogicValidator()
        self.tax_specialist = TaxSpecialist()
        self.results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "details": []
        }
    
    def log_test(self, name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        self.results["total"] += 1
        if passed:
            self.results["passed"] += 1
            status = "✅ PASS"
        else:
            self.results["failed"] += 1
            status = "❌ FAIL"
        
        self.results["details"].append({
            "name": name,
            "passed": passed,
            "message": message
        })
        
        print(f"{status}: {name}")
        if message:
            print(f"   {message}")
    
    async def test_vat_validation(self):
        """测试增值税验证逻辑"""
        print("\n" + "=" * 80)
        print("测试 1: 增值税验证逻辑")
        print("=" * 80)
        
        test_cases = [
            {
                "name": "正常增值税数据",
                "data": {
                    "tax_type": "vat",
                    "input_tax": 100000,
                    "output_tax": 130000,
                    "taxable_amount": 1000000,
                    "input_invoice_count": 50,
                    "output_invoice_count": 80
                },
                "expected_valid": True
            },
            {
                "name": "进项大于销项（异常）",
                "data": {
                    "tax_type": "vat",
                    "input_tax": 200000,
                    "output_tax": 50000,
                    "taxable_amount": 500000,
                    "input_invoice_count": 100,
                    "output_invoice_count": 30
                },
                "expected_valid": False
            },
            {
                "name": "税负率异常",
                "data": {
                    "tax_type": "vat",
                    "input_tax": 5000,
                    "output_tax": 3000,
                    "taxable_amount": 1000000,
                    "input_invoice_count": 10,
                    "output_invoice_count": 20
                },
                "expected_valid": False
            }
        ]
        
        for case in test_cases:
            try:
                result = await self.validator.validate_tax_logic(case["data"])
                
                is_valid = result["is_valid"] if isinstance(result, dict) else result
                matches_expectation = is_valid == case["expected_valid"]
                
                self.log_test(
                    case["name"],
                    matches_expectation,
                    f"结果: {is_valid}, 期望: {case['expected_valid']}"
                )
            except Exception as e:
                self.log_test(case["name"], False, f"异常: {str(e)}")
    
    async def test_advanced_anomaly_detection(self):
        """测试高级异常检测"""
        print("\n" + "=" * 80)
        print("测试 2: 高级异常检测算法")
        print("=" * 80)
        
        test_data = {
            "input_tax": 100000,
            "output_tax": 130000,
            "taxable_amount": 1000000,
            "input_invoice_count": 50,
            "output_invoice_count": 80,
            "tax_rate": 0.13
        }
        
        historical_data = [
            {
                "input_tax": 90000,
                "output_tax": 120000,
                "taxable_amount": 900000,
                "input_invoice_count": 45,
                "output_invoice_count": 75
            },
            {
                "input_tax": 95000,
                "output_tax": 125000,
                "taxable_amount": 950000,
                "input_invoice_count": 48,
                "output_invoice_count": 78
            }
        ]
        
        try:
            result = await self.validator.detect_advanced_anomalies(
                tax_data=test_data,
                historical_data=historical_data
            )
            
            has_anomaly_count = "total_anomalies" in result
            has_risk_level = "risk_level" in result
            has_recommendations = "recommendations" in result
            
            self.log_test(
                "高级异常检测返回结构",
                has_anomaly_count and has_risk_level,
                f"检测到 {result.get('total_anomalies', 0)} 个异常"
            )
            
            self.log_test(
                "异常检测建议",
                has_recommendations,
                f"建议数: {len(result.get('recommendations', []))}"
            )
            
            print(f"\n   异常检测详情:")
            print(f"   - 总异常数: {result.get('total_anomalies', 0)}")
            print(f"   - 高置信度异常: {result.get('high_confidence_anomalies', 0)}")
            print(f"   - 风险级别: {result.get('risk_level', 'unknown')}")
            
        except Exception as e:
            self.log_test("高级异常检测", False, f"异常: {str(e)}")
    
    async def test_structured_output(self):
        """测试结构化输出"""
        print("\n" + "=" * 80)
        print("测试 3: TaxSpecialist结构化输出")
        print("=" * 80)
        
        test_state = {
            "report_id": f"test_{uuid.uuid4().hex[:8]}",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "document_content": """
            增值税纳税申报表
            本期销项税额：130,000元
            本期进项税额：100,000元
            销项税额明细：
            - 专用发票：100,000元
            - 普通发票：30,000元
            """,
            "extracted_entities": {
                "input_tax": 100000,
                "output_tax": 130000,
                "input_invoice_count": 50,
                "output_invoice_count": 80
            },
            "uncertain_fields": ["tax_rate", "business_type"]
        }
        
        try:
            result = await self.tax_specialist.analyze_with_structured_output(
                state=test_state,
                llm_adapter=None
            )
            
            has_required_fields = all(
                k in result for k in ["report_id", "tax_types_analyzed", "issues_found"]
            )
            
            self.log_test(
                "结构化输出包含必要字段",
                has_required_fields,
                f"字段: {list(result.keys())[:5]}..."
            )
            
            if isinstance(result, dict):
                issues_count = len(result.get("issues_found", []))
                risk_score = result.get("risk_score", 0)
            else:
                issues_count = len(result.issues_found) if hasattr(result, "issues_found") else 0
                risk_score = result.risk_score if hasattr(result, "risk_score") else 0
            
            self.log_test(
                "结构化输出风险评分",
                0 <= risk_score <= 100,
                f"风险评分: {risk_score}"
            )
            
        except Exception as e:
            self.log_test("结构化输出", False, f"异常: {str(e)}")
    
    async def test_iqr_anomaly_detection(self):
        """测试IQR异常检测"""
        print("\n" + "=" * 80)
        print("测试 4: IQR四分位距异常检测")
        print("=" * 80)
        
        test_data = {
            "input_tax": 100000,
            "output_tax": 130000,
            "taxable_amount": 1000000
        }
        
        try:
            anomalies = self.validator._detect_iqr_anomalies(test_data)
            
            is_list = isinstance(anomalies, list)
            self.log_test(
                "IQR检测返回列表",
                is_list,
                f"检测到 {len(anomalies)} 个异常"
            )
            
            if is_list and anomalies:
                first = anomalies[0]
                has_required_fields = all(k in first for k in ["type", "severity", "confidence"])
                self.log_test(
                    "IQR异常包含必要字段",
                    has_required_fields,
                    f"类型: {first.get('type')}, 严重程度: {first.get('severity')}"
                )
                
        except Exception as e:
            self.log_test("IQR异常检测", False, f"异常: {str(e)}")
    
    async def test_zscore_anomaly_detection(self):
        """测试Z-score异常检测"""
        print("\n" + "=" * 80)
        print("测试 5: Z-score标准化异常检测")
        print("=" * 80)
        
        test_data = {
            "input_tax": 100000,
            "output_tax": 130000,
            "taxable_amount": 1000000,
            "input_invoice_count": 50,
            "output_invoice_count": 80
        }
        
        historical = [
            {"input_tax": 90000, "output_tax": 120000, "taxable_amount": 900000},
            {"input_tax": 95000, "output_tax": 125000, "taxable_amount": 950000},
            {"input_tax": 105000, "output_tax": 135000, "taxable_amount": 1050000}
        ]
        
        try:
            anomalies = self.validator._detect_zscore_anomalies(test_data, historical)
            
            self.log_test(
                "Z-score检测返回列表",
                isinstance(anomalies, list),
                f"检测到 {len(anomalies)} 个异常"
            )
            
        except Exception as e:
            self.log_test("Z-score异常检测", False, f"异常: {str(e)}")
    
    async def test_trend_anomaly_detection(self):
        """测试趋势异常检测"""
        print("\n" + "=" * 80)
        print("测试 6: 趋势异常检测")
        print("=" * 80)
        
        test_data = {
            "input_tax": 100000,
            "output_tax": 130000,
            "taxable_amount": 1000000
        }
        
        historical = [
            {"input_tax": 80000, "output_tax": 100000, "taxable_amount": 800000},
            {"input_tax": 85000, "output_tax": 110000, "taxable_amount": 850000},
            {"input_tax": 90000, "output_tax": 120000, "taxable_amount": 900000}
        ]
        
        try:
            anomalies = self.validator._detect_trend_anomalies(test_data, historical)
            
            self.log_test(
                "趋势检测返回列表",
                isinstance(anomalies, list),
                f"检测到 {len(anomalies)} 个异常"
            )
            
        except Exception as e:
            self.log_test("趋势异常检测", False, f"异常: {str(e)}")
    
    async def test_industry_benchmark_anomaly_detection(self):
        """测试行业基准异常检测"""
        print("\n" + "=" * 80)
        print("测试 7: 行业基准异常检测")
        print("=" * 80)
        
        test_data = {
            "input_tax": 100000,
            "output_tax": 130000,
            "taxable_amount": 1000000,
            "industry": "manufacturing"
        }
        
        try:
            anomalies = self.validator._detect_industry_benchmark_anomalies(test_data)
            
            self.log_test(
                "行业基准检测返回列表",
                isinstance(anomalies, list),
                f"检测到 {len(anomalies)} 个异常"
            )
            
        except Exception as e:
            self.log_test("行业基准异常检测", False, f"异常: {str(e)}")
    
    async def test_correlation_anomaly_detection(self):
        """测试关联异常检测"""
        print("\n" + "=" * 80)
        print("测试 8: 多指标关联异常检测")
        print("=" * 80)
        
        test_data = {
            "input_tax": 100000,
            "output_tax": 130000,
            "taxable_amount": 1000000,
            "input_invoice_count": 50,
            "output_invoice_count": 80,
            "tax_rate": 0.13
        }
        
        try:
            anomalies = self.validator._detect_correlation_anomalies(test_data)
            
            self.log_test(
                "关联检测返回列表",
                isinstance(anomalies, list),
                f"检测到 {len(anomalies)} 个异常"
            )
            
        except Exception as e:
            self.log_test("关联异常检测", False, f"异常: {str(e)}")
    
    async def test_tax_issue_categories(self):
        """测试税务问题分类"""
        print("\n" + "=" * 80)
        print("测试 9: 税务问题分类")
        print("=" * 80)
        
        test_cases = [
            ("进项税异常偏高", TaxIssueCategory.INPUT_TAX_ANOMALY),
            ("销项税偏低", TaxIssueCategory.OUTPUT_TAX_LOW),
            ("发票数量不匹配", TaxIssueCategory.INVOICE_MISMATCH),
            ("税负率异常", TaxIssueCategory.TAX_LOAD_ANOMALY)
        ]
        
        all_valid = True
        for desc, expected_category in test_cases:
            try:
                category = TaxIssueCategory(desc)
                is_match = category == expected_category
                all_valid = all_valid and is_match
                self.log_test(f"分类: {desc}", is_match)
            except ValueError:
                self.log_test(f"分类: {desc}", False, "枚举值不匹配")
    
    async def test_risk_level_scoring(self):
        """测试风险等级评分"""
        print("\n" + "=" * 80)
        print("测试 10: 风险等级评分")
        print("=" * 80)
        
        test_cases = [
            ("低风险", 25),
            ("中风险", 55),
            ("高风险", 85)
        ]
        
        for desc, score in test_cases:
            try:
                level = RiskLevelStr.from_score(score)
                self.log_test(
                    f"风险评分 {score} -> {desc}",
                    level.value == desc,
                    f"实际: {level.value}"
                )
            except Exception as e:
                self.log_test(f"风险评分 {score}", False, f"异常: {str(e)}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 80)
        print("税务Agent集成测试套件")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        await self.test_vat_validation()
        await self.test_advanced_anomaly_detection()
        await self.test_structured_output()
        await self.test_iqr_anomaly_detection()
        await self.test_zscore_anomaly_detection()
        await self.test_trend_anomaly_detection()
        await self.test_industry_benchmark_anomaly_detection()
        await self.test_correlation_anomaly_detection()
        await self.test_tax_issue_categories()
        await self.test_risk_level_scoring()
        
        self.print_summary()
        return self.results
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("测试摘要")
        print("=" * 80)
        print(f"总测试数: {self.results['total']}")
        print(f"通过: {self.results['passed']} ✅")
        print(f"失败: {self.results['failed']} ❌")
        
        if self.results["total"] > 0:
            pass_rate = self.results["passed"] / self.results["total"] * 100
            print(f"通过率: {pass_rate:.1f}%")
        
        if self.results["failed"] > 0:
            print("\n失败详情:")
            for detail in self.results["details"]:
                if not detail["passed"]:
                    print(f"  - {detail['name']}: {detail['message']}")


async def main():
    """主函数"""
    tester = TaxAgentIntegrationTester()
    results = await tester.run_all_tests()
    
    if results["failed"] > 0:
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
