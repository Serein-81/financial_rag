# app/agent_framework/llm/token_utils.py

"""
Token 计数工具

提供文本和响应的 token 统计功能
"""

import re


def num_tokens_from_string(text: str) -> int:
    """
    估算文本的 token 数量

    使用简单的中文字符和英文单词统计

    Args:
        text: 输入文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    other_chars = len(text) - chinese_chars - english_words

    return int(chinese_chars * 1.5 + english_words * 0.25 + other_chars * 0.5)


def total_token_count_from_response(response) -> int:
    """
    从 API 响应中提取 token 使用量

    Args:
        response: API 响应对象

    Returns:
        总 token 数
    """
    try:
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            if hasattr(usage, 'total_tokens'):
                return usage.total_tokens
            elif hasattr(usage, 'prompt_tokens') and hasattr(usage, 'completion_tokens'):
                return usage.prompt_tokens + usage.completion_tokens
        return 0
    except (AttributeError, TypeError):
        return 0


def estimate_tokens_from_messages(messages: list) -> int:
    """
    估算消息列表的总 token 数

    Args:
        messages: 消息列表

    Returns:
        估算的总 token 数
    """
    total = 0
    for msg in messages:
        content = msg.get('content', '')
        total += num_tokens_from_string(content)
        total += 4

    total += 3
    return total
