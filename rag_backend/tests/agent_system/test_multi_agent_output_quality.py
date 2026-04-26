"""
多智能体协作输出质量测试

测试多智能体协作的输出质量和格式一致性
"""

import re
import json
from typing import Dict, List, Any


class OutputQualityValidator:
    """输出质量验证器"""
    
    @staticmethod
    def validate_structure(response: str) -> Dict[str, Any]:
        """验证响应结构"""
        result = {
            "has_introduction": False,
            "has_analysis": False,
            "has_recommendations": False,
            "has_conclusion": False,
            "is_structured": False,
            "word_count": len(response.split()),
            "paragraph_count": len([p for p in response.split('\n\n') if p.strip()]),
            "issues": []
        }
        
        # 检查结构元素
        intro_patterns = [r'^(根据|基于|针对|关于)', r'.*分析如下.*', r'.*报告如下.*']
        result["has_introduction"] = any(re.search(p, response[:200]) for p in intro_patterns)
        
        analysis_keywords = ['分析', '评估', '发现', '结果', '数据']
        result["has_analysis"] = any(kw in response for kw in analysis_keywords)
        
        rec_keywords = ['建议', '措施', '方案', '策略']
        result["has_recommendations"] = any(kw in response for kw in rec_keywords)
        
        conclusion_patterns = [r'综上所述', r'总之', r'总而言之', r'总结']
        result["has_conclusion"] = any(p in response[-200:] for p in conclusion_patterns)
        
        # 检查是否结构化
        structure_score = sum([
            result["has_introduction"],
            result["has_analysis"],
            result["has_recommendations"],
            result["has_conclusion"]
        ])
        result["is_structured"] = structure_score >= 3
        
        # 收集问题
        if not result["has_introduction"]:
            result["issues"].append("缺少引言")
        if not result["has_analysis"]:
            result["issues"].append("缺少分析内容")
        if not result["has_recommendations"]:
            result["issues"].append("缺少建议措施")
        if not result["has_conclusion"]:
            result["issues"].append("缺少结论")
        if result["word_count"] < 100:
            result["issues"].append("内容过短")
            
        return result
    
    @staticmethod
    def validate_format(response: str) -> Dict[str, Any]:
        """验证响应格式"""
        result = {
            "has_headings": False,
            "has_lists": False,
            "has_data": False,
            "has_expert_attribution": False,
            "format_score": 0,
            "issues": []
        }
        
        # 检查标题
        heading_patterns = [r'^[一二三四五六七八九十]、', r'^\d+\.', r'^[•\-*]']
        lines = response.split('\n')
        heading_lines = sum(1 for line in lines if any(re.match(p, line.strip()) for p in heading_patterns))
        result["has_headings"] = heading_lines >= 2
        
        # 检查列表
        list_patterns = [r'[•\-*]\s', r'\d+\.\s']
        result["has_lists"] = any(re.search(p, response) for p in list_patterns)
        
        # 检查数据
        data_patterns = [r'\d+%', r'\d+\.\d+', r'同比增长', r'环比增长']
        result["has_data"] = any(re.search(p, response) for p in data_patterns)
        
        # 检查专家归属
        expert_patterns = ['财务专家', '税务专家', '法务专家', '（财务）', '（税务）', '（法务）']
        result["has_expert_attribution"] = any(p in response for p in expert_patterns)
        
        # 计算格式分数
        format_score = sum([
            result["has_headings"],
            result["has_lists"],
            result["has_data"],
            result["has_expert_attribution"]
        ])
        result["format_score"] = format_score
        
        # 收集问题
        if not result["has_headings"]:
            result["issues"].append("缺少标题结构")
        if not result["has_lists"]:
            result["issues"].append("缺少列表格式")
        if not result["has_data"]:
            result["issues"].append("缺少具体数据")
        if not result["has_expert_attribution"]:
            result["issues"].append("缺少专家归属")
            
        return result
    
    @staticmethod
    def validate_content(response: str, query: str) -> Dict[str, Any]:
        """验证内容质量"""
        result = {
            "relevance_score": 0,
            "completeness_score": 0,
            "clarity_score": 0,
            "overall_score": 0,
            "issues": []
        }
        
        # 相关性评分
        query_words = set(re.findall(r'\w+', query.lower()))
        response_words = set(re.findall(r'\w+', response.lower()))
        common_words = query_words.intersection(response_words)
        
        if query_words:
            result["relevance_score"] = len(common_words) / len(query_words)
        else:
            result["relevance_score"] = 1.0
        
        # 完整性评分
        word_count = len(response.split())
        if word_count >= 300:
            completeness = 1.0
        elif word_count >= 200:
            completeness = 0.8
        elif word_count >= 100:
            completeness = 0.6
        else:
            completeness = 0.4
            
        structure_result = OutputQualityValidator.validate_structure(response)
        structure_completeness = 0.4 if structure_result["is_structured"] else 0.1
        
        result["completeness_score"] = (completeness + structure_completeness) / 2
        
        # 清晰度评分
        sentences = re.split(r'[.!?]+', response)
        avg_sentence_len = sum(len(s.split()) for s in sentences if s.strip()) / max(1, len(sentences))
        
        if avg_sentence_len <= 25:
            clarity = 1.0
        elif avg_sentence_len <= 35:
            clarity = 0.7
        elif avg_sentence_len <= 45:
            clarity = 0.5
        else:
            clarity = 0.3
            
        paragraphs = [p for p in response.split('\n\n') if p.strip()]
        paragraph_clarity = 0.5 if len(paragraphs) >= 3 else 0.2
        
        result["clarity_score"] = (clarity + paragraph_clarity) / 2
        
        # 总体评分
        weights = {"relevance": 0.4, "completeness": 0.3, "clarity": 0.3}
        result["overall_score"] = (
            result["relevance_score"] * weights["relevance"] +
            result["completeness_score"] * weights["completeness"] +
            result["clarity_score"] * weights["clarity"]
        )
        
        # 收集问题
        if result["relevance_score"] < 0.5:
            result["issues"].append("与查询相关性不足")
        if result["completeness_score"] < 0.5:
            result["issues"].append("内容不够完整")
        if result["clarity_score"] < 0.5:
            result["issues"].append("表达不够清晰")
            
        return result


def test_orchestrator_output_format():
    """测试编排器输出格式"""
    print("=" * 80)
    print("测试编排器输出格式")
    print("=" * 80)
    
    test_responses = [
        """多智能体协作分析报告

根据您关于"分析企业财务状况"的查询，财务专家、税务专家、法务专家协同分析如下：

一、财务分析（财务专家）
1. 营收状况
   • 年度营收：1.2亿元，同比增长15%
   • 毛利率：32%，同比提升2个百分点
   • 净利润：960万元，净利润率8%

2. 成本结构
   • 人工成本占比：28%
   • 原材料成本占比：45%
   • 运营费用占比：18%

3. 现金流分析
   • 经营活动现金流：正流入
   • 投资活动现金流：负流出（设备更新）
   • 融资活动现金流：稳定

4. 建议措施
   • 优化供应链管理，降低原材料成本5-8%
   • 加强预算控制，提高资金使用效率
   • 建立财务预警机制，监控关键指标

二、税务分析（税务专家）
1. 合规情况
   • 增值税申报及时率：100%
   • 企业所得税准确率：98%
   • 税务稽查历史：无重大违规

2. 优化机会
   • 研发费用加计扣除：预计节税45万元
   • 高新技术企业认定：符合条件，可享受15%税率
   • 固定资产加速折旧：可优化现金流

3. 风险提示
   • 关联交易定价需文档支持
   • 跨境业务需关注税收协定适用
   • 税务政策变化需及时跟进

三、法务分析（法务专家）
1. 合规评估
   • 合同管理合规率：85%
   • 劳动法合规：需改进加班费计算
   • 知识产权保护：3项专利需续费

2. 风险识别
   • 合同风险：标准合同使用率70%
   • 劳动风险：员工手册需更新
   • 数据安全：GDPR合规待完善

四、综合建议
1. 短期行动（1-3个月）
   • 启动应收账款专项清理
   • 申请研发费用加计扣除
   • 完成专利续费工作

2. 中期规划（3-12个月）
   • 优化供应链成本结构
   • 申请高新技术企业认定
   • 建立全面合规管理体系

3. 长期战略（1-3年）
   • 数字化转型提升运营效率
   • 国际化业务税务筹划
   • 构建企业风险预警系统

五、预期效益
• 财务：预计提升净利润率1-2个百分点
• 税务：年度节税约60-80万元
• 法律：降低合规风险30%

总结：企业财务状况总体健康，建议关注成本优化、税务筹划和法律合规。建议成立跨部门工作小组，定期跟踪改进措施执行情况。""",
        
        """企业风险评估报告

基于多智能体系统分析，企业主要风险如下：

🔍 风险识别
1. 财务风险
   - 应收账款周转天数较长（65天，行业平均45天）
   - 存货周转率有待提升（3.2次，目标4.5次）
   - 资产负债率偏高（65%，警戒线70%）
   - 现金流季节性波动较大

2. 税务风险
   - 关联交易定价需文档支持
   - 跨境业务税收协定适用
   - 税收优惠政策利用不足
   - 税务合规培训需加强

3. 法律风险
   - 合同管理合规率85%，需提升至95%
   - 劳动法合规存在改进空间
   - 知识产权保护体系不完善
   - 数据隐私合规需关注

4. 运营风险
   - 供应链依赖度较高（单一供应商占比40%）
   - 技术更新迭代速度较慢
   - 人才流失率偏高（年度15%）
   - 市场竞争加剧

💡 风险应对建议
• 建立风险预警机制：设置关键风险指标阈值
• 完善内部控制制度：加强审计和监督
• 加强合规培训：定期开展法律法规培训
• 优化供应链管理：建立多元化供应商体系
• 提升技术能力：加大研发投入
• 改善人才管理：优化薪酬福利体系

📊 预期效果
实施建议后，预计可降低整体风险30%，提升运营效率15%，年度节约成本约200万元，提高企业抗风险能力和市场竞争力。

⚠️ 注意事项
1. 建议成立风险管理委员会
2. 定期进行风险评估和审计
3. 建立风险应对预案
4. 加强跨部门协作

本报告由财务专家、税务专家、法务专家协同分析完成，数据基于企业实际情况和行业标准对比得出。"""
    ]
    
    validator = OutputQualityValidator()
    
    for i, response in enumerate(test_responses, 1):
        print(f"\n测试响应 {i}:")
        print("-" * 40)
        
        # 验证结构
        structure = validator.validate_structure(response)
        print(f"结构验证:")
        print(f"  结构化: {structure['is_structured']}")
        print(f"  字数: {structure['word_count']}")
        print(f"  段落数: {structure['paragraph_count']}")
        if structure['issues']:
            print(f"  问题: {', '.join(structure['issues'])}")
        
        # 验证格式
        format_result = validator.validate_format(response)
        print(f"格式验证:")
        print(f"  格式分数: {format_result['format_score']}/4")
        print(f"  有标题: {format_result['has_headings']}")
        print(f"  有列表: {format_result['has_lists']}")
        print(f"  有数据: {format_result['has_data']}")
        print(f"  有专家归属: {format_result['has_expert_attribution']}")
        if format_result['issues']:
            print(f"  问题: {', '.join(format_result['issues'])}")
        
        # 验证内容
        content = validator.validate_content(response, "分析企业财务状况和风险")
        print(f"内容验证:")
        print(f"  相关性: {content['relevance_score']:.2f}")
        print(f"  完整性: {content['completeness_score']:.2f}")
        print(f"  清晰度: {content['clarity_score']:.2f}")
        print(f"  总体评分: {content['overall_score']:.2f}")
        if content['issues']:
            print(f"  问题: {', '.join(content['issues'])}")
        
        print("-" * 40)
    
    print("\n" + "=" * 80)
    print("编排器输出格式测试完成")
    print("=" * 80)


def test_multi_agent_collaboration_indicators():
    """测试多智能体协作指标"""
    print("\n" + "=" * 80)
    print("测试多智能体协作指标")
    print("=" * 80)
    
    collaboration_indicators = {
        "专家协作": ["财务专家", "税务专家", "法务专家", "协同分析", "多专家"],
        "综合分析": ["综合建议", "整体评估", "全面分析", "多维度"],
        "风险识别": ["风险分析", "风险评估", "风险识别", "风险点"],
        "建议措施": ["建议", "措施", "方案", "策略", "行动计划"],
        "数据支持": ["数据", "指标", "百分比", "增长率", "同比"]
    }
    
    test_response = """多智能体协作分析报告

根据财务专家、税务专家、法务专家的协同分析，企业综合评估如下：

📈 财务表现（财务专家）
• 营收增长率：15%（行业平均：12%）
• 净利润率：8.5%（目标：10%）
• 现金流充足率：120%

💰 税务优化（税务专家）
• 可享受税收优惠：研发费用加计扣除（150万元）
• 潜在节税空间：年度约60万元
• 合规风险：关联交易文档需完善

⚖️ 法律合规（法务专家）
• 合同管理合规率：85%（目标：95%）
• 劳动法风险：加班费计算需规范
• 知识产权：3项专利需续费

🎯 综合建议
1. 财务方面：加强成本控制，目标降低运营成本5%
2. 税务方面：启动税务筹划，合理利用优惠政策
3. 法律方面：完善合同管理制度，建立合规培训

📊 预期效果
• 财务：预计提升净利润率1-2个百分点
• 税务：年度节税约60-80万元
• 法律：降低合规风险30%

⚠️ 注意事项
建议成立跨部门工作小组，定期跟踪改进措施执行情况。"""
    
    print("\n协作指标检查:")
    print("-" * 40)
    
    found_indicators = {}
    for category, indicators in collaboration_indicators.items():
        found = [ind for ind in indicators if ind in test_response]
        found_indicators[category] = found
        print(f"{category}:")
        if found:
            print(f"  ✅ 找到: {', '.join(found)}")
        else:
            print(f"  ❌ 未找到相关指标")
    
    # 计算协作度分数
    total_categories = len(collaboration_indicators)
    categories_with_indicators = sum(1 for found in found_indicators.values() if found)
    collaboration_score = categories_with_indicators / total_categories
    
    print(f"\n协作度分数: {collaboration_score:.2f} ({categories_with_indicators}/{total_categories})")
    
    if collaboration_score >= 0.8:
        print("✅ 多智能体协作表现良好")
    elif collaboration_score >= 0.6:
        print("⚠️ 多智能体协作基本达标")
    else:
        print("❌ 多智能体协作不足")
    
    print("\n" + "=" * 80)
    print("多智能体协作指标测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_orchestrator_output_format()
    test_multi_agent_collaboration_indicators()
    
    print("\n" + "=" * 80)
    print("所有测试完成")
    print("=" * 80)