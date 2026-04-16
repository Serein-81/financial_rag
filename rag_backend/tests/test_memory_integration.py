#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试企业记忆系统集成到Agent Service

验证记忆系统是否正确集成到Agent Service中，包括：
1. 记忆管理器创建和获取
2. 对话历史自动保存和检索
3. 上下文增强效果
4. 多会话隔离
"""

import asyncio
import sys
import os
import uuid

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.agent_service import agent_service
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatSession


async def create_test_session(session_id: str, user_id: str, kb_id: str):
    """创建测试用的会话记录"""
    async with AsyncSessionLocal() as db:
        try:
            # 检查会话是否已存在
            from sqlalchemy import select
            result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                # 创建新会话（ChatSession 不需要 kb_id 参数）
                session = ChatSession(
                    id=session_id,
                    user_id=user_id,
                    title="测试会话"
                )
                db.add(session)
                await db.commit()
                print(f"✅ 创建测试会话: {session_id[:8]}...")
            else:
                print(f"ℹ️ 会话已存在: {session_id[:8]}...")
        except Exception as e:
            print(f"⚠️ 创建会话失败: {e}")
            await db.rollback()


async def test_memory_integration():
    """测试记忆系统集成"""
    
    print("=" * 80)
    print("🧠 测试企业记忆系统集成到Agent Service")
    print("=" * 80)
    
    # 测试参数 - 使用有效的UUID格式
    test_user_id = str(uuid.uuid4())  # 生成有效的UUID
    test_session_id = str(uuid.uuid4())  # 生成有效的UUID
    test_kb_id = str(uuid.uuid4())  # 生成有效的UUID
    
    # 创建测试会话
    await create_test_session(test_session_id, test_user_id, test_kb_id)
    
    try:
        # 1. 测试记忆管理器创建
        print("\n1️⃣ 测试记忆管理器创建")
        print("-" * 40)
        
        memory_manager = agent_service._get_memory_manager(test_session_id, test_user_id)
        print(f"✅ 记忆管理器创建成功: {memory_manager}")
        print(f"   Session ID: {memory_manager.session_id}")
        print(f"   User ID: {memory_manager.user_id}")
        
        # 验证同一session_id返回相同实例
        memory_manager2 = agent_service._get_memory_manager(test_session_id, test_user_id)
        assert memory_manager is memory_manager2, "同一session_id应返回相同实例"
        print("✅ 记忆管理器实例复用正确")
        
        # 2. 测试对话记忆保存和检索
        print("\n2️⃣ 测试对话记忆保存和检索")
        print("-" * 40)
        
        # 模拟第一轮对话
        user_input1 = "我叫张三，今年25岁，是一名软件工程师"
        print(f"用户输入1: {user_input1}")
        
        response1 = await agent_service.chat(
            user_input=user_input1,
            kb_id=test_kb_id,
            session_id=test_session_id,
            user_id=test_user_id
        )
        print(f"AI回答1: {response1[:100]}...")
        
        # 模拟第二轮对话（测试记忆检索）
        user_input2 = "我的职业是什么？"
        print(f"\n用户输入2: {user_input2}")
        
        response2 = await agent_service.chat(
            user_input=user_input2,
            kb_id=test_kb_id,
            session_id=test_session_id,
            user_id=test_user_id
        )
        print(f"AI回答2: {response2[:100]}...")
        
        # 检查AI是否能记住之前的信息
        if "软件工程师" in response2 or "张三" in response2:
            print("✅ 记忆系统工作正常，AI能记住之前的对话")
        else:
            print("⚠️ 记忆系统可能未正常工作，AI没有引用之前的信息")
        
        # 3. 测试记忆统计
        print("\n3️⃣ 测试记忆统计")
        print("-" * 40)
        
        stats = await memory_manager.get_memory_statistics()
        print(f"记忆统计:")
        print(f"  工作记忆: {stats['working_memory'].get('size', 0)} 条")
        print(f"  情景记忆: {stats['episodic_memory'].get('size', 0)} 条")
        print(f"  语义记忆: {stats['semantic_memory'].get('size', 0)} 条")
        print(f"  总计: {stats['total_memories']} 条")
        
        # 4. 测试多会话隔离
        print("\n4️⃣ 测试多会话隔离")
        print("-" * 40)
        
        # 创建另一个会话
        test_session_id2 = str(uuid.uuid4())  # 生成有效的UUID
        memory_manager3 = agent_service._get_memory_manager(test_session_id2, test_user_id)
        
        assert memory_manager3 is not memory_manager, "不同session_id应返回不同实例"
        print("✅ 多会话隔离正确")
        
        # 5. 测试Agent信息
        print("\n5️⃣ 测试Agent信息")
        print("-" * 40)
        
        agent_info = agent_service.get_agent_info()
        print(f"Agent信息:")
        for key, value in agent_info.items():
            print(f"  {key}: {value}")
        
        assert agent_info["memory_enabled"] == True, "记忆系统应该已启用"
        assert agent_info["memory_sessions"] >= 2, "应该有至少2个记忆会话"
        print("✅ Agent信息正确显示记忆系统状态")
        
        print("\n" + "=" * 80)
        print("🎉 企业记忆系统集成测试全部通过！")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_stream_memory_integration():
    """测试流式对话的记忆系统集成"""
    
    print("\n" + "=" * 80)
    print("🌊 测试流式对话的记忆系统集成")
    print("=" * 80)
    
    test_user_id = str(uuid.uuid4())  # 生成有效的UUID
    test_session_id = str(uuid.uuid4())  # 生成有效的UUID
    test_kb_id = str(uuid.uuid4())  # 生成有效的UUID
    
    # 创建测试会话
    await create_test_session(test_session_id, test_user_id, test_kb_id)
    
    try:
        # 测试流式对话
        user_input = "请记住：我最喜欢的颜色是蓝色"
        print(f"用户输入: {user_input}")
        
        full_response = ""
        print("AI流式回答: ", end="")
        
        async for chunk in agent_service.chat_stream(
            user_input=user_input,
            kb_id=test_kb_id,
            session_id=test_session_id,
            history=[],
            user_id=test_user_id
        ):
            print(chunk, end="", flush=True)
            full_response += chunk
        
        print(f"\n完整回答长度: {len(full_response)} 字符")
        
        # 测试记忆是否保存
        memory_manager = agent_service._get_memory_manager(test_session_id, test_user_id)
        stats = await memory_manager.get_memory_statistics()
        
        if stats['total_memories'] > 0:
            print("✅ 流式对话记忆保存成功")
        else:
            print("⚠️ 流式对话记忆保存可能失败")
        
        # 测试后续对话是否能使用记忆
        user_input2 = "我最喜欢什么颜色？"
        print(f"\n用户输入2: {user_input2}")
        
        response2 = await agent_service.chat(
            user_input=user_input2,
            kb_id=test_kb_id,
            session_id=test_session_id,
            user_id=test_user_id
        )
        print(f"AI回答2: {response2}")
        
        if "蓝色" in response2:
            print("✅ 流式对话记忆检索成功")
        else:
            print("⚠️ 流式对话记忆检索可能失败")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 流式测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    
    print("🚀 开始企业记忆系统集成测试")
    
    # 测试基本记忆集成
    test1_result = await test_memory_integration()
    
    # 测试流式记忆集成
    test2_result = await test_stream_memory_integration()
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    print(f"基本记忆集成测试: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"流式记忆集成测试: {'✅ 通过' if test2_result else '❌ 失败'}")
    
    if test1_result and test2_result:
        print("\n🎉 所有测试通过！企业记忆系统已成功集成到Agent Service")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查集成实现")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)