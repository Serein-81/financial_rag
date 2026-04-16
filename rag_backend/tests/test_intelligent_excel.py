"""
测试智能Excel列名识别功能
"""
import pandas as pd
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from difflib import SequenceMatcher

# 导入列名映射系统
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_backend'))

from app.api.v1.endpoints.user_financial_data import (
    COLUMN_MAPPING, 
    normalize_column_name, 
    calculate_similarity,
    auto_detect_columns
)

def create_test_excel_variants():
    """创建不同格式的测试Excel文件"""
    
    test_variants = [
        {
            'name': '标准中文模板',
            'columns': ['财务年度', '周期类型', '周期开始日期', '周期结束日期', 
                       '总收入', '应税销售额', '免税销售额', '总支出', 
                       '可抵扣支出', '不可抵扣支出', '进项税额', '销项税额',
                       '增值税率', '应纳税所得额', '企业所得税率', '是否小微企业',
                       '工资薪金', '专项附加扣除', '发票总数', '进项发票数', '销项发票数']
        },
        {
            'name': '英文变体',
            'columns': ['Year', 'Period Type', 'Start Date', 'End Date',
                       'Revenue', 'Taxable Sales', 'Tax Free Sales', 'Expenses',
                       'Deductible Expenses', 'Non Deductible Expenses', 
                       'Input Tax', 'Output Tax', 'VAT Rate', 'Taxable Income',
                       'Corporate Tax Rate', 'Small Enterprise', 
                       'Payroll', 'Special Deductions', 'Invoice Count',
                       'Input Invoices', 'Output Invoices']
        },
        {
            'name': '混合中英文',
            'columns': ['年度', '类型', '开始', '结束',
                       '收入', '应税销售额', '免税销售', '费用',
                       '可抵扣费用', '不可抵扣费用', 
                       '进项税', '销项税', '税率', '应税收入',
                       '企业所得税率', '小微', 
                       '薪酬', '专项扣除', '发票数',
                       '收票数', '开票数']
        },
        {
            'name': '缩写和简化',
            'columns': ['FY', 'Type', 'From', 'To',
                       'Sales', 'Taxable', 'TaxFree', 'Costs',
                       'DedCosts', 'NonDedCosts', 
                       'VAT In', 'VAT Out', 'Rate', 'Tax Base',
                       'CIT Rate', 'SME', 
                       'Wages', 'Add Ded', 'Inv Total',
                       'Inv In', 'Inv Out']
        },
        {
            'name': '带空格的英文',
            'columns': ['Fiscal Year', 'Period Type', 'Start Date', 'End Date',
                       'Total Revenue', 'Taxable Sales Amount', 'Tax Free Sales Amount',
                       'Total Expenses', 'Deductible Expenses Amount', 
                       'Non Deductible Expenses Amount', 
                       'Input Tax Amount', 'Output Tax Amount', 
                       'VAT Rate (%)', 'Taxable Income Amount',
                       'Corporate Tax Rate (%)', 'Is Small Enterprise',
                       'Total Payroll', 'Special Deductions Amount',
                       'Total Invoices', 'Input Invoice Count', 'Output Invoice Count']
        }
    ]
    
    return test_variants

def test_column_detection():
    """测试列名识别功能"""
    print("=" * 80)
    print("智能Excel列名识别测试")
    print("=" * 80)
    
    test_variants = create_test_excel_variants()
    
    for variant in test_variants:
        print(f"\n\n测试变体: {variant['name']}")
        print("-" * 80)
        print(f"Excel列名: {', '.join(variant['columns'])}")
        print()
        
        detected = auto_detect_columns(variant['columns'])
        
        detected_count = sum(1 for v in detected.values() if v is not None)
        required_detected = 0
        required_total = 0
        
        print("识别结果:")
        print()
        
        for field, config in COLUMN_MAPPING.items():
            excel_col = detected[field]
            is_required = config['required']
            
            if is_required:
                required_total += 1
                if excel_col:
                    required_detected += 1
            
            status_icon = "✓" if excel_col else "✗"
            status_text = "已识别" if excel_col else "未识别"
            required_text = "(必需)" if is_required else "(可选)"
            
            if excel_col:
                print(f"  {status_icon} {field:30s} {required_text:8s} → '{excel_col}'  {status_text}")
            else:
                print(f"  {status_icon} {field:30s} {required_text:8s}   {status_text}")
        
        print()
        print(f"识别统计:")
        print(f"  - 总字段数: {len(detected)}")
        print(f"  - 已识别: {detected_count} ({detected_count/len(detected)*100:.1f}%)")
        print(f"  - 必需字段: {required_total}")
        print(f"  - 已识别必需字段: {required_detected} ({required_detected/required_total*100:.1f}%)")
        
        if required_detected == required_total:
            print(f"  ✓ 可以成功导入此格式")
        else:
            print(f"  ✗ 缺少必需字段，无法导入")

def test_similarity_calculation():
    """测试相似度计算"""
    print("\n\n相似度计算示例:")
    print("=" * 80)
    
    test_pairs = [
        ("总收入", "总收入"),
        ("总收入", "营业收入"),
        ("总收入", "Revenue"),
        ("总收入", "Revenu"),
        ("应税销售额", "应税销售额"),
        ("应税销售额", "Taxable Sales"),
        ("应税销售额", "taxable_sales"),
        ("增值税率", "VAT税率"),
        ("增值税率", "税率"),
    ]
    
    for s1, s2 in test_pairs:
        similarity = calculate_similarity(s1, s2)
        print(f"  '{s1}' ↔ '{s2}': {similarity:.3f}")

def create_sample_excel():
    """创建一个示例Excel文件用于测试"""
    print("\n\n创建示例Excel测试文件...")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "财务数据"
    
    # 使用标准中文列名
    headers = ['财务年度', '周期类型', '总收入', '应税销售额', '免税销售额', 
               '总支出', '可抵扣支出', '进项税额', '销项税额', '增值税率',
               '应纳税所得额', '企业所得税率']
    
    ws.append(headers)
    
    # 添加示例数据
    sample_data = [
        [2024, 'yearly', 1000000, 850000, 150000, 600000, 500000, 110500, 85000, 0.13, 400000, 0.25],
        [2023, 'yearly', 900000, 750000, 150000, 550000, 450000, 97500, 75000, 0.13, 350000, 0.25],
    ]
    
    for row in sample_data:
        ws.append(row)
    
    output_path = 'test_financial_data.xlsx'
    wb.save(output_path)
    print(f"  ✓ 示例文件已创建: {output_path}")

def main():
    """主测试函数"""
    test_similarity_calculation()
    test_column_detection()
    create_sample_excel()
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)

if __name__ == '__main__':
    main()
