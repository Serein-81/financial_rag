"""
情景记忆 (Episodic Memory) - 增强版

模拟人类的情景记忆，存储完整的对话会话
特点：
- 容量中等（100-500条）
- 持久化到数据库
- 🆕 支持向量检索和相关性评分
- 🆕 时间衰减因子
- 🆕 重要性权重
- 按会话组织
"""

import math
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, update, func
from .base_memory import BaseMemory, MemoryItem
from app.db import AsyncSessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


def _is_valid_uuid(val: str) -> bool:
    """检查字符串是否为有效的UUID"""
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


class EpisodicMemory(BaseMemory):
    """
    情景记忆 - 完整的对话会话历史
    
    实现策略：
    1. 持久化到 PostgreSQL
    2. 按 session_id 组织
    3. 支持向量检索相似对话
    4. 自动摘要和压缩
    """
    
    def __init__(self, session_id: str, user_id: str, capacity: int = 100):
        """
        初始化情景记忆
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            capacity: 单个会话的最大记忆数
        """
        super().__init__(capacity)
        self.session_id = session_id
        self.user_id = user_id
        self.loaded = False
        logger.info(f"[情景记忆] 初始化 | Session: {session_id[:8]}... | User: {user_id}")
    
    async def load_from_db(self) -> None:
        """从数据库加载会话历史"""
        if self.loaded:
            return
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == self.session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            messages = result.scalars().all()
            
            for msg in messages:
                item = MemoryItem(
                    id=str(msg.id),
                    content=msg.content,
                    role=msg.role,
                    timestamp=msg.created_at,
                    importance=msg.importance or 0.5,  # 🆕 使用数据库中的重要性
                    access_count=msg.access_count or 0,  # 🆕 访问次数
                    last_access=msg.last_accessed or msg.created_at,  # 🆕 最后访问时间
                    embedding=msg.embedding,  # 🆕 向量嵌入
                    metadata={
                        "session_id": self.session_id,
                        "sources": msg.sources or []
                    }
                )
                self.memories.append(item)
            
            self.loaded = True
            logger.info(f"[情景记忆] 从数据库加载 {len(messages)} 条记忆")

    async def _ensure_session_exists(self) -> bool:
        """
        确保会话存在于数据库中，如果不存在则创建

        Returns:
            会话是否存在或创建成功
        """
        if not _is_valid_uuid(self.session_id):
            logger.warning(f"[情景记忆] session_id 不是有效的UUID: {self.session_id}")
            return False

        if not _is_valid_uuid(self.user_id):
            logger.warning(f"[情景记忆] user_id 不是有效的UUID: {self.user_id}")
            return False

        try:
            session_uuid = uuid.UUID(str(self.session_id))
            user_uuid = uuid.UUID(str(self.user_id))

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == session_uuid)
                )
                session = result.scalar_one_or_none()

                if not session:
                    new_session = ChatSession(
                        id=session_uuid,
                        user_id=user_uuid,
                        title=f"Task Session {self.session_id[:8]}..."
                    )
                    db.add(new_session)
                    await db.commit()
                    logger.info(f"[情景记忆] 创建会话: {self.session_id[:8]}...")
                return True

        except (ValueError, KeyError) as e:
            logger.error(f"[情景记忆] 会话创建数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"[情景记忆] 会话创建IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[情景记忆] 会话创建失败: {e}")
            return False

    async def add(self, item: MemoryItem) -> None:
        """
        添加记忆到情景记忆
        
        策略：
        1. 验证输入参数
        2. 生成向量嵌入（如果没有）
        3. 计算重要性评分
        4. 添加到内存
        5. 持久化到数据库
        6. 如果超过容量，触发压缩
        """
        # 1. 输入验证
        if not item or not item.content or not item.content.strip():
            logger.warning("[情景记忆] 跳过空内容记忆")
            return
        
        if item.role not in ["user", "assistant", "system"]:
            logger.warning(f"[情景记忆] 无效角色: {item.role}，设置为 'user'")
            item.role = "user"
        
        # 2. 确保已加载历史记忆
        await self.load_from_db()
        
        # 3. 生成向量嵌入（如果没有）
        # 💡 修复点 5：安全判断数组
        if item.embedding is None or len(item.embedding) == 0:
            try:
                item.embedding = await embedding_service.get_embedding(item.content.strip())
                logger.debug("[情景记忆] 生成向量嵌入")
            except (ValueError, KeyError) as e:
                logger.warning(f"[情景记忆] 向量生成数据错误: {e}")
                item.embedding = None
            except (OSError, IOError) as e:
                logger.warning(f"[情景记忆] 向量生成IO错误: {e}")
                item.embedding = None
            except Exception as e:
                logger.warning(f"[情景记忆] 向量生成失败: {e}")
                item.embedding = None

        # 4. 计算重要性评分
        item.importance = self._calculate_importance(item)

        # 5. 检查会话存在性并持久化到数据库
        session_exists = await self._ensure_session_exists()

        if session_exists:
            try:
                session_uuid = uuid.UUID(str(self.session_id))

                async with AsyncSessionLocal() as db:
                    # 添加会话ID到元数据
                    if "session_id" not in item.metadata:
                        item.metadata["session_id"] = self.session_id

                    db_message = ChatMessage(
                        session_id=session_uuid,
                        role=item.role,
                        content=item.content.strip(),
                        sources=item.metadata.get("sources", []),
                        embedding=item.embedding,  # 🆕 保存向量
                        importance=item.importance,  # 🆕 保存重要性
                        access_count=item.access_count,  # 🆕 保存访问次数
                        last_accessed=item.last_access  # 🆕 保存最后访问时间
                    )
                    db.add(db_message)
                    await db.commit()
                    await db.refresh(db_message)

                    # 更新 item 的 id
                    item.id = str(db_message.id)

                logger.debug(f"[情景记忆] 保存记忆 | ID: {item.id[:8]}...")

            except (ValueError, KeyError) as e:
                logger.error(f"[情景记忆] 数据库保存数据错误: {e}")
            except (OSError, IOError) as e:
                logger.error(f"[情景记忆] 数据库保存IO错误: {e}")
            except Exception as e:
                logger.error(f"[情景记忆] 数据库保存失败: {e}")
                session_exists = False

        # 6. 添加到内存（即使数据库保存失败也添加到内存）
        self.memories.append(item)

        # 7. 如果超过容量，触发压缩
        if len(self.memories) > self.capacity:
            await self._compress()

    async def retrieve(self, query: str, top_k: int = 5,
                      query_embedding: Optional[List[float]] = None) -> List[MemoryItem]:
        """
        增强版检索情景记忆

        策略：
        1. 如果有 query_embedding，使用向量检索 + 相关性评分
        2. 否则返回最近的 top_k 条
        3. 应用时间衰减因子
        4. 更新访问统计
        """
        await self.load_from_db()

        if not self.memories:
            return []

        # 如果有向量，使用智能检索
        if query_embedding:
            return await self._smart_retrieve(query, query_embedding, top_k)
        else:
            # 简单检索：返回最近的 top_k 条
            results = self.memories[-top_k:]

            # 更新访问统计
            await self._update_access_stats([m.id for m in results])

            return results

    async def _smart_retrieve(self, query: str, query_embedding: List[float], top_k: int) -> List[MemoryItem]:
        """
        智能检索：向量相似度 + 时间衰减 + 重要性权重
        """
        scored_memories = []

        for memory in self.memories:
            # 💡 修复点 6：安全判断数组
            if memory.embedding is None or len(memory.embedding) == 0:
                continue

            # 1. 计算向量相似度
            vector_score = self._calculate_cosine_similarity(memory.embedding, query_embedding)

            # 2. 计算时间衰减因子
            time_decay = self._calculate_time_decay(memory.timestamp)

            # 3. 计算重要性权重
            importance_weight = 0.8 + (memory.importance * 0.4)  # 0.8-1.2 范围

            # 4. 计算访问热度加成
            access_boost = min(memory.access_count * 0.05, 0.3)  # 最多30%加成

            # 5. 综合评分
            # 公式：(向量相似度 * 0.7 + 时间衰减 * 0.3) * 重要性权重 + 访问热度
            base_relevance = vector_score * 0.7 + time_decay * 0.3
            final_score = base_relevance * importance_weight + access_boost

            if final_score > 0:
                scored_memories.append((final_score, memory))

        # 按分数排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # 返回 top_k
        results = [m for _, m in scored_memories[:top_k]]

        # 更新访问统计
        await self._update_access_stats([m.id for m in results])

        logger.debug(f"[情景记忆] 检索完成 | 候选: {len(scored_memories)} | 返回: {len(results)}")
        return results

    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm_a = math.sqrt(sum(a * a for a in vec1))
            norm_b = math.sqrt(sum(b * b for b in vec2))

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return dot_product / (norm_a * norm_b)
        except (ValueError, KeyError):
            return 0.0
        except (OSError, IOError):
            return 0.0
        except TypeError:
            return 0.0
        except Exception:
            return 0.0

    def _calculate_time_decay(self, timestamp: datetime) -> float:
        """计算时间衰减因子"""
        from datetime import timezone

        # 💡 修复点 1：统一使用带时区的时间进行计算
        # 如果数据库里的时间是带时区的 (offset-aware)
        if timestamp.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()

        time_diff = now - timestamp

        if time_diff <= timedelta(hours=1):
            return 1.0
        elif time_diff <= timedelta(days=1):
            return 0.8
        elif time_diff <= timedelta(weeks=1):
            return 0.6
        elif time_diff <= timedelta(days=30):
            return 0.4
        else:
            return 0.2

    def _calculate_importance(self, item: MemoryItem) -> float:
        """
        计算记忆重要性（修复版）

        策略：
        - 以外部传入的 item.importance 为基准（memory_manager 已做过智能评估）
        - 角色基准值作为下限参考，取两者中的较小值（避免强制覆盖外部评估）
        - 长文本加成：+0.05
        - 包含关键词加成：+0.05
        """
        # 🔧 修复：不再用角色固定值强制覆盖，而是取外部 importance 与角色基准的较小值
        role_baseline = {
            "user": 0.7,
            "assistant": 0.6,
            "system": 0.3
        }.get(item.role, 0.5)

        # 以外部 importance 为主，角色基准仅作为上限参考
        base_importance = min(item.importance, role_baseline)

        # 长度加成（适度减半，避免通货膨胀）
        length_bonus = 0.05 if len(item.content) > 100 else 0

        # 关键词加成
        keywords = ["重要", "关键", "问题", "错误", "帮助", "谢谢"]
        keyword_bonus = 0.05 if any(kw in item.content for kw in keywords) else 0

        final_importance = min(1.0, base_importance + length_bonus + keyword_bonus)
        return final_importance

    async def _update_access_stats(self, memory_ids: List[str]) -> None:
        """批量更新访问统计"""
        if not memory_ids:
            return

        try:
            async with AsyncSessionLocal() as db:
                # 批量更新数据库
                await db.execute(
                    update(ChatMessage)
                    .where(ChatMessage.id.in_(memory_ids))
                    .values(
                        access_count=ChatMessage.access_count + 1,
                        last_accessed=func.now()
                    )
                )
                await db.commit()

                # 更新内存中的统计
                for memory in self.memories:
                    if memory.id in memory_ids:
                        memory.access()

                logger.debug(f"[情景记忆] 更新访问统计: {len(memory_ids)} 条")

        except (ValueError, KeyError) as e:
            logger.warning(f"[情景记忆] 访问统计更新数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"[情景记忆] 访问统计更新IO错误: {e}")
        except Exception as e:
            logger.warning(f"[情景记忆] 访问统计更新失败: {e}")

    async def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆项"""
        await self.load_from_db()

        for memory in self.memories:
            if memory.id == item_id:
                for key, value in updates.items():
                    if hasattr(memory, key):
                        setattr(memory, key, value)

                # 同步到数据库
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(ChatMessage).where(ChatMessage.id == item_id)
                    )
                    db_message = result.scalar_one_or_none()
                    if db_message:
                        if "content" in updates:
                            db_message.content = updates["content"]
                        await db.commit()

                return True
        return False

    async def forget(self, item_id: str) -> bool:
        """删除指定记忆"""
        await self.load_from_db()

        for i, memory in enumerate(self.memories):
            if memory.id == item_id:
                self.memories.pop(i)

                # 从数据库删除
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(ChatMessage).where(ChatMessage.id == item_id)
                    )
                    db_message = result.scalar_one_or_none()
                    if db_message:
                        await db.delete(db_message)
                        await db.commit()

                logger.debug(f"[情景记忆] 删除记忆: {item_id}")
                return True
        return False

    async def _compress(self) -> None:
        """
        压缩情景记忆

        策略：
        1. 保留最近的 20% 记忆（完整保留）
        2. 中间的 60% 记忆进行摘要
        3. 最旧的 20% 记忆删除或转移到语义记忆
        """
        total = len(self.memories)
        keep_recent = int(total * 0.2)
        compress_middle = int(total * 0.6)

        # 保留最近的
        recent_memories = self.memories[-keep_recent:]

        # 中间的进行摘要（这里简化处理，实际可以调用 LLM 生成摘要）
        middle_memories = self.memories[-(keep_recent + compress_middle):-keep_recent]

        # 创建摘要记忆
        if middle_memories:
            summary_content = f"[摘要] 共 {len(middle_memories)} 条对话"
            summary_item = MemoryItem(
                content=summary_content,
                role="system",
                importance=0.5,
                metadata={"type": "summary", "count": len(middle_memories)}
            )
            recent_memories.insert(0, summary_item)

        # 更新记忆列表
        self.memories = recent_memories

        logger.info(f"[情景记忆] 压缩完成 | 原始: {total} → 压缩后: {len(self.memories)}")

    async def consolidate(self) -> None:
        """
        情景记忆巩固

        专门针对情景记忆的巩固策略：
        1. 清理衰减严重的记忆
        2. 压缩过多的历史对话
        3. 保持会话的连贯性
        4. 更新数据库中的记忆状态
        """
        await self.load_from_db()

        if not self.memories:
            print("📚 [情景记忆] 无记忆需要巩固")
            return

        original_count = len(self.memories)

        # 1. 应用基础巩固逻辑（删除衰减严重的记忆）
        await super().consolidate()

        # 2. 情景记忆特有的巩固：如果记忆过多，进行会话级压缩
        if len(self.memories) > self.capacity * 0.8:  # 超过容量的80%时开始压缩
            await self._compress()

        # 3. 更新记忆的衰减状态
        from datetime import timezone
        for memory in self.memories:
            # 💡 修复点 2：时区安全的时间相减
            if memory.timestamp.tzinfo is not None:
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now()
            # 计算时间差（小时）
            time_diff = (now - memory.timestamp).total_seconds() / 3600
            memory.decay(time_diff)

        consolidated_count = len(self.memories)
        print(f"🔄 [情景记忆] 巩固完成 | 原始: {original_count} → 巩固后: {consolidated_count}")

    async def get_session_summary(self) -> str:
        """
        获取会话摘要

        返回整个会话的简短摘要
        """
        await self.load_from_db()

        if not self.memories:
            return "暂无对话记录"

        total_messages = len(self.memories)
        user_messages = sum(1 for m in self.memories if m.role == "user")
        assistant_messages = sum(1 for m in self.memories if m.role == "assistant")

        first_message = self.memories[0].content[:50] + "..." if len(self.memories[0].content) > 50 else self.memories[0].content
        last_message = self.memories[-1].content[:50] + "..." if len(self.memories[-1].content) > 50 else self.memories[-1].content

        summary = (
            f"会话摘要:\n"
            f"- 总消息数: {total_messages}\n"
            f"- 用户消息: {user_messages}\n"
            f"- AI 回复: {assistant_messages}\n"
            f"- 首条消息: {first_message}\n"
            f"- 最后消息: {last_message}"
        )

        return summary