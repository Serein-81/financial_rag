"""
编排器查询处理测试

测试编排器处理不同类型查询的能力和输出质量
"""

import re
from typing import Dict, List, Any


class QueryHandlerTester:
    """查询处理器测试器"""
    
    @staticmethod
    def analyze_query_type(query: str) -> Dict[str, bool]:
        """分析查询类型"""
        analysis = {
            "is_financial": False,
            "is_tax": False,
            "is_legal": False,
            "is_comprehensive": False,
            "is_analysis": False,
            "is_recommendation": False,
            "is_risk": False,
            "is_optimization": False
        }
        
        # 财务相关查询
        financial_keywords = ["财务", "营收", "利润", "成本", "现金流", "预算", "投资"]
        analysis["is_financial"] = any(kw in query for kw in financial_keywords)
        
        # 税务相关查询
        tax_keywords = ["税务", "税收", "增值税", "所得税", "纳税", "税收优惠", "税务筹划"]
        analysis["is_tax"] = any(kw in query for kw in tax_keywords)
        
        # 法律相关查询
        legal_keywords = ["法律", "合规", "合同", "法务", "风险", "诉讼", "知识产权"]
        analysis["is_legal"] = any(kw in query for kw in legal_keywords)
        
        # 综合分析查询
        comprehensive_patterns = ["综合", "全面", "整体", "多维度", "协同"]
        analysis["is_comprehensive"] = any(p in query for p in comprehensive_patterns)
        
        # 分析类查询
        analysis_keywords = ["分析", "评估", "审查", "研究", "诊断"]
        analysis["is_analysis"] = any(kw in query for kw in analysis_keywords)
        
        # 建议类查询
        recommendation_keywords = ["建议", "方案", "措施", "策略", "优化", "改进"]
        analysis["is_recommendation"] = any(kw in query for kw in recommendation_keywords)
        
        # 风险类查询
        risk_keywords = ["风险", "问题", "挑战", "困难", "障碍"]
        analysis["is_risk"] = any(kw in query for kw in risk_keywords)
        
        # 优化类查询
        optimization_keywords = ["优化", "提升", "改善", "增强", "提高"]
        analysis["is_optimization"] = any(kw in query for kw in optimization_keywords)
        
        return analysis
    
    @staticmethod
    def validate_response_adequacy(response: str, query_analysis: Dict[str, bool]) -> Dict[str, Any]:
        """验证响应充分性"""
        validation = {
            "covers_financial": False,
            "covers_tax": False,
            "covers_legal": False,
            "has_analysis": False,
            "has_recommendations": False,
            "has_risk_assessment": False,
            "has_optimization_suggestions": False,
            "adequacy_score": 0,
            "missing_elements": []
        }
        
        # 检查财务覆盖
        financial_indicators = ["财务", "营收", "利润", "成本", "现金流"]
        validation["covers_financial"] = any(ind in response for ind in financial_indicators)
        
        # 检查税务覆盖
        tax_indicators = ["税务", "税收", "增值税", "所得税", "纳税"]
        validation["covers_tax"] = any(ind in response for ind in tax_indicators)
        
        # 检查法律覆盖
        legal_indicators = ["法律", "合规", "合同", "法务", "风险"]
        validation["covers_legal"] = any(ind in response for ind in legal_indicators)
        
        # 检查分析内容
        analysis_indicators = ["分析", "评估", "发现", "结果", "数据"]
        validation["has_analysis"] = any(ind in response for ind in analysis_indicators)
        
        # 检查建议内容
        recommendation_indicators = ["建议", "措施", "方案", "策略", "行动计划"]
        validation["has_recommendations"] = any(ind in response for ind in recommendation_indicators)
        
        # 检查风险评估
        risk_indicators = ["风险", "问题", "挑战", "注意事项", "预警"]
        validation["has_risk_assessment"] = any(ind in response for ind in risk_indicators)
        
        # 检查优化建议
        optimization_indicators = ["优化", "提升", "改善", "增强", "提高效率"]
        validation["has_optimization_suggestions"] = any(ind in response for ind in optimization_indicators)
        
        # 计算充分性分数
        required_elements = []
        if query_analysis["is_financial"]:
            required_elements.append("covers_financial")
        if query_analysis["is_tax"]:
            required_elements.append("covers_tax")
        if query_analysis["is_legal"]:
            required_elements.append("covers_legal")
        if query_analysis["is_analysis"]:
            required_elements.append("has_analysis")
        if query_analysis["is_recommendation"]:
            required_elements.append("has_recommendations")
        if query_analysis["is_risk"]:
            required_elements.append("has_risk_assessment")
        if query_analysis["is_optimization"]:
            required_elements.append("has_optimization_suggestions")
        
        if required_elements:
            covered_elements = sum(1 for elem in required_elements if validation[elem])
            validation["adequacy_score"] = covered_elements / len(required_elements)
            
            # 记录缺失元素
            for elem in required_elements:
                if not validation[elem]:
                    elem_name = elem.replace("_", " ")
                    validation["missing_elements"].append(elem_name)
        
        return validation
    
    @staticmethod
    def generate_mock_response(query: str, query_analysis: Dict[str, bool]) -> str:
        """生成模拟响应（用于测试）"""
        response_parts = []
        
        # 添加标题
        if query_analysis["is_comprehensive"]:
            response_parts.append("多智能体协作分析报告")
        else:
            response_parts.append("智能体分析报告")
        
        response_parts.append("=" * 40)
        
        # 添加引言
        intro = f"根据您关于\"{query}\"的查询"
        if query_analysis["is_comprehensive"]:
            intro += "，财务、税务、法务专家协同分析如下："
        elif query_analysis["is_financial"]:
            intro += "，财务专家分析如下："
        elif query_analysis["is_tax"]:
            intro += "，税务专家分析如下："
        elif query_analysis["is_legal"]:
            intro += "，法务专家分析如下："
        else:
            intro += "，分析如下："
        
        response_parts.append(intro)
        response_parts.append("")
        
        # 添加分析部分
        if query_analysis["is_analysis"]:
            response_parts.append("一、分析结果")
            if query_analysis["is_financial"]:
                response_parts.append("1. 财务状况")
                response_parts.append("   • 营收状况：稳定增长")
                response_parts.append("   • 成本结构：有待优化")
                response_parts.append("   • 现金流：充足")
            
            if query_analysis["is_tax"]:
                response_parts.append("2. 税务情况")
                response_parts.append("   • 合规性：良好")
                response_parts.append("   • 优化空间：存在")
                response_parts.append("   • 风险点：需关注")
            
            if query_analysis["is_legal"]:
                response_parts.append("3. 法律合规")
                response_parts.append("   • 合同管理：需加强")
                response_parts.append("   • 风险识别：已完成")
                response_parts.append("   • 合规培训：建议开展")
            
            response_parts.append("")
        
        # 添加风险评估
        if query_analysis["is_risk"]:
            response_parts.append("二、风险评估")
            response_parts.append("1. 主要风险点")
            response_parts.append("   • 运营风险：中等")
            response_parts.append("   • 合规风险：低")
            response_parts.append("   • 市场风险：需监控")
            response_parts.append("")
        
        # 添加建议部分
        if query_analysis["is_recommendation"] or query_analysis["is_optimization"]:
            response_parts.append("三、建议措施")
            
            if query_analysis["is_optimization"]:
                response_parts.append("1. 优化建议")
                response_parts.append("   • 流程优化：简化审批流程")
                response_parts.append("   • 成本优化：降低运营成本")
                response_parts.append("   • 效率优化：提升工作效率")
            
            if query_analysis["is_recommendation"]:
                response_parts.append("2. 实施建议")
                response_parts.append("   • 短期行动：立即执行")
                response_parts.append("   • 中期规划：3-6个月")
                response_parts.append("   • 长期战略：1年以上")
            
            response_parts.append("")
        
        # 添加结论
        response_parts.append("四、总结")
        if query_analysis["is_comprehensive"]:
            response_parts.append("综合来看，企业整体状况良好，建议持续优化改进。")
        else:
            response_parts.append("分析完成，建议根据具体情况实施相应措施。")
        
        return "\n".join(response_parts)


def test_query_type_analysis():
    """测试查询类型分析"""
    print("=" * 80)
    print("测试查询类型分析")
    print("=" * 80)
    
    test_queries = [
        "分析企业财务状况",
        "评估税务风险和优化机会",
        "审查法律合规性和合同风险",
        "综合分析企业财务、税务、法律状况",
        "提供财务优化建议",
        "识别企业主要风险点",
        "制定全面的改进方案"
    ]
    
    tester = QueryHandlerTester()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n查询 {i}: {query}")
        print("-" * 40)
        
        analysis = tester.analyze_query_type(query)
        
        print("查询类型分析:")
        for key, value in analysis.items():
            if value:
                print(f"  ✅ {key.replace('_', ' ')}")
        
        print("-" * 40)
    
    print("\n" + "=" * 80)
    print("查询类型分析测试完成")
    print("=" * 80)


def test_response_adequacy():
    """测试响应充分性"""
    print("\n" + "=" * 80)
    print("测试响应充分性")
    print("=" * 80)
    
    test_cases = [
        {
            "query": "分析企业财务状况",
            "response": """财务分析报告

根据您关于"分析企业财务状况"的查询，财务专家分析如下：

一、财务状况分析
1. 营收状况
   • 年度营收：1.2亿元
   • 同比增长：15%

2. 成本结构
   • 人工成本：28%
   • 原材料成本：45%

3. 现金流
   • 现金充足率：120%
   • 应收账款周转：65天

二、建议措施
• 优化成本结构
• 加强应收账款管理

总结：财务状况总体健康，建议关注成本优化。"""
        },
        {
            "query": "综合评估企业风险",
            "response": """企业风险评估报告

基于多智能体系统分析，企业风险评估如下：

一、风险识别
1. 财务风险
   • 应收账款周转较慢
   • 存货管理有待优化

2. 法律风险
   • 合同管理合规率85%
   • 劳动法合规需改进

二、风险应对
• 建立风险预警机制
• 完善内部控制制度

总结：风险总体可控，建议加强风险管理。"""
        }
    ]
    
    tester = QueryHandlerTester()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}")
        print(f"查询: {test_case['query']}")
        print("-" * 40)
        
        # 分析查询类型
        query_analysis = tester.analyze_query_type(test_case['query'])
        
        # 验证响应充分性
        adequacy = tester.validate_response_adequacy(test_case['response'], query_analysis)
        
        print(f"充分性分数: {adequacy['adequacy_score']:.2f}")
        
        if adequacy['adequacy_score'] >= 0.8:
            print("✅ 响应充分性良好")
        elif adequacy['adequacy_score'] >= 0.6:
            print("⚠️ 响应基本充分")
        else:
            print("❌ 响应不够充分")
        
        if adequacy['missing_elements']:
            print(f"缺失元素: {', '.join(adequacy['missing_elements'])}")
        
        print("-" * 40)
    
    print("\n" + "=" * 80)
    print("响应充分性测试完成")
    print("=" * 80)


def test_mock_response_generation():
    """测试模拟响应生成"""
    print("\n" + "=" * 80)
    print("测试模拟响应生成")
    print("=" * 80)
    
    test_queries = [
        "分析企业财务状况",
        "评估税务优化机会",
        "审查法律合规风险",
        "综合分析并提出改进建议"
    ]
    
    tester = QueryHandlerTester()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n测试查询 {i}: {query}")
        print("-" * 40)
        
        # 分析查询类型
        query_analysis = tester.analyze_query_type(query)
        
        # 生成模拟响应
        mock_response = tester.generate_mock_response(query, query_analysis)
        
        print("生成的响应:")
        print(mock_response[:200] + "..." if len(mock_response) > 200 else mock_response)
        
        # 验证响应充分性
        adequacy = tester.validate_response_adequacy(mock_response, query_analysis)
        print(f"\n充分性分数: {adequacy['adequacy_score']:.2f}")
        
        print("-" * 40)
    
    print("\n" + "=" * 80)
    print("模拟响应生成测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_query_type_analysis()
    test_response_adequacy()
    test_mock_response_generation()
    
    print("\n" + "=" * 80)
    print("所有查询处理测试完成")
    print("=" * 80)