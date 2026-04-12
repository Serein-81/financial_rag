# -*- coding: utf-8 -*-
import os
import re

def fix_file_completely(filepath):
    """彻底修复Vue文件的编码问题"""
    with open(filepath, 'rb') as f:
        raw = f.read()
    
    # 方法1：尝试用GBK解码整个文件
    try:
        content = raw.decode('gbk')
        # 验证内容是否包含合理的中文
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', content)
        if len(''.join(chinese_chars)) > 50:
            # 文件是GBK编码，保存为UTF-8
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except:
        pass
    
    # 方法2：逐行处理，尝试用GBK解码每行
    try:
        lines = raw.split(b'\n')
        fixed_lines = []
        modified = False
        
        for line in lines:
            try:
                # 先尝试UTF-8
                decoded_line = line.decode('utf-8')
                fixed_lines.append(decoded_line)
            except UnicodeDecodeError:
                # UTF-8失败，尝试GBK
                try:
                    decoded_line = line.decode('gbk')
                    fixed_lines.append(decoded_line)
                    modified = True
                except:
                    # 尝试修复无效字节
                    fixed_line = fix_invalid_bytes(line)
                    fixed_lines.append(fixed_line)
                    modified = True
        
        if modified:
            content = '\n'.join(fixed_lines)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Line-by-line fix failed: {e}")
    
    return False

def fix_invalid_bytes(data):
    """修复无效的UTF-8字节"""
    result = bytearray()
    i = 0
    
    while i < len(data):
        byte = data[i]
        
        if byte < 0x80:
            # ASCII字符
            result.append(byte)
            i += 1
        elif byte >= 0xC0:
            # 可能是一个多字节UTF-8字符的开始
            if byte >= 0xF0:
                length = 4
            elif byte >= 0xE0:
                length = 3
            else:
                length = 2
            
            # 获取可能完整的字符
            if i + length <= len(data):
                seq = data[i:i+length]
                try:
                    # 尝试用UTF-8解码
                    decoded = seq.decode('utf-8')
                    result.extend(seq)
                    i += length
                except UnicodeDecodeError:
                    # UTF-8解码失败，可能是GBK编码
                    # 尝试用latin1解码每个字节并合并为GBK字符
                    try:
                        if length == 2:
                            # 两个字节可能是GBK字符
                            byte1 = data[i]
                            byte2 = data[i+1]
                            gbk_seq = bytes([byte1, byte2])
                            char = gbk_seq.decode('gbk')
                            # 再编码为UTF-8
                            result.extend(char.encode('utf-8'))
                            i += 2
                            continue
                    except:
                        pass
                    # 无法修复，跳过第一个字节
                    result.append(byte)
                    i += 1
            else:
                # 不完整的序列
                result.append(byte)
                i += 1
        else:
            # 无效的延续字节或单独的 >= 0x80 字节
            # 尝试用latin1解码
            try:
                char = bytes([byte]).decode('latin1')
                result.extend(char.encode('utf-8'))
            except:
                result.append(byte)
            i += 1
    
    try:
        return result.decode('utf-8')
    except:
        return result.decode('utf-8', errors='replace')

def main():
    views_dir = r'd:\Python\Codebase\My_rag\rag_frontend\src\views'
    
    files_to_fix = [
        'AuditResultView.vue',
        'ChatLogsView.vue',
        'ContractReviewView.vue',
        'FinancialDataEntryView.vue',
        'FinancialHealthView.vue',
        'HITLApprovalView.vue',
        'IntentClassifierDebugView.vue',
        'MultiAgentChatView.vue',
        'MultiAgentMonitorView.vue',
        'NotificationCenterView.vue',
        'SecurityAuditView.vue',
        'TaskManagementView.vue',
        'TaxIntelligenceView.vue',
        'TestDataGuideView.vue',
    ]
    
    fixed_count = 0
    for filename in files_to_fix:
        filepath = os.path.join(views_dir, filename)
        if os.path.exists(filepath):
            print(f'Processing: {filename}')
            try:
                if fix_file_completely(filepath):
                    print(f'  Fixed: {filename}')
                    fixed_count += 1
                else:
                    print(f'  No changes: {filename}')
            except Exception as e:
                print(f'  Error: {e}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
