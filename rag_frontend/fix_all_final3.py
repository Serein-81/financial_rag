# -*- coding: utf-8 -*-
import os

def fix_file(filepath):
    """修复单个文件中的所有乱码"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    fixes = [
        # HITLApprovalView.vue
        ('允许的权限级?', '允许的权限级别'),
        ('允许的操?/th>', '允许的操作</th>'),
        ('禁止的操?/th>', '禁止的操作</th>'),
        
        # FinancialDataEntryView.vue
        ('销?{{ formData', '销项{{formData'),
        
        # TestDataGuideView.vue
        ('应税销售额?<br/>', '应税销售额<br/>'),
        
        # MultiAgentMonitorView.vue
        ('处理?, color:', '处理中， color:'),
        ('已完?, color:', '已完成， color:'),
        ('系统健康?', '系统健康度'),
        ('任务流水?', '任务流水线'),
        ('监控各Agent的请求量、响应时间和成功?', '监控各Agent的请求量、响应时间和成功率'),
        ('组件状?', '组件状态'),
        ('重新检?', '重新检测'),
        ('系统状?', '系统状态'),
        ('待审?', '待审核'),
        ('运行? :', '运行中 :'),
        ('已完? :', '已完成 :'),
        ('等待? :', '等待中 :'),
        ('流式输出? }}', '流式输出中 }}'),
        ('个任?', '个任务'),
        ('成功?', '成功率'),
        ('最后执行时?', '最后执行时间'),
        
        # TaxReportUploadView.vue
        ('删除这个报告吗?', '删除这个报告吗？'),
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
        'HITLApprovalView.vue',
        'FinancialDataEntryView.vue',
        'TestDataGuideView.vue',
        'MultiAgentMonitorView.vue',
        'TaxReportUploadView.vue',
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
