# -*- coding: utf-8 -*-
import os
import glob

def fix_file_encoding(filepath):
    """修复Vue文件的编码问题"""
    # 首先尝试用GBK读取（因为文件可能是GBK编码的）
    try:
        with open(filepath, 'r', encoding='gbk') as f:
            content = f.read()
        # 检查内容是否包含合理的中文
        chinese_count = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
        if chinese_count > 10:
            # 文件很可能是GBK编码，保存为UTF-8
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except Exception as e:
        pass
    
    # 如果GBK读取失败，用二进制模式读取并修复
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
        
        # 尝试修复无效的UTF-8字节
        fixed = fix_invalid_utf8(raw)
        if fixed != raw:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed)
            return True
    except Exception as e:
        print(f"Binary fix failed for {filepath}: {e}")
    
    return False

def fix_invalid_utf8(data):
    """修复无效的UTF-8字节序列"""
    result = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        
        if byte < 0x80:
            # ASCII字符
            result.append(byte)
            i += 1
        elif byte >= 0xC0:
            # 可能是一个多字节字符的开始
            # 确定字符长度
            if byte >= 0xFC:
                length = 6
            elif byte >= 0xF8:
                length = 5
            elif byte >= 0xF0:
                length = 4
            elif byte >= 0xE0:
                length = 3
            elif byte >= 0xC0:
                length = 2
            
            # 获取完整字符
            if i + length <= len(data):
                seq = data[i:i+length]
                try:
                    seq.decode('utf-8')
                    result.extend(seq)
                    i += length
                except:
                    # 无效的UTF-8序列，尝试用latin1解码并重新编码
                    # 这是GBK编码被当作UTF-8的情况
                    if length == 2:
                        # 可能是GBK的双字节字符
                        # 尝试用latin1 -> gbk -> utf-8
                        try:
                            # latin1将每个字节当作一个字符
                            # 将两个字节合并为一个GBK字符
                            gbk_char = bytes([data[i], data[i+1]]).decode('gbk')
                            # 再编码为UTF-8
                            result.extend(gbk_char.encode('utf-8'))
                            i += 2
                            continue
                        except:
                            pass
                    # 无法修复，跳过这个字节
                    result.append(byte)
                    i += 1
            else:
                # 不完整的序列
                result.append(byte)
                i += 1
        else:
            # 无效的延续字节
            result.append(byte)
            i += 1
    
    # 尝试用UTF-8解码修复后的数据
    try:
        return result.decode('utf-8')
    except:
        # 仍然失败，用replace模式
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
                if fix_file_encoding(filepath):
                    print(f'  Fixed: {filename}')
                    fixed_count += 1
                else:
                    print(f'  No changes: {filename}')
            except Exception as e:
                print(f'  Error: {e}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
