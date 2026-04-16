"""
测试编排器数据缺失场景
"""
import sys
import re
import json

def test_requires_enterprise_data():
    """测试 _requires_enterprise_data 逻辑"""
    
    print("=" * 80)
    print("测试1: _requires_enterprise_data 逻辑")
    print("=" * 80)
    
    enterprise_patterns = [
        r'我们', r'我司', r'贵公司', r'本公司', r'本企业',
        r'公司', r'企业', r'财务状况', r'经营情况',
        r'税务情况', r'风险分析', r'财务风险', r'税务风险'
    ]
    
    test_cases = [
        "分析企业税务风险",
        "我们公司的财务状况如何",
        "如何报税",
        "一般税务问题",
        "帮我看看税务",
        "分析税务风险"
    ]
    
    specialist_keywords = ['finance', 'tax', 'legal', '财务', '税务', '法务', '风险']
    
    for user_input in test_cases:
        user_input_lower = user_input.lower()
        requires_data = any(re.search(pattern, user_input_lower) for pattern in enterprise_patterns) or \
                       any(keyword in user_input_lower for keyword in specialist_keywords)
        
        print(f"\n输入: '{user_input}'")
        print(f"  结果: {'需要企业数据' if requires_data else '不需要企业数据'}")
        
        # 匹配的模式
        matched_patterns = [p for p in enterprise_patterns if re.search(p, user_input_lower)]
        matched_keywords = [k for k in specialist_keywords if k in user_input_lower]
        
        if matched_patterns:
            print(f"  匹配的模式: {matched_patterns}")
        if matched_keywords:
            print(f"  匹配的关键词: {matched_keywords}")


def test_format_no_data_response():
    """测试 _format_no_data_response 输出格式"""
    
    print("\n" + "=" * 80)
    print("测试2: 无数据场景响应格式")
    print("=" * 80)
    
    # 模拟专家结果
    specialist_result = {
        "status": "no_data",
        "specialist": "tax",
        "result": {
            "specialist_type": "tax",
            "response": "感谢您的税务专家咨询！根据您的问题「分析企业税务风险」，这是一个需要企业特定税务专家数据才能完成的专业税务分析。",
            "summary": "当前系统中未检索到您的企业相关税务专家数据，无法直接生成税务专家报告。",
            "limitations": [
                "企业税务数据尚未导入系统",
                "无法进行定量分析",
                "无法生成具体风险评估"
            ],
            "general_guidance": {
                "topic": "企业税务风险管理通用指导",
                "general_knowledge": [
                    "税务风险管理是企业内部控制的重要组成部分",
                    "主要税务风险包括：增值税风险、企业所得税风险等",
                    "税务风险管理的目标是确保企业合规经营"
                ],
                "best_practices": [
                    "建立健全的税务管理制度",
                    "定期进行税务健康检查"
                ],
                "next_steps": "建议您先导入企业的税务数据"
            }
        },
        "suggestions": [
            {
                "title": "上传税务申报材料",
                "description": "上传增值税申报表、企业所得税申报表等税务材料",
                "required_fields": ["增值税申报表", "企业所得税申报表"],
                "format": "支持 PDF/Excel 格式"
            },
            {
                "title": "对接电子税务局",
                "description": "如果您的企业已开通电子税务局接口，可以实现数据自动同步",
                "benefits": ["数据自动同步", "实时风险监控"]
            }
        ]
    }
    
    # 模拟 _format_no_data_response 方法的简化实现
    result = specialist_result.get("result", {})
    specialist_type = specialist_result.get("specialist", "general")
    suggestions = specialist_result.get("suggestions", [])
    
    specialist_name_map = {
        "finance": "财务专家",
        "tax": "税务专家",
        "legal": "法务专家"
    }
    
    specialist_display = specialist_name_map.get(specialist_type, "专家")
    response_text = result.get("response", "")
    summary = result.get("summary", "")
    general_guidance = result.get("general_guidance", {})
    limitations = result.get("limitations", [])
    
    sections = []
    
    sections.append(f"## {specialist_display}")
    sections.append(f"\n### 分析说明\n\n{response_text}\n\n{summary}")
    
    if limitations:
        sections.append("### 当前限制\n\n" + "\n".join(f"- {limitation}" for limitation in limitations))
    
    if general_guidance:
        sections.append(f"\n### {general_guidance.get('topic', '通用指导')}\n")
        sections.append("#### 基础知识\n" + "\n".join(f"- {knowledge}" for knowledge in general_guidance.get('general_knowledge', [])))
        
        if general_guidance.get('best_practices'):
            sections.append("\n#### 最佳实践\n" + "\n".join(f"- {practice}" for practice in general_guidance.get('best_practices', [])))
        
        if general_guidance.get('next_steps'):
            sections.append(f"\n> **下一步**: {general_guidance.get('next_steps', '')}")
    
    if suggestions:
        suggestions_lines = ["\n### 数据导入建议\n"]
        for i, suggestion in enumerate(suggestions, 1):
            suggestions_lines.append(f"{i}. **{suggestion.get('title', '导入数据')}**")
            suggestions_lines.append(f"   - {suggestion.get('description', '')}")
            if suggestion.get('required_fields'):
                suggestions_lines.append(f"   - 必填字段: {', '.join(suggestion.get('required_fields', []))}")
            if suggestion.get('format'):
                suggestions_lines.append(f"   - 支持格式: {suggestion.get('format', '')}")
            suggestions_lines.append("")
        sections.append("\n".join(suggestions_lines))
    
    sections.append("\n---\n\n**温馨提示**: 为了给您提供更准确的分析报告，建议您先导入企业的相关财务/税务数据。")
    
    response = "\n".join(sections)
    
    print(response)


def test_output_agent_cleaning():
    """测试输出智能体的清理逻辑"""
    
    print("\n" + "=" * 80)
    print("测试3: 输出智能体清理逻辑")
    print("=" * 80)
    
    test_text = """

## 税务专家

### 分析说明

感谢您的咨询！


### 当前限制

- 企业税务数据尚未导入系统


- 无法进行定量分析



### 数据导入建议

1. **上传税务申报材料**
   - 上传增值税申报表
   - 必填字段: 增值税申报表


"""
    
    cleaned = test_text
    
    # 移除多余的连续空行（保留最多2个）
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # 移除行尾多余空格
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
    
    # 移除行首或段落开头的多余空格
    cleaned = re.sub(r'\n\s{2,}', '\n', cleaned)
    
    print("清理后的文本：")
    print(cleaned)


def main():
    print("\n" + "=" * 80)
    print("编排器数据缺失场景测试")
    print("=" * 80)
    
    test_requires_enterprise_data()
    test_format_no_data_response()
    test_output_agent_cleaning()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
