# app/utils/file_utils.py
"""
文件处理工具函数
"""
import hashlib


def calculate_md5(file_obj) -> str:
    """
    计算文件的 MD5 哈希值，用于文件查重
    
    Args:
        file_obj: 文件对象（支持 read() 和 seek() 方法）
        
    Returns:
        str: 32位小写的MD5哈希值
        
    Note:
        读取完后会将文件指针重置回开头，确保后续操作正常
    """
    md5 = hashlib.md5()
    
    # 分块读取，防止大文件撑爆内存
    for chunk in iter(lambda: file_obj.read(4096), b""):
        md5.update(chunk)
    
    # 关键：计算完必须把指针移回开头，否则后续无法保存文件
    file_obj.seek(0)
    
    return md5.hexdigest()
