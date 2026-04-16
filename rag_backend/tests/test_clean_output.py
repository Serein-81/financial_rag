"""
测试 _clean_output 方法对输出的影响
"""
import re

def original_clean_output(text: str) -> str:
    """
    原始的清理方法
    """
    if not text:
        return text
    
    cleaned = text
    
    # 移除多余的连续空行（保留最多2个）
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # 移除行尾多余空格
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
    
    # 移除 Markdown 代码块标记（如果有）
    cleaned = re.sub(r'^```markdown\n', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^```\n', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n```$', '', cleaned)
    
    # 移除行首多余的井号空格（保持标准 Markdown 格式）
    cleaned = re.sub(r'^#+\s*#+\s*', lambda m: m.group(0).replace('#', '', 1), cleaned, flags=re.MULTILINE)
    
    # 移除连续的短横线和空格（分隔线误判）
    cleaned = re.sub(r'^-\s*-{3,}$', '', cleaned, flags=re.MULTILINE)
    
    # 移除 Unicode 控制字符（除换行和Tab外）
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    
    # 移除特殊空白字符
    cleaned = re.sub(r'[\u200b-\u200d\uFEFF]', '', cleaned)
    
    # 移除行首或段落开头的多余空格
    cleaned = re.sub(r'\n\s{2,}', '\n', cleaned)
    
    # 限制表格单元格内容长度（超过50字符的截断）
    lines = cleaned.split('\n')
    processed_lines = []
    for line in lines:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            cells = line.split('|')
            processed_cells = []
            for cell in cells:
                cell_text = cell.strip()
                if len(cell_text) > 50:
                    cell_text = cell_text[:47] + '...'
                processed_cells.append(cell_text)
            line = '| ' + ' | '.join(processed_cells) + ' |'
        processed_lines.append(line)
    cleaned = '\n'.join(processed_lines)
    
    cleaned = cleaned.strip()
    
    return cleaned


def new_clean_output(text: str) -> str:
    """
    改进的清理方法 - 保留更多格式
    """
    if not text:
        return text
    
    cleaned = text
    
    # 移除多余的连续空行（保留最多2个）
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # 移除 Markdown 代码块标记（如果有）
    cleaned = re.sub(r'^```markdown\n', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^```\n', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n```$', '', cleaned)
    
    # 移除连续超过3个的短横线（分隔线误判）
    cleaned = re.sub(r'^---{3,}$', '', cleaned, flags=re.MULTILINE)
    
    # 移除 Unicode 控制字符（除换行和Tab外）
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    
    # 移除特殊空白字符
    cleaned = re.sub(r'[\u200b-\u200d\uFEFF]', '', cleaned)
    
    # 移除行尾多余空格，但保留缩进
    cleaned = re.sub(r'[ \t]+$', '', cleaned, flags=re.MULTILINE)
    
    cleaned = cleaned.strip()
    
    return cleaned


# 测试样本
test_content = """## 企业税务风险分析报告

感谢您的咨询！当前系统中未检索到您的企业税务数据。

### 一、当前情况说明

系统检测到以下数据缺口：
- 未获取增值税申报表
- 缺少发票管理数据
- 无税收优惠记录

### 二、税务风险基础知识

| 风险类别 | 典型表现 | 建议措施 |
|----------|----------|----------|
| 申报风险 | 申报时间延误、税额计算错误 | 按时申报、仔细核对 |
| 发票风险 | 抵扣凭证不规范、发票遗失 | 规范管理、妥善保存 |

> [TIP] **温馨提示**：数据导入后，系统将自动生成详细报告。

### 三、数据导入建议

**第一步**：上传税务申报材料
- 增值税申报表（最近36个月）
- 企业所得税年度申报表
"""

print("=" * 80)
print("原始内容：")
print(test_content)
print(f"\n原始长度: {len(test_content)} 字符")

print("\n" + "=" * 80)
print("原始 clean_output 处理后：")
original_result = original_clean_output(test_content)
print(original_result)
print(f"\n处理后长度: {len(original_result)} 字符")
print(f"丢失: {len(test_content) - len(original_result)} 字符")

print("\n" + "=" * 80)
print("新的 clean_output 处理后：")
new_result = new_clean_output(test_content)
print(new_result)
print(f"\n处理后长度: {len(new_result)} 字符")
print(f"丢失: {len(test_content) - len(new_result)} 字符")

print("\n" + "=" * 80)
print("差异对比：")
if len(original_result) != len(new_result):
    print(f"✅ 新方法保留了 {len(new_result) - len(original_result)} 额外字符")
