# app/agent_framework/llm/notifications.py

"""
LLM 通知消息系统

提供上下文窗口截断等通知消息
"""

import re


def is_chinese(texts: list) -> bool:
    """
    检测文本是否包含中文

    Args:
        texts: 文本列表

    Returns:
        是否包含中文
    """
    if not texts:
        return False
    text = texts[0] if isinstance(texts, list) else texts
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return bool(chinese_pattern.search(str(text)))


LENGTH_NOTIFICATION_CN = "······\n由于大模型的上下文窗口大小限制，回答已经被大模型截断。"
LENGTH_NOTIFICATION_EN = "...\nThe answer is truncated by your chosen LLM due to its limitation on context length."


def get_length_notification(text: str) -> str:
    """
    根据文本语言获取截断通知

    Args:
        text: 输入文本

    Returns:
        对应语言的截断通知
    """
    if is_chinese([text]):
        return LENGTH_NOTIFICATION_CN
    return LENGTH_NOTIFICATION_EN


def append_length_notification(text: str) -> str:
    """
    为文本追加截断通知

    Args:
        text: 输入文本

    Returns:
        追加通知后的文本
    """
    notification = get_length_notification(text)
    return text + notification
