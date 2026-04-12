# -*- coding: utf-8 -*-
import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    # Fix patterns like 中文/span> -> 中文</span>
    content = re.sub(r'([\u4e00-\u9fff])/span>', r'\1</span>', content)
    content = re.sub(r'([\u4e00-\u9fff])/div>', r'\1</div>', content)
    content = re.sub(r'([\u4e00-\u9fff])/p>', r'\1</p>', content)
    content = re.sub(r'([\u4e00-\u9fff])/label>', r'\1</label>', content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    views_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src\views'
    
    files = [
        'MultiAgentChatView.vue',
        'TaxIntelligenceView.vue',
        'TaskManagementView.vue',
        'IntentClassifierDebugView.vue',
        'FinancialHealthView.vue',
        'ContractReviewView.vue',
        'AuditResultView.vue',
        'TestDataGuideView.vue',
        'FinancialDataEntryView.vue',
        'NotificationCenterView.vue',
        'ChatLogsView.vue',
        'MultiAgentMonitorView.vue',
        'HITLApprovalView.vue',
    ]
    
    fixed_count = 0
    for filename in files:
        filepath = os.path.join(views_dir, filename)
        if os.path.exists(filepath):
            if fix_file(filepath):
                print(f'Fixed: {filename}')
                fixed_count += 1
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
