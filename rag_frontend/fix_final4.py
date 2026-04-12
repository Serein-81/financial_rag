# -*- coding: utf-8 -*-
import os

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    fixes = [
        # FinancialDataEntryView.vue
        ('总收入(?', '总收入（元）'),
        ('应税销售额 (?', '应税销售额（元）'),
        ('免税销售额 (?', '免税销售额（元）'),
        ('可抵扣支出(?', '可抵扣支出（元）'),
        ('进项税额 (?', '进项税额（元）'),
        ('销项税额(?', '销项税额（元）'),
        ('应纳税所得额 (?', '应纳税所得额（元）'),
        ('工资薪金总额 (?', '工资薪金总额（元）'),
        ('<li>?<strong>智能识别', '<li>• <strong>智能识别'),
        ('导入错误 ({{ uploadErrors.length }}?', '导入错误（{{ uploadErrors.length }}条）'),
        ('第{{ error.row }}?{{ error.field }}:', '第{{ error.row }}行，{{ error.field }}列：'),
        
        # ChatLogsView.vue
        ('<p class="text-sm text-gray-500 mt-1">?{{ activeTab', '<p class="text-sm text-gray-500 mt-1">{{ activeTab'),
        ('?{{ page }} 页，?{{ getTotalPages() }}', '第 {{ page }} 页，共 {{ getTotalPages() }}'),
        ('?{{ actionLogsTotal }} 条记录', '{{ actionLogsTotal }} 条记录'),
        
        # NotificationCenterView.vue
        ('<span>?{{ filteredNotifications.length }}', '<span>{{ filteredNotifications.length'),
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
        'FinancialDataEntryView.vue',
        'ChatLogsView.vue',
        'NotificationCenterView.vue',
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
