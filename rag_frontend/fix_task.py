# -*- coding: utf-8 -*-
import os

def fix_file(filepath):
    """修复单个文件中的所有乱码"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    fixes = [
        # TaskManagementView.vue
        ('创建第一个任?', '创建第一个任务'),
        ('已暂?', '已暂停'),
        ('无描?', '无描述'),
        ('状?', '状态'),
        ('开始时?', '开始时间'),
        ('已完?', '已完成'),
        ('运行?', '运行中'),
        ('已取?', '已取消'),
        ('即将执行的任?', '即将执行的任务'),
        ('请输入任务名?', '请输入任务名称'),
        ('快速创建任?', '快速创建任务'),
        ('检查频?', '检查频率'),
        ('每小?', '每小时'),
        ('查看任务执行的完整信?', '查看任务执行的完整信息'),
        ('taskTypeOptions.find', 'taskTypeOptions.find'),
        ('frequencyOptions.find', 'frequencyOptions.find'),
        ("placeholder=\"请输入任务名?", "placeholder=\"请输入任务名称"),
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
