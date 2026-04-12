# -*- coding: utf-8 -*-
import os
import re

def fix_file(filepath):
    """修复单个文件中的所有乱码"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    # 修复各种乱码模式
    fixes = [
        # TaxIntelligenceView.vue
        ('本季度分?', '本季度分析'),
        ('合规?', '合规'),
        ('最近分?', '最近分析'),
        ('快速分?', '快速分析'),
        ('进项销项分?', '进项销项分析'),
        ("tax_type = '全税?", "tax_type = '全税种"),
        ('节省?', '节省'),
        ('暂未匹配到适用的税收优惠政?', '暂未匹配到适用的税收优惠政策'),
        ('当前申报状态良?', '当前申报状态良好'),
        ('未发现合规问?', '未发现合规问题'),
        ('低风?', '低风险'),
        ('消费?>消费?', '消费税>消费税'),
        ('全税?>全税?', '全税种>全税种'),
        ('请输入企业名?', '请输入企业名称'),
        ('开始分?', '开始分析'),
        
        # TestDataGuideView.vue
        ('应税销售额?<br/>', '应税销售额<br/>'),
        
        # TaskManagementView.vue
        ('确定要删除这个任务吗?', '确定要删除这个任务吗'),
        ('taskTypeOptions.find', 'taskTypeOptions.find'),
        ('frequencyOptions.find', 'frequencyOptions.find'),
    ]
    
    for wrong, correct in fixes:
        content = content.replace(wrong, correct)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    views_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src\views'
    
    files = [
        'TaxIntelligenceView.vue',
        'TestDataGuideView.vue',
        'TaskManagementView.vue',
    ]
    
    fixed_count = 0
    for filename in files:
        filepath = os.path.join(views_dir, filename)
        if os.path.exists(filepath):
            if fix_file(filepath):
                print(f'Fixed: {filename}')
                fixed_count += 1
            else:
                print(f'No changes: {filename}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
