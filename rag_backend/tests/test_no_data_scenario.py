#!/usr/bin/env python3
"""
测试无数据场景下的输出智能体
验证是否正确使用列表而不是表格
"""

import asyncio
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_backend'))

async def test_no_data_scenario():
    """测试无数据场景"""
    print("=" * 80)
    print("测试：税务风险分析 - 无数据场景")
    print("=" * 80)

    try:
        from app.agent_framework.core.output_agent import OutputAgent
        from app.agent_framework.llm.factory import create_llm_adapter

        llm = create_llm_adapter(provider="deepseek")
        output_agent = OutputAgent(llm_adapter=llm)

        user_query = "分析企业税务风险"

        specialist_results = {
            "税务专家": """## 税务专家分析

感谢您的税务咨询！根据您的问题「分析企业税务风险」，这是一个需要企业特定税务数据才能完成的专业税务分析。

### 当前状态
系统目前未检测到您导入的税务申报材料、企业所得税数据或增值税记录。

### 主要限制
- 无法进行定量风险评估
- 无法生成具体风险评分
- 无法提供精准的合规建议

### 税务风险通用知识
税务风险管理是企业内部控制的重要组成部分，建议您关注以下常见风险类型：

**申报风险**：
- 典型表现：申报时间延误、税额计算错误
- 建议措施：按时申报、仔细核对

**发票风险**：
- 典型表现：抵扣凭证不规范、发票遗失
- 建议措施：规范管理、妥善保存

**政策风险**：
- 典型表现：优惠政策适用不当、解读偏差
- 建议措施：关注政策、加强培训

**账务风险**：
- 典型表现：成本列支不规范、凭证缺失
- 建议措施：规范记账、完善档案

### 数据导入建议
要获得准确的企业税务风险分析报告，建议您：

**第一步**：上传税务申报材料
- 增值税申报表（按月或按季）
- 企业所得税申报表（按年）

**第二步**：完善企业基础信息
- 纳税人识别号
- 税务登记信息

> 💡 温馨提示：数据导入后，系统将自动进行深度分析。
"""
        }

        print("\n[1] 调用输出智能体...")
        result = await output_agent.synthesize_and_format(
            specialist_results,
            user_query
        )

        print(f"\n[2] 输出长度: {len(result)} 字符")

        print("\n[3] 检查输出格式...")
        lines = result.split('\n')
        print(f"   总行数: {len(lines)}")

        table_pattern = re.compile(r'\|[^\n]+\|')
        table_lines = [line for line in lines if table_pattern.match(line.strip())]
        print(f"   表格行数: {len(table_lines)}")

        list_pattern = re.compile(r'^[\s]*[-*]\s+')
        list_lines = [line for line in lines if list_pattern.match(line.strip())]
        print(f"   列表行数: {len(list_lines)}")

        print("\n[4] 检查空表格格式错误...")
        empty_table_errors = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('|'):
                cells = [c.strip() for c in stripped.split('|') if c.strip()]
                if len(cells) == 0:
                    empty_table_errors.append(f"第{i}行: {stripped}")
                elif all(len(c) < 2 for c in cells):
                    empty_table_errors.append(f"第{i}行: {stripped}")

        if empty_table_errors:
            print(f"   ❌ 发现 {len(empty_table_errors)} 个空表格格式错误:")
            for error in empty_table_errors[:5]:
                print(f"      {error}")
        else:
            print("   ✅ 没有发现空表格格式错误")

        print("\n[5] 输出质量评估...")
        quality_score = 0

        if len(table_lines) == 0:
            print("   ✅ 没有使用表格（符合预期）")
            quality_score += 1
        else:
            print(f"   ⚠️  仍然使用了 {len(table_lines)} 行表格")
            if len(table_lines) <= 2:
                print("      但表格行数较少，可能影响可读性")

        if len(list_lines) >= 10:
            print(f"   ✅ 使用了 {len(list_lines)} 个列表项（内容充实）")
            quality_score += 1
        elif len(list_lines) >= 5:
            print(f"   ⚠️  使用了 {len(list_lines)} 个列表项（建议增加）")
            quality_score += 0.5
        else:
            print(f"   ❌ 列表项过少: {len(list_lines)} 个")

        if len(result) >= 1500:
            print(f"   ✅ 输出长度充足: {len(result)} 字符")
            quality_score += 1
        else:
            print(f"   ⚠️  输出长度较短: {len(result)} 字符")

        print(f"\n[6] 总体质量评分: {quality_score}/3")
        if quality_score >= 2.5:
            print("   ✅ 测试通过！")
        else:
            print("   ⚠️  需要进一步优化")

        print("\n[7] 预览输出（前500字符）...")
        print("-" * 80)
        print(result[:500])
        print("-" * 80)

        return quality_score >= 2.5

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    result = asyncio.run(test_no_data_scenario())
    sys.exit(0 if result else 1)
