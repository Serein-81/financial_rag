"""
统一时间工具函数

所有项目中的时间处理都应使用此模块，确保统一使用北京时间（Asia/Shanghai）
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# 北京时区
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def now_beijing() -> datetime:
    """
    获取当前北京时间
    
    Returns:
        当前时区的 datetime 对象（Asia/Shanghai）
    """
    return datetime.now(BEIJING_TZ)


def utc_now() -> datetime:
    """
    获取当前 UTC 时间
    
    Returns:
        当前 UTC 时区的 datetime 对象
    """
    return datetime.now(timezone.utc)


def to_beijing(dt: Optional[datetime]) -> Optional[datetime]:
    """
    将 datetime 转换为北京时间
    
    Args:
        dt: 要转换的 datetime 对象
    
    Returns:
        转换后的北京时间，如果输入为 None 则返回 None
    """
    if dt is None:
        return None
    
    # 如果没有时区信息，假设是 UTC 时间
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # 转换为北京时间
    return dt.astimezone(BEIJING_TZ)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    将 datetime 转换为 UTC 时间
    
    Args:
        dt: 要转换的 datetime 对象
    
    Returns:
        转换后的 UTC 时间，如果输入为 None 则返回 None
    """
    if dt is None:
        return None
    
    # 如果没有时区信息，假设是北京时间
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING_TZ)
    
    # 转换为 UTC 时间
    return dt.astimezone(timezone.utc)


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化 datetime 为字符串（北京时间）
    
    Args:
        dt: 要格式化的 datetime 对象
        fmt: 格式化字符串，默认为 "%Y-%m-%d %H:%M:%S"
    
    Returns:
        格式化后的时间字符串
    """
    if dt is None:
        return ""
    
    # 确保是北京时间
    beijing_time = to_beijing(dt)
    return beijing_time.strftime(fmt)


def format_iso(dt: Optional[datetime]) -> str:
    """
    格式化 datetime 为 ISO 格式字符串（北京时间）
    
    Args:
        dt: 要格式化的 datetime 对象
    
    Returns:
        ISO 格式的时间字符串
    """
    if dt is None:
        return ""
    
    # 确保是北京时间
    beijing_time = to_beijing(dt)
    return beijing_time.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """
    解析时间字符串为 datetime 对象（假设为北京时间）
    
    Args:
        dt_str: 时间字符串
    
    Returns:
        解析后的 datetime 对象（包含时区信息）
    """
    # 尝试解析 ISO 格式
    try:
        dt = datetime.fromisoformat(dt_str)
        # 如果没有时区信息，假设是北京时间
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BEIJING_TZ)
        return dt
    except ValueError:
        pass
    
    # 尝试解析常见格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return dt.replace(tzinfo=BEIJING_TZ)
        except ValueError:
            continue
    
    raise ValueError(f"无法解析时间字符串: {dt_str}")


def get_date_range(days: int = 30) -> tuple[datetime, datetime]:
    """
    获取日期范围（北京时间）
    
    Args:
        days: 天数，默认为 30 天
    
    Returns:
        (开始时间, 结束时间) 的元组
    """
    end_time = now_beijing()
    start_time = end_time - timedelta(days=days)
    return start_time, end_time


# 向后兼容的别名
get_beijing_now = now_beijing
get_utc_now = utc_now
convert_to_beijing = to_beijing
convert_to_utc = to_utc
format_time = format_datetime
