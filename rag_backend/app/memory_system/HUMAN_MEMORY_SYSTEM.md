
# 人类记忆系统设计文档

## 📋 概述

本文档介绍基于认知科学的人类记忆模块设计，这是一个完全自研的记忆系统，用于提升 RAG 系统的上下文管理能力。

## 🧠 设计理念

### 为什么需要人类记忆模块？

传统 RAG 系统的问题：
1. **简单的历史记录查询** - 只是从数据库读取消息，没有记忆管理
2. **缺少上下文优先级** - 所有历史消息权重相同
3. **无法处理长对话** - 超过 token 限制就截断
4. **缺少知识积累** - 每次对话都是独立的，无法学习用户偏好

### 人类记忆模型

基于认知心理学的 Atkinson-Shiffrin 记忆模型：

```
感知输入 → 工作记忆 → 情景记忆 → 语义记忆
(Sensory)  (Working)   (Episodic)  (Semantic)
```

## 🏗️ 架构设计

### 三层记忆架构

```
┌─────────────────────────────────────────────────────────┐
│                    Memory Manager                        │
│                     (记忆管理器)                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Working    │  │   Episodic   │  │   Semantic   │ │
│  │   Memory     │  │    Memory    │  │    Memory    │ │
│  │  (工作记忆)  │  │  (情景记忆)  │  │  (语义记忆)  │ │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤ │
│  │ 容量: 7条    │  │ 容量: 100条  │  │ 容量: 1000条 │ │
│  │ 时效: 30分钟 │  │ 持久化: DB   │  │ 持久化: DB   │ │
│  │ 检索: 全部   │  │ 检索: 向量   │  │ 检索: 向量   │ │
│  │ 用途: 当前   │  │ 用途: 历史   │  │ 用途: 知识   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 1. 工作记忆 (Working Memory)

**特点：**
- 容量小（7±2 条，符合米勒定律）
- 访问速度快
- 不持久化（内存中）
- 自动淘汰旧记忆（FIFO）
- 自动过期（30 分钟未访问）

**用途：**
- 存储当前对话的上下文
- 提供给 LLM 的直接输入
- 快速访问最近的对话

**实现：**
```python
class WorkingMemory(BaseMemory):
    def __init__(self, capacity=7, expire_minutes=30):
        # FIFO 队列
        # 自动过期机制
        # 不需要向量检索
```

### 2. 情景记忆 (Episodic Memory)

**特点：**
- 容量中等（100 条/会话）
- 持久化到 PostgreSQL
- 支持向量检索
- 按会话组织
- 自动压缩和摘要

**用途：**
- 存储完整的对话历史
- 检索相似的历史对话
- 生成会话摘要
- 提取知识到语义记忆

**实现：**
```python
class EpisodicMemory(BaseMemory):
    def __init__(self, session_id, user_id, capacity=100):
        # 持久化到 chat_messages 表
        # 支持向量检索
        # 自动压缩（保留 20% + 摘要 60% + 删除 20%）
```

### 3. 语义记忆 (Semantic Memory)

**特点：**
- 容量大（1000+ 条）
- 高度结构化
- 向量检索
- 跨会话共享
- 知识图谱（未来扩展）

**用途：**
- 存储用户的知识偏好
- 存储常见问题和答案
- 存储领域知识
- 支持知识推理

**实现：**
```python
class SemanticMemory(BaseMemory):
    def __init__(self, user_id, capacity=1000):
        # 向量检索
        # 知识提取
        # 知识图谱
        # 去重合并
```

## 🔄 工作流程

### 消息添加流程

```
用户输入
    ↓
创建 MemoryItem
    ↓
添加到工作记忆 (立即可用)
    ↓
添加到情景记忆 (持久化)
    ↓
如果重要性 >= 0.8
    ↓
添加到语义记忆 (知识积累)
```

### 上下文检索流程

```
用户查询
    ↓
生成查询向量
    ↓
┌─────────────┬─────────────┬─────────────┐
│ 工作记忆    │ 情景记忆    │ 语义记忆    │
│ (全部返回)  │ (向量检索)  │ (向量检索)  │
└─────────────┴─────────────┴─────────────┘
    ↓
合并结果
    ↓
格式化上下文
    ↓
传递给 LLM
```

### 记忆巩固流程

```
定期触发 (每小时/会话结束)
    ↓
清理工作记忆 (删除过期)
    ↓
压缩情景记忆 (摘要旧对话)
    ↓
提取知识到语义记忆 (高频问题)
    ↓
清理低价值记忆 (衰减因子 < 0.1)
```

## 📊 核心算法

### 1. 记忆衰减算法

基于艾宾浩斯遗忘曲线：

```python
def decay(self, time_delta_hours: float):
    """
    R = e^(-t/S)
    R: 记忆保持率
    t: 时间间隔
    S: 记忆强度 = 重要性 × (1 + log(1 + 访问次数))
    """
    strength = self.importance * (1 + math.log(1 + self.access_count))
    self.decay_factor = math.exp(-time_delta_hours / (strength * 24))
```

### 2. 相关性评分算法

综合多个因素：

```python
def get_relevance_score(self, query_embedding):
    """
    最终分数 = 
        语义相似度 × 40% +
        衰减因子 × 30% +
        重要性 × 20% +
        访问频率 × 10%
    """
    similarity = cosine_similarity(self.embedding, query_embedding)
    access_score = min(1.0, self.access_count / 10)
    
    return (
        similarity * 0.4 +
        self.decay_factor * 0.3 +
        self.importance * 0.2 +
        access_score * 0.1
    )
