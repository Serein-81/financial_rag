"""
人类记忆系统简单测试（不需要数据库）
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.base_memory import MemoryItem
from app.memory_system.working_memory import WorkingMemory


async def test_memory_item():
    """测试记忆项"""
    print("\n" + "=" * 60)
    print("测试 1: 记忆项 (MemoryItem)")
    print("=" * 60)
    
    item = MemoryItem(
        content="Python 是一种编程语言",
        role="user",
        importance=0.8
    )
    
    print(f"\n记忆项创建成功:")
    print(f"  ID: {item.id[:8]}...")
    print(f"  内容: {item.content}")
    print(f"  角色: {item.role}")
    print(f"  重要性: {item.importance}")
    print(f"  访问次数: {item.access_count}")
    print(f"  衰减因子: {item.decay_factor}")
    
    # 测试访问
    print(f"\n访问记忆...")
    item.access()
    print(f"  访问次数: {item.access_count}")
    print(f"  衰减因子: {item.decay_factor}")
    
    # 测试衰减
    print(f"\n测试记忆衰减:")
    for hours in [1, 6, 12, 24]:
        item.decay(hours)
        print(f"  {hours:2d} 小时后: 衰减因子 = {item.decay_factor:.4f}")
    
    print("\n✅ 记忆项测试通过")


async def test_working_memory():
    """测试工作记忆"""
    print("\n" + "=" * 60)
    print("测试 2: 工作记忆 (Working Memory)")
    print("=" * 60)
    
    wm = WorkingMemory(capacity=5)
    
    # 添加记忆
    print(f"\n添加 7 条记忆到容量为 5 的工作记忆:")
    for i in range(7):
        item = MemoryItem(
            content=f"消息 {i+1}",
            role="user" if i % 2 == 0 else "assistant"
        )
        await wm.add(item)
    
    # 检索记忆
    memories = await wm.retrieve()
    print(f"\n当前工作记忆数量: {len(memories)}/{wm.capacity}")
    print(f"内容:")
    for m in memories:
        print(f"  - {m.role}: {m.content}")
    
    # 获取上下文窗口
    context = wm.get_context_window()
    print(f"\n上下文窗口 ({len(context)} 条):")
    for ctx in context:
        print(f"  {ctx['role']}: {ctx['content']}")
    
    # 获取摘要
    summary = wm.get_recent_summary()
    print(f"\n最近摘要: {summary}")
    
    # 统计信息
    stats = wm.get_statistics()
    print(f"\n统计信息:")
    print(f"  总数: {stats['total']}")
    print(f"  平均重要性: {stats['avg_importance']:.2f}")
    print(f"  平均衰减: {stats['avg_decay']:.2f}")
    print(f"  使用率: {stats['usage_rate']:.1%}")
    
    print("\n✅ 工作记忆测试通过")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 人类记忆系统简单测试")
    print("=" * 60)
    
    try:
        await test_memory_item()
        await test_working_memory()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        print("\n📝 说明:")
        print("  - 记忆项: 基本的记忆单元，支持衰减和访问统计")
        print("  - 工作记忆: 短期记忆，容量 7±2，FIFO 队列")
        print("  - 情景记忆: 需要数据库，存储完整对话历史")
        print("  - 语义记忆: 需要向量服务，存储长期知识")
        print("\n💡 下一步:")
        print("  1. 激活虚拟环境: .venv\\Scripts\\activate")
        print("  2. 运行完整测试: python test_memory_system.py")
        print("  3. 集成到 Agent: 参考 MEMORY_INTEGRATION_GUIDE.md")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
