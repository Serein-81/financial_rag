"""
输出格式化工具

用于清理和格式化 Agent 的输出，移除调试信息和内部标记
"""

import re
from typing import Optional


class OutputFormatter:
    """输出格式化器"""
    
    DEBUG_PATTERNS = [
        r'\[工具调用多次失败\]',
        r'\[检测到重复思考.*?\]\n?',
        r'\[达到最大迭代次数.*?\]\n?',
        r'\[处理出错.*?\]\n?',
        r'\[执行超时.*?\]\n?',
        r'\n\n根据检索到的资料：\n\n.*?知识库中未找到相关内容.*?',
    ]
    
    PRIVATE_INFO_PATTERNS = [
        r'报销暗号[：:].*',
        r'启动密码[：:].*',
        r'秘[密钥][：:].*',
        r'password[：:].*',
        r'secret[：:].*',
    ]
    
    @classmethod
    def clean_output(cls, text: str) -> str:
        """
        清理输出文本
        
        Args:
            text: 原始输出文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        
        cleaned = text
        
        for pattern in cls.DEBUG_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
        
        for pattern in cls.PRIVATE_INFO_PATTERNS:
            cleaned = re.sub(pattern, '[已隐藏敏感信息]', cleaned, flags=re.IGNORECASE)
        
        cleaned = cleaned.strip()
        
        return cleaned
    
    @classmethod
    def format_no_result_answer(cls, question_type: str = "问题") -> str:
        """
        格式化"未找到结果"的回答
        
        Args:
            question_type: 问题类型
            
        Returns:
            格式化后的回答
        """
        return "抱歉，我暂时没有找到相关的信息。能否请您提供更多细节或换个方式描述您的问题？"
    
    @classmethod
    def format_error_answer(cls, error_msg: str = None) -> str:
        """
        格式化错误回答
        
        Args:
            error_msg: 错误信息
            
        Returns:
            格式化后的回答
        """
        return "抱歉，处理您的请求时遇到了一些问题，请稍后重试。"
    
    @classmethod
    def is_meaningful_response(cls, text: str, min_length: int = 10) -> bool:
        """
        检查响应是否有意义
        
        Args:
            text: 响应文本
            min_length: 最小长度
            
        Returns:
            是否有意义
        """
        if not text:
            return False
        
        cleaned = cls.clean_output(text)
        
        if len(cleaned.strip()) < min_length:
            return False
        
        empty_patterns = [
            r'^[\s\n\r]*$',
            r'^[\[\]（）()。，，、\.\,\!\！\?\？]+$',
        ]
        
        for pattern in empty_patterns:
            if re.match(pattern, cleaned):
                return False
        
        return True


output_formatter = OutputFormatter()