```

### 3. 记忆压缩算法

三段式压缩：

```python
async def _compress(self):
    """
    保留最近 20% (完整)
    摘要中间 60% (压缩)
    删除最旧 20% (遗忘)
    """
    total = len(self.memories)
    keep_recent = int(total * 0.2)
    compress_middle = int(total * 0.6)
    
    # 保留 + 摘要 + 删除
```

## 💾 数据模型

### MemoryItem (记忆项)

```python
@dataclass
class MemoryItem:
    id: str                          # 唯一标识
    content: str                     # 内容
    role: str                        # 角色 (user/assistant/system)
    timestamp: datetime              # 创建时间
    importance: float                # 重要性 (0.0-1.0)
    access_count: int                # 访问次数
    last_access: datetime            # 最后访问时间
    decay_factor: float              # 衰减因子 (0.0-1.0)
    metadata: Dict[str, Any]         # 元数据
    embedding: Optional[List[float]] # 向量嵌入
```

### 数据库表

复用现有表，无需新建：

- `chat_sessions` - 会话信息
- `chat_messages` - 消息记录（情景记忆）
- 未来可扩展：`semantic_knowledge` - 语义知识表

## 🎯 与传统 RAG 的对比

| 维度 | 传统 RAG | 人类记忆模块 |
|------|---------|-------------|
| **历史管理** | 简单查询数据库 | 三层记忆架构 |
| **上下文选择** | 全部或截断 | 智能检索和排序 |
| **记忆衰减** | 无 | 艾宾浩斯曲线 |
| **知识积累** | 无 | 语义记忆提取 |
| **长对话处理** | Token 限制 | 自动压缩和摘要 |
| **检索策略** | 单一向量检索 | 分层检索 + 相关性评分 |
| **性能** | 每次查询数据库 | 工作记忆缓存 |

## 🚀 使用示例

### 基础使用

```python
from app.memory_system import MemoryManager

# 1. 初始化记忆管理器
memory_manager = MemoryManager(
    session_id="session_123",
    user_id="user_456"
)

# 2. 添加消息
await memory_manager.add_message(
    role="user",
    content="什么是 Python？",
    importance=0.8
)

await memory_manager.add_message(
    role="assistant",
    content="Python 是一种高级编程语言...",
    importance=0.9
)

# 3. 检索上下文
context = await memory_manager.get_formatted_context(
    query="Python 的特点是什么？",
    max_tokens=2000
)

# 4. 获取 LLM 上下文
llm_context = memory_manager.get_context_for_llm()

# 5. 记忆巩固
await memory_manager.consolidate_memories()

# 6. 获取统计信息
stats = await memory_manager.get_memory_statistics()
```

### 集成到 Agent

```python
from app.memory_system import MemoryManager
from app.agent_framework import ReActAgent

class EnhancedAgentService:
    def __init__(self):
        self.agent = ReActAgent(...)
        self.memory_manager = None
    
    async def chat(self, user_input, session_id, user_id):
        # 初始化记忆管理器
        if not self.memory_manager:
            self.memory_manager = MemoryManager(session_id, user_id)
        
        # 添加用户消息
        await self.memory_manager.add_message("user", user_input)
        
        # 获取上下文
        context = await self.memory_manager.get_formatted_context(user_input)
        
        # 调用 Agent
        response = await self.agent.run(
            user_input=user_input,
            context=context
        )
        
        # 保存 AI 回复
        await self.memory_manager.add_message("assistant", response)
        
        return response
```

## 📈 性能优化

### 1. 缓存策略

- 工作记忆：内存缓存，无需数据库查询
- 情景记忆：延迟加载，首次访问时加载
- 语义记忆：向量索引，快速检索

### 2. 异步处理

- 所有数据库操作异步执行
- 向量生成异步执行
- 记忆巩固后台任务

### 3. 批量操作

- 批量生成向量嵌入
- 批量插入数据库
- 批量检索记忆

## 🔮 未来扩展

### 1. 知识图谱

```python
class SemanticMemory:
    async def build_knowledge_graph(self):
        # 实体识别
        # 关系抽取
        # 图谱构建
        # 图谱推理
```

### 2. 多模态记忆

```python
class MultimodalMemory:
    # 支持图片、音频、视频
    # 跨模态检索
    # 多模态融合
```

### 3. 联邦记忆

```python
class FederatedMemory:
    # 跨用户知识共享
    # 隐私保护
    # 协同学习
```

## 🎓 技术亮点

### 1. 完全自研

- 不依赖 LangChain Memory
- 展示对记忆系统的深度理解
- 可控性和可扩展性强

### 2. 认知科学基础

- 基于 Atkinson-Shiffrin 模型
- 艾宾浩斯遗忘曲线
- 米勒定律（7±2）

### 3. 工程实践

- 异步架构
- 数据库持久化
- 向量检索
- 自动巩固

### 4. 面试价值

- 体现系统设计能力
- 体现算法理解
- 体现工程实践
- 体现创新思维

## 📝 总结

人类记忆模块是对传统 RAG 系统的重大升级：

1. **三层记忆架构** - 工作记忆、情景记忆、语义记忆
2. **智能记忆管理** - 衰减、巩固、压缩、提取
3. **高效检索策略** - 分层检索、相关性评分
4. **完全自研实现** - 不依赖第三方框架

这套系统不仅提升了 RAG 的性能，更重要的是展示了对 Agent 和记忆系统的深度掌握，具有很高的技术价值和面试价值。
