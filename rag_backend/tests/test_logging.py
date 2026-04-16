"""
测试统一的日志系统

运行方法：python test_logging.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath('rag_backend'))

from app.utils.logging_config import setup_logging, get_logger, LogFormat, get_app_logger, STDIOAwareLogger

def test_basic_logging():
    """测试基础日志功能"""
    print("\n" + "="*60)
    print("测试 1: 基础日志功能")
    print("="*60)
    
    setup_logging(
        log_level="DEBUG",
        log_dir="logs",
        log_file="test.log",
        enable_console=True,
        enable_file=True,
        format_type=LogFormat.DETAILED
    )
    
    logger = get_logger(__name__)
    
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    
    print("\n✅ 基础日志功能测试完成")

def test_stdio_safe():
    """测试 STDIO 安全模式"""
    print("\n" + "="*60)
    print("测试 2: STDIO 安全模式")
    print("="*60)
    
    stdio_logger = get_logger("stdio_test", stdio_safe=True)
    
    stdio_logger.info("这是 STDIO 安全日志（应该输出到 stderr）")
    
    print("\n✅ STDIO 安全模式测试完成")
    print("注意：上面应该看到 INFO 级别的日志输出")

def test_app_logger():
    """测试 AppLogger 封装"""
    print("\n" + "="*60)
    print("测试 3: AppLogger 封装")
    print("="*60)
    
    app_logger = get_app_logger("app_test")
    
    app_logger.info("用户登录成功", user_id="123", action="login")
    app_logger.log_user_action("456", "logout", "success")
    app_logger.log_api_request("POST", "/api/users", status_code=201)
    app_logger.log_database_query("SELECT", "users", 15.5)
    
    print("\n✅ AppLogger 测试完成")

def test_log_levels():
    """测试不同日志级别"""
    print("\n" + "="*60)
    print("测试 4: 不同日志级别")
    print("="*60)
    
    logger = get_logger("level_test")
    
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    for level in levels:
        getattr(logger, level.lower())(f"测试 {level} 级别")
    
    print("\n✅ 日志级别测试完成")

def test_with_extra():
    """测试带额外数据的日志"""
    print("\n" + "="*60)
    print("测试 5: 带额外数据的日志")
    print("="*60)
    
    logger = get_logger("extra_test")
    
    logger.info(
        "用户执行了操作",
        extra={
            "user_id": "123",
            "action": "login",
            "ip": "192.168.1.1",
            "user_agent": "Mozilla/5.0"
        }
    )
    
    print("\n✅ 带额外数据日志测试完成")

def test_exception_logging():
    """测试异常日志"""
    print("\n" + "="*60)
    print("测试 6: 异常日志")
    print("="*60)
    
    logger = get_logger("exception_test")
    
    try:
        result = 1 / 0
    except Exception as e:
        logger.exception(f"捕获到异常: {e}")
    
    print("\n✅ 异常日志测试完成")

if __name__ == "__main__":
    print("\n" + "🎯"*30)
    print("开始测试统一的日志系统")
    print("🎯"*30 + "\n")
    
    test_basic_logging()
    test_stdio_safe()
    test_app_logger()
    test_log_levels()
    test_with_extra()
    test_exception_logging()
    
    print("\n" + "🎉"*30)
    print("所有测试完成！")
    print("🎉"*30 + "\n")
    print("请检查 logs/test.log 文件，验证日志是否正确写入。\n")
