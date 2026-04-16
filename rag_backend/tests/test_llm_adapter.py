#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 适配器测试脚本

测试 LLM 适配器的功能和切换
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agent_framework.llm import create_llm_adapter, LLMAdapterFactory
from app.services.llm_service import LLMService
from app.core.config import settings


async def test_default_adapter():
    """测试默认适配器"""
    print("="*60)
    print("1️⃣ 测试默认适配器")
    print("="*60)
    
    print(f"\n当前配置:")
    print(f"  - 提供商: {settings.LLM_PROVIDER}")
    print(f"  - 模型: {settings.ZHIPU_MODEL}")
    
    # 创建 LLM 服务
    llm_service = LLMService()
    
    # 测试非流式生成
    print(f"\n📝 测试非流式生成...")
    answer = await llm_service.get_answer(
        query="什么是人工智能？请用一句话回答。",
        context_chunks=["人工智能（AI）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。"],
        history=[]
    )
    
    print(f"\n回答: {answer}\n")


async def test_stream_generation():
    """测试流式生成"""
    print("="*60)
    print("2️⃣ 测试流式生成")
    print("="*60)
    
    llm_service = LLMService()
    
    print(f"\n🌊 流式生成回答...")
    print("回答: ", end="", flush=True)
    
    for chunk in llm_service.get_answer_stream(
        query="用一句话介绍Python编程语言",
        context_chunks=[],
        history=[]
    ):
        print(chunk, end="", flush=True)
    
    print("\n")


async def test_with_context():
    """测试带上下文的回答"""
    print("="*60)
    print("3️⃣ 测试带上下文的回答")
    print("="*60)
    
    llm_service = LLMService()
    
    context_chunks = [
        "FastAPI 是一个现代、快速（高性能）的 Web 框架，用于构建 API。",
        "FastAPI 基于 Python 3.6+ 的类型提示，提供自动的 API 文档生成。",
        "FastAPI 的性能可以与 NodeJS 和 Go 相媲美。"
    ]
    
    print(f"\n📚 参考资料:")
    for i, chunk in enumerate(context_chunks, 1):
        print(f"  {i}. {chunk}")
    
    print(f"\n❓ 问题: FastAPI 有什么特点？")
    
    answer = await llm_service.get_answer(
        query="FastAPI 有什么特点？",
        context_chunks=context_chunks,
        history=[]
    )
    
    print(f"\n💡 回答: {answer}\n")


async def test_with_history():
    """测试带历史记录的对话"""
    print("="*60)
    print("4️⃣ 测试带历史记录的对话")
    print("="*60)
    
    llm_service = LLMService()
    
    history = [
        {"role": "user", "content": "什么是机器学习？"},
        {"role": "assistant", "content": "机器学习是人工智能的一个分支，它使计算机能够从数据中学习并改进性能，而无需明确编程。"},
        {"role": "user", "content": "它有哪些应用？"},
        {"role": "assistant", "content": "机器学习广泛应用于图像识别、自然语言处理、推荐系统、自动驾驶等领域。"}
    ]
    
    print(f"\n💬 对话历史:")
    for msg in history:
        role = "用户" if msg["role"] == "user" else "助手"
        print(f"  {role}: {msg['content']}")
    
    print(f"\n❓ 新问题: 深度学习和机器学习有什么区别？")
    
    answer = await llm_service.get_answer(
        query="深度学习和机器学习有什么区别？",
        context_chunks=[],
        history=history
    )
    
    print(f"\n💡 回答: {answer}\n")


async def test_adapter_info():
    """测试适配器信息"""
    print("="*60)
    print("5️⃣ 测试适配器信息")
    print("="*60)
    
    # 获取支持的提供商
    providers = LLMAdapterFactory.get_supported_providers()
    print(f"\n📋 支持的提供商: {', '.join(providers)}")
    
    # 获取当前提供商
    current = LLMAdapterFactory.get_current_provider()
    print(f"✅ 当前提供商: {current}")
    
    # 创建适配器并获取信息
    adapter = create_llm_adapter()
    info = adapter.get_model_info()
    
    print(f"\n🔍 适配器详情:")
    print(f"  - 类型: {info['adapter_type']}")
    print(f"  - 模型: {info['model_name']}")
    print(f"  - 配置: {info['config']}")
    print()


async def main():
    """主函数"""
    print("\n🚀 开始测试 LLM 适配器...")
    print()
    
    try:
        # 测试1：默认适配器
        await test_default_adapter()
        
        # 测试2：流式生成
        await test_stream_generation()
        
        # 测试3：带上下文
        await test_with_context()
        
        # 测试4：带历史记录
        await test_with_history()
        
        # 测试5：适配器信息
        await test_adapter_info()
        
        print("="*60)
        print("✅ 所有测试完成！")
        print("="*60)
        print()
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
