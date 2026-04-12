# -*- coding: utf-8 -*-
import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    # Replace <Warning with <AlertTriangle
    content = content.replace('<Warning', '<AlertTriangle')
    
    # Replace Warning, with AlertTriangle, in imports
    content = content.replace('Warning,', 'AlertTriangle,')
    content = content.replace('Warning }', 'AlertTriangle }')
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    src_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src'
    
    files_to_fix = [
        'views/FinancialDataEntryView.vue',
        'views/TestDataGuideView.vue',
        'views/AuditResultView.vue',
        'views/MultiAgentChatView.vue',
        'views/ContractReviewView.vue',
        'views/FinancialHealthView.vue',
        'views/IntentClassifierDebugView.vue',
        'views/TaskManagementView.vue',
        'views/TaxIntelligenceView.vue',
        'views/TaxSubmissionView.vue',
        'components/TaxWorkflowRisk.vue',
        'components/HumanReviewDialog.vue',
        'components/TaxWorkflowViewer.vue',
        'components/IssueList.vue',
        'views/ReviewDashboard.vue',
    ]
    
    fixed_count = 0
    for file_path in files_to_fix:
        full_path = os.path.join(src_dir, file_path)
        if os.path.exists(full_path):
            if fix_file(full_path):
                print(f'Fixed: {file_path}')
                fixed_count += 1
            else:
                print(f'No changes: {file_path}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
