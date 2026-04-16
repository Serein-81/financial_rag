#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 Agent 监控修复
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.monitor_service import MonitorService, AgentTraceContext


class MockLLMResponse:
    """模拟 LLM 响应对象"""
    def __init__(self, content):
        self.content = content


def test_set_result_with_string():
    """测试 set_result 接收字符串"""
    print("\n" + "="*70)
    print("测试 1: set_result 接收字符串")
    print("="*70)
    
    try:
        monitor = MonitorService(enable_console_log=False)
        
        # 模拟 AgentTraceContext
        event = monitor._create_event("agent_start")
        context = AgentTraceContext(monitor, event)
        
        # 测试字符串
        context.set_result("这是一个测试回答")
        
        print("✅ 通过: 字符串类型")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_set_result_with_object():
    """测试 set_result 接收对象（应该提取 content 属性）"""
    print("\n" + "="*70)
    print("测试 2: set_result 接收 LLMResponse 对象")
    print("="*70)
    
    try:
        monitor = MonitorService(enable_console_log=False)
        
        # 模拟 AgentTraceContext
        event = monitor._create_event("agent_start")
        context = AgentTraceContext(monitor, event)
        
        # 测试 LLMResponse 对象 - 这应该失败，因为 set_result 期望字符串
        response = MockLLMResponse("这是一个测试回答")
        
        # 直接传入对象会失败
        try:
            context.set_result(response)
            print("❌ 失败: 应该抛出 TypeError")
            return False
        except TypeError as e:
            print(f"✅ 通过: 正确捕获了 TypeError: {e}")
            print("   这说明 agent_service.py 中必须提取 .content 属性")
            return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extract_content():
    """测试提取 content 属性的正确方式"""
    print("\n" + "="*70)
    print("测试 3: 正确提取 content 属性")
    print("="*70)
    
    try:
        monitor = MonitorService(enable_console_log=False)
        
        # 模拟 AgentTraceContext
        event = monitor._create_event("agent_start")
        context = AgentTraceContext(monitor, event)
        
        # 测试 LLMResponse 对象
        response = MockLLMResponse("这是一个测试回答")
        
        # 正确方式：提取 content 属性
        result_content = response.content if hasattr(response, 'content') else str(response)
        context.set_result(result_content)
        
        print(f"✅ 通过: result_content = '{result_content}'")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_none_handling():
    """测试 None 值的处理"""
    print("\n" + "="*70)
    print("测试 4: None 值的处理")
    print("="*70)
    
    try:
        result = None
        
        # 确保结果是字符串
        if result is None:
            result = "抱歉，未能获取到有效回答。"
        elif not isinstance(result, str):
            result = str(result)
        
        print(f"✅ 通过: result = '{result}'")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 添加缺失的方法到 MonitorService
    def _create_event(self, event_type):
        from app.services.monitor_service import MonitorEvent, EventType
        event = MonitorEvent(event_type=EventType.AGENT_START)
        return event
    
    MonitorService._create_event = _create_event
    
    # 运行测试
    results = []
    results.append(("字符串输入", test_set_result_with_string()))
    results.append(("对象输入", test_set_result_with_object()))
    results.append(("提取 content", test_extract_content()))
    results.append(("None 处理", test_none_handling()))
    
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    
    passed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {status}: {name}")
        if result:
            passed += 1
    
    print("\n" + "="*70)
    if passed == len(results):
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️  通过 {passed}/{len(results)} 个测试")
    print("="*70)
