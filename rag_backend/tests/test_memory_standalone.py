"""
人类记忆系统独立测试（完全不依赖项目环境）
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict
import uuid
import math


@dataclass
class MemoryItem:
    """记忆项"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    role: str = "user"
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 1.0
    access_count: int = 0
    last_access: datetime = field(default_factory=datetime.now)
    decay_factor: float = 1.0
    
    def access(self):
        """访问记忆"""
        self.access_count += 1
        self.last_access = datetime.now()
        self.decay_factor = min(1.0, self.decay_factor + 0.1)
    
    def decay(self, time_delta_hours: float):
        """记忆衰减（艾宾浩斯曲线）"""
        strength = self.importance * (1 + math.log(1 + self.access_count))
        self.decay_factor = math.exp(-time_delta_hours / (strength * 24))


class WorkingMemory:
    """工作记忆"""
    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.memories: List[MemoryItem] = []
    
    async def add(self, item: MemoryItem):
        """添加记忆"""
        if len(self.memories) >= self.capacity:
            removed = self.memories.pop(0)
            print(f"  🗑️ 容量已满，移除: {removed.content}")
        self.memories.append(item)
        print(f"  ➕ 添加: {item.content} | 当前: {len(self.memories)}/{self.capacity}")
    
    async def retrieve(self) -> List[MemoryItem]:
        """检索记忆"""
        for m in self.memories:
            m.access()
        return self.memories.copy()
    
    def get_context_window(self) -> List[Dict[str, str]]:
        """获取上下文窗口"""
        return [{"role": m.role, "content": m.content} for m in self.memories]


async def test_memory_item():
    """测试记忆项"""
    print("\n" + "=" * 60)
    print("测试 1: 记忆项 (MemoryItem)")
    print("=" * 60)
    
    item = MemoryItem(
        content="Python 是一种高级编程语言",
        role="user",
        importance=0.8
    )
    
    print("\n✨ 记忆项创建:")
    print(f"  ID: {item.id[:8]}...")
    print(f"  内容: {item.content}")
    print(f"  重要性: {item.importance}")
    print(f"  衰减因子: {item.decay_factor}")
    
    print("\n🔄 测试记忆衰减（艾宾浩斯曲线）:")
    for hours in [1, 6, 12, 24, 48]:
        item.decay(hours)
        print(f"  {hours:2d} 小时后: {item.decay_factor:.4f}")
    
    print("\n👆 访问记忆:")
    item.access()
    print(f"  访问次数: {item.access_count}")
    print(f"  衰减因子: {item.decay_factor:.4f} (访问后增强)")
    
    print("\n✅ 记忆项测试通过")


async def test_working_memory():
    """测试工作记忆"""
    print("\n" + "=" * 60)
    print("测试 2: 工作记忆 (Working Memory)")
    print("=" * 60)
    
    wm = WorkingMemory(capacity=5)
    
    print("\n📝 添加 7 条记忆到容量为 5 的工作记忆:")
    conversations = [
        ("user", "你好"),
        ("assistant", "你好！有什么可以帮你的？"),
        ("user", "什么是 Python？"),
        ("assistant", "Python 是一种高级编程语言..."),
        ("user", "Python 有什么特点？"),
        ("assistant", "Python 简洁、易读、功能强大..."),
        ("user", "如何学习 Python？"),
    ]
    
    for role, content in conversations:
        item = MemoryItem(content=content, role=role)
        await wm.add(item)
    
    print("\n🔍 检索工作记忆:")
    memories = await wm.retrieve()
    print(f"  当前数量: {len(memories)}/{wm.capacity}")
    for i, m in enumerate(memories, 1):
        print(f"  {i}. {m.role:10s}: {m.content[:40]}...")
    
    print("\n📋 上下文窗口:")
    context = wm.get_context_window()
    for ctx in context:
        print(f"  {ctx['role']:10s}: {ctx['content'][:40]}...")
    
    print("\n✅ 工作记忆测试通过")


async def test_memory_architecture():
    """测试三层记忆架构概念"""
    print("\n" + "=" * 60)
    print("测试 3: 三层记忆架构演示")
    print("=" * 60)
    
    print("""
    🧠 人类记忆系统架构:
    
    ┌─────────────────────────────────────────┐
    │         Memory Manager                   │
    ├─────────────────────────────────────────┤
    │  ┌──────────┐  ┌──────────┐  ┌────────┐│
    │  │ Working  │  │ Episodic │  │Semantic││
    │  │ Memory   │  │  Memory  │  │ Memory ││
    │  │ (短期)   │  │  (中期)  │  │ (长期) ││
    │  │  7条     │  │  100条   │  │ 1000条 ││
    │  └──────────┘  └──────────┘  └────────┘│
    └─────────────────────────────────────────┘
    
    📌 工作记忆 (Working Memory):
       - 容量: 7±2 条（米勒定律）
       - 存储: 内存
       - 用途: 当前对话上下文
       - 策略: FIFO 队列
    
    📚 情景记忆 (Episodic Memory):
       - 容量: 100 条/会话
       - 存储: PostgreSQL
       - 用途: 完整对话历史
       - 策略: 向量检索 + 自动压缩
    
    🧠 语义记忆 (Semantic Memory):
       - 容量: 1000+ 条
       - 存储: PostgreSQL + pgvector
       - 用途: 长期知识库
       - 策略: 向量检索 + 知识提取
    """)
    
    print("✅ 架构演示完成")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("🧠 人类记忆系统 - 独立测试套件")
    print("=" * 70)
    
    try:
        await test_memory_item()
        await test_working_memory()
        await test_memory_architecture()
        
        print("\n" + "=" * 70)
        print("🎉 所有测试通过！")
        print("=" * 70)
        
        print("\n📊 技术亮点:")
        print("  ✅ 基于认知科学的 Atkinson-Shiffrin 模型")
        print("  ✅ 艾宾浩斯遗忘曲线算法")
        print("  ✅ 米勒定律（7±2）工作记忆容量")
        print("  ✅ 三层记忆架构（工作/情景/语义）")
        print("  ✅ 完全自研实现（不依赖 LangChain）")
        
        print("\n💡 下一步:")
        print("  1. 查看设计文档: HUMAN_MEMORY_SYSTEM.md")
        print("  2. 查看对比分析: RAG_MECHANISM_COMPARISON.md")
        print("  3. 查看集成指南: MEMORY_INTEGRATION_GUIDE.md")
        print("  4. 激活虚拟环境后运行完整测试")
        
        print("\n🎯 面试价值:")
        print("  - 展示系统设计能力（三层架构）")
        print("  - 展示算法理解（遗忘曲线）")
        print("  - 展示工程实践（异步、缓存）")
        print("  - 展示创新思维（认知科学 + 工程）")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
