# -*- coding: utf-8 -*-
import os
import glob

def fix_encoding_issue(filepath):
    """将UTF-8编码的文件中由GBK误读产生的乱码转换回正确的中文"""
    with open(filepath, 'rb') as f:
        raw_bytes = f.read()
    
    original = raw_bytes
    
    # 乱码映射表：将常见的UTF-8错误解码模式映射回正确的中文
    # 这些乱码是GBK字节被当作UTF-8解码产生的
    replacements = [
        # 错
        (b'\xe9\x94\x99', b'\xe9\x94\x99'),  # 保留原本正确的
        # 败
        (b'\xe8\xb4\xa5', b'\xe8\xb4\xa5'),  # 保留原本正确的
        # 常见乱码模式替换
        (b'\xe9\x94\x99', b'\xe9\x94\x99'),  # 错 (latin1编码的GBK)
        (b'\xe8\xb4\xa5', b'\xe8\xb4\xa5'),  # 败
        (b'\xe9\x94\x99', b'\xe9\x94\x99'),  # 错
        (b'\xe8\xb4\xa5', b'\xe8\xb4\xa5'),  # 败
        # 问
        (b'\xe9\x97\xae', b'\xe9\x97\xae'),  # 问 (latin1编码的GBK)
        # 题
        (b'\xe9\xa2\x98', b'\xe9\xa2\x98'),  # 题 (latin1编码的GBK)
    ]
    
    # 方法1：尝试用latin1解码，然后用GBK编码回正确的中文
    try:
        content = raw_bytes.decode('utf-8', errors='replace')
        # 检测是否有乱码字符
        has_garbled = any(ord(c) > 0x4e00 and ord(c) < 0x9fff for c in content if len(c.encode('utf-8')) > 1)
        
        if '銆' in content or '?' in content:
            # 有明显的乱码标记
            # 尝试将乱码还原
            fixed = fix_garbled_text(content)
            if fixed != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(fixed)
                return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    
    return False

def fix_garbled_text(text):
    """修复乱码文本"""
    # 常见的GBK字符被UTF-8错误解码后的模式
    # 在latin1编码下，UTF-8的每个字节被当作一个字符
    # 例如：UTF-8的中文字符在GBK下的等价编码
    
    # 替换规则：latin1解码后的乱码 -> 正确的中文
    garbled_map = {
        '銆': '',  # 无效字符
        '娴': '获',  # 获取
        '澶': '取',  # 单独这个位置
        '闂': '失',
        '闃': '败',
        '闅': '请',
        '鍖': '稍',
        '闀': '重',
        '閿': '试',
        '閼': '验',
        '浠': '查',
        '浼': '证',
        '鎵': '失',
        '鍙': '败',
        '娴': '错',
        '澶': '误',
        '闂': '网',
        '闃': '络',
        '闅': '错',
        '鍖': '误',
        '闀': '请',
        '閿': '稍',
        '閼': '后',
        '浠': '重',
        '浼': '试',
        '鎵': '请',
        '鍙': '稍',
        '娴': '请',
        '澶': '稍',
        '闂': '后',
        '闃': '重',
        '闅': '试',
        '鍖': '错',
        '闀': '误',
        '娴': '请',
        '澶': '稍',
        '闂': '后',
        '闃': '重',
        '闅': '试',
    }
    
    # 只替换导致语法错误的明显乱码
    # 对于正常的中文保留原样
    
    # 替换明显的无效字符
    for garbled in ['銆', '浠ラ']:
        if garbled in text:
            # 查找并修复
            if '浠ラ' in text:
                text = text.replace('浠ラ', '检查')
            if '浠ラ' in text:
                text = text.replace('浠ラ', '加载')
    
    return text

def main():
    views_dir = r'd:\Python\Codebase\My_rag\rag_frontend\src\views'
    
    # 扫描所有Vue文件
    pattern = os.path.join(views_dir, '*.vue')
    files = glob.glob(pattern)
    
    print(f"Found {len(files)} Vue files")
    
    fixed_count = 0
    for filepath in files:
        filename = os.path.basename(filepath)
        
        # 读取文件内容
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue
        
        original = content
        modified = False
        
        # 修复特定乱码模式
        fixes = [
            ('鍗?', '失败'),
            ('浠ラ', '检查'),
            ('娴?', '获取'),
            ('闂ラ', '获取'),
            ('闃?', '状态'),
            ('娴ラ', '导入'),
            ('闅ラ', '失败'),
            ('娴?', '操作'),
            ('闃ラ', '请求'),
            ('闅ラ', '解析'),
            ('娴ラ', '分类'),
            ('闀?', '进入'),
            ('娴ラ', '会话'),
            ('闂ラ', '事件'),
            ('娴ラ', '配置'),
            ('闃ラ', '统计'),
            ('娴ラ', '检测'),
            ('娴ラ', '证书'),
            ('娴ラ', '访问'),
            ('闂ラ', '上传'),
            ('娴ラ', '下载'),
            ('娴ラ', '登录'),
            ('闂ラ', '注册'),
            ('闃ラ', '搜索'),
            ('娴ラ', '登记'),
            ('娴ラ', '图像'),
            ('闃ラ', '严重'),
            ('娴ラ', '信息'),
            ('娴ラ', '提示'),
            ('娴ラ', '审计'),
            ('娴ラ', '管理'),
            ('娴ラ', '通知'),
            ('娴ラ', '智能'),
            ('娴ラ', '任务'),
            ('娴ラ', '记录'),
            ('娴ラ', '处理'),
            ('娴ラ', '分析'),
            ('娴ラ', '规则'),
            ('娴ラ', '税务'),
            ('娴ラ', '财务'),
            ('娴ラ', '服务'),
            ('娴ラ', '数据'),
            ('娴ラ', '问题'),
            ('娴ラ', '体化'),
        ]
        
        for garbled, correct in fixes:
            if garbled in content:
                content = content.replace(garbled, correct)
                modified = True
        
        # 替换单独的乱码字符
        # 这些字符后面跟着正确的中文，表示前一个字符是乱码
        single_char_fixes = [
            ('娴', '获'),
            ('澶', '取'),
            ('闂', '失'),
            ('闃', '败'),
            ('闅', '请'),
            ('鍖', '稍'),
            ('闀', '重'),
            ('閿', '试'),
            ('閼', '验'),
            ('浠', '查'),
            ('浼', '证'),
            ('鎵', '错'),
            ('鍙', '误'),
        ]
        
        for wrong, correct in single_char_fixes:
            if wrong in content and content.count(wrong) > 0:
                # 替换所有出现
                content = content.replace(wrong, correct)
                modified = True
        
        if modified and content != original:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'Fixed: {filename}')
                fixed_count += 1
            except Exception as e:
                print(f"Error writing {filename}: {e}")
        else:
            print(f'No changes: {filename}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
