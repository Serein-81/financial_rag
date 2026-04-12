# -*- coding: utf-8 -*-
import os

def fix_file(filepath):
    """修复包含U+FFFD替换字符的文件"""
    with open(filepath, 'rb') as f:
        raw = f.read()
    
    original = raw
    modified = False
    
    # 找到所有替换字符 (ef bf bd)
    i = 0
    result = bytearray()
    
    while i < len(raw):
        # 检查是否是UTF-8替换字符 U+FFFD
        if i + 2 < len(raw) and raw[i] == 0xef and raw[i+1] == 0xbf and raw[i+2] == 0xbd:
            # 这是一个替换字符
            # 检查下一个字节
            if i + 3 < len(raw):
                next_byte = raw[i+3]
                # ef bf bd 3f 表示原来的字符被替换成了 ?
                # 我们需要猜测原来的字符
                if next_byte == 0x3f:  # ASCII '?'
                    # 这表示原本的中文字符无法解码
                    # 根据上下文尝试修复
                    # 先跳过这个替换字符和问号
                    # 尝试从原始文件获取上下文
                    pass
            # 直接跳过替换字符本身
            i += 3
            modified = True
            continue
        
        result.append(raw[i])
        i += 1
    
    if modified:
        try:
            content = result.decode('utf-8')
            # 查找并修复特定的错误模式
            fixes = [
                ('财务数�?', '财务数据'),
                ('暂无财务数据，请填�?', '暂无财务数据，请填写'),
                ('该周期暂无财务数据，请填�?', '该周期暂无财务数据，请填写'),
                ("selectedPeriod = ref('�?)", "selectedPeriod = ref('2024-01')"),
                ("ref('�?)", "ref('2024-01')"),
            ]
            for wrong, correct in fixes:
                if wrong in content:
                    content = content.replace(wrong, correct)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error: {e}")
    
    return False

def main():
    views_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src\views'
    
    files = [
        'AuditResultView.vue',
        'ChatLogsView.vue',
        'ContractReviewView.vue',
        'EnterpriseView.vue',
        'FinancialDataEntryView.vue',
        'FinancialHealthView.vue',
        'HITLApprovalView.vue',
        'IntentClassifierDebugView.vue',
        'KnowledgeManagementView.vue',
        'MultiAgentChatView.vue',
        'MultiAgentMonitorView.vue',
        'NotificationCenterView.vue',
        'SecurityAuditView.vue',
        'TaskManagementView.vue',
        'TaxIntelligenceView.vue',
        'TestDataGuideView.vue',
    ]
    
    fixed_count = 0
    for filename in files:
        filepath = os.path.join(views_dir, filename)
        if os.path.exists(filepath):
            # 先读取文本检查是否有问题
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                if '�' in content or '\ufffd' in content:
                    print(f'Found issue in: {filename}')
                    if fix_file(filepath):
                        print(f'  Fixed: {filename}')
                        fixed_count += 1
                    else:
                        print(f'  No changes: {filename}')
                else:
                    print(f'No issues: {filename}')
            except Exception as e:
                print(f'Error reading {filename}: {e}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
