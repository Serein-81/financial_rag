"""
增强版上下文构建器 (Enhanced Context Builder)

融合示例代码的优点和我们项目的特色：
- Token预算管理
- 统一上下文结构
- 智能相关性计算
- 企业级特性
"""

import math
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from .base_memory import MemoryItem
from .memory_manager import MemoryManager
from app.services.embedding_service import embedding_service


@dataclass
class ContextPacket:
    """上下文信息包"""
    content: str
    timestamp: datetime
    token_count: int
    relevance_score: float
    metadata: Dict[str, Any]
    source_type: str  # "system", "memory", "knowledge", "history"
    priority: int = 0  # 优先级 (0=最高)


@dataclass
class ContextConfig:
    """上下文构建配置"""
    relevance_weight: float = 0.7
    recency_weight: float = 0.3
    min_relevance: float = 0.3
    max_tokens: int = 4000
    preserve_system: bool = True
    enable_compression: bool = True


class EnhancedContextBuilder:
    """
    增强版上下文构建器
    
    特性：
    1. Token预算管理
    2. 统一结构化输出
    3. 智能相关性计算
    4. 企业记忆集成
    5. 多租户支持
    """
    
    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
        print("🔧 [上下文构建器] 初始化完成")
    
    async def build_context(
        self,
        user_query: str,
        memory_manager: MemoryManager,
        knowledge_context: str = "",
        system_instructions: str = "",
        custom_packets: Optional[List[ContextPacket]] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        构建完整的上下文
        
        流程：
        1. 汇集候选信息 (_gather)
        2. 选择最相关信息 (_select)
        3. 结构化组织 (_structure)
        4. 压缩超限内容 (_compress)
        
        Args:
            user_query: 用户查询
            memory_manager: 记忆管理器
            knowledge_context: 知识库上下文
            system_instructions: 系统指令
            custom_packets: 自定义信息包
            max_tokens: 最大token数
            
        Returns:
            结构化的上下文字符串
        """
        max_tokens = max_tokens or self.config.max_tokens
        
        print(f"🏗️ [上下文构建] 开始构建 | 查询: {user_query[:50]}...")
        
        # 1. 汇集候选信息
        packets = await self._gather(
            user_query, memory_manager, knowledge_context, 
            system_instructions, custom_packets
        )
        
        # 2. 选择最相关信息
        selected = await self._select(packets, user_query, max_tokens)
        
        # 3. 结构化组织
        structured = self._structure(selected, user_query)
        
        # 4. 压缩超限内容
        if self.config.enable_compression:
            final_context = self._compress(structured, max_tokens)
        else:
            final_context = structured
        
        final_tokens = self._count_tokens(final_context)
        print(f"✅ [上下文构建] 完成 | Token: {final_tokens}/{max_tokens}")
        
        return final_context
    
    async def _gather(
        self,
        user_query: str,
        memory_manager: MemoryManager,
        knowledge_context: str = "",
        system_instructions: str = "",
        custom_packets: Optional[List[ContextPacket]] = None
    ) -> List[ContextPacket]:
        """
        汇集所有候选信息
        
        Args:
            user_query: 用户查询
            memory_manager: 记忆管理器
            knowledge_context: 知识库上下文
            system_instructions: 系统指令
            custom_packets: 自定义信息包
            
        Returns:
            候选信息包列表
        """
        packets = []
        
        # 1. 添加系统指令(最高优先级,不参与评分)
        if system_instructions:
            packets.append(ContextPacket(
                content=system_instructions,
                timestamp=datetime.now(),
                token_count=self._count_tokens(system_instructions),
                relevance_score=1.0,  # 系统指令始终保留
                metadata={"type": "system_instruction"},
                source_type="system",
                priority=0
            ))
        
        # 2. 从记忆系统检索相关记忆
        try:
            memories = await memory_manager.retrieve_context(
                query=user_query,
                use_working=True,
                use_episodic=True,
                use_semantic=True,
                top_k=10
            )
            
            # 转换工作记忆
            for m in memories.get("working", []):
                packets.append(self._memory_to_packet(m, "working"))
            
            # 转换情景记忆
            for m in memories.get("episodic", []):
                packets.append(self._memory_to_packet(m, "episodic"))
            
            # 转换语义记忆
            for m in memories.get("semantic", []):
                packets.append(self._memory_to_packet(m, "semantic"))
                
        except Exception as e:
            print(f"⚠️ [上下文构建] 记忆检索失败: {e}")
        
        # 3. 添加知识库上下文
        if knowledge_context:
            packets.append(ContextPacket(
                content=knowledge_context,
                timestamp=datetime.now(),
                token_count=self._count_tokens(knowledge_context),
                relevance_score=0.8,  # 知识库内容高相关性
                metadata={"type": "knowledge_base"},
                source_type="knowledge",
                priority=1
            ))
        
        # 4. 添加自定义信息包
        if custom_packets:
            packets.extend(custom_packets)
        
        print(f"📦 [信息汇集] 汇集了 {len(packets)} 个候选信息包")
        return packets
    
    async def _select(
        self,
        packets: List[ContextPacket],
        user_query: str,
        available_tokens: int
    ) -> List[ContextPacket]:
        """
        选择最相关的信息包 (借鉴示例代码的Token预算管理)
        
        策略：
        1. 分离系统指令和其他信息
        2. 计算综合分数 (相关性 + 新近性 + 优先级)
        3. 贪心选择直到Token上限
        
        Args:
            packets: 候选信息包列表
            user_query: 用户查询
            available_tokens: 可用token数量
            
        Returns:
            选中的信息包列表
        """
        # 1. 分离系统指令和其他信息
        system_packets = [p for p in packets if p.source_type == "system"]
        other_packets = [p for p in packets if p.source_type != "system"]
        
        # 2. 计算系统指令占用的token
        system_tokens = sum(p.token_count for p in system_packets)
        remaining_tokens = available_tokens - system_tokens
        
        if remaining_tokens <= 0:
            print("⚠️ [信息选择] 系统指令已占满所有token预算")
            return system_packets
        
        # 3. 为其他信息计算综合分数
        scored_packets = []
        for packet in other_packets:
            # 重新计算相关性分数
            if packet.relevance_score == 0.5:  # 默认值,需要重新计算
                relevance = await self._calculate_relevance(packet.content, user_query)
                packet.relevance_score = relevance
            
            # 计算新近性分数
            recency = self._calculate_recency(packet.timestamp)
            
            # 计算优先级加成
            priority_boost = max(0, (5 - packet.priority) * 0.1)  # 优先级越高加成越多
            
            # 综合分数 = 相关性权重 × 相关性 + 新近性权重 × 新近性 + 优先级加成
            combined_score = (
                self.config.relevance_weight * packet.relevance_score +
                self.config.recency_weight * recency +
                priority_boost
            )
            
            # 过滤低于最小相关性阈值的信息
            if packet.relevance_score >= self.config.min_relevance:
                scored_packets.append((combined_score, packet))
        
        # 4. 按分数降序排序
        scored_packets.sort(key=lambda x: x[0], reverse=True)
        
        # 5. 贪心选择:按分数从高到低填充,直到达到token上限
        selected = system_packets.copy()
        current_tokens = system_tokens
        
        for score, packet in scored_packets:
            if current_tokens + packet.token_count <= available_tokens:
                selected.append(packet)
                current_tokens += packet.token_count
            else:
                # Token预算已满,停止选择
                break
        
        print(f"🎯 [信息选择] 选择了 {len(selected)} 个信息包,共 {current_tokens} tokens")
        return selected
    
    def _structure(self, selected_packets: List[ContextPacket], user_query: str) -> str:
        """
        将选中的信息包组织成结构化的上下文模板 (借鉴示例代码的结构化输出)
        
        结构：
        [Enterprise Context] - 企业记忆和历史
        [Knowledge Base] - 知识库内容
        [Current Context] - 当前对话上下文
        [Task] - 用户查询任务
        [System Instructions] - 系统指令
        [Output Requirements] - 输出要求
        
        Args:
            selected_packets: 选中的信息包列表
            user_query: 用户查询
            
        Returns:
            结构化的上下文字符串
        """
        # 按类型分组
        system_instructions = []
        enterprise_context = []
        knowledge_base = []
        current_context = []
        
        for packet in selected_packets:
            source_type = packet.source_type
            packet_type = packet.metadata.get("type", "general")
            
            if source_type == "system":
                system_instructions.append(packet.content)
            elif source_type == "knowledge":
                knowledge_base.append(packet.content)
            elif source_type == "memory":
                if packet_type in ["semantic", "episodic"]:
                    enterprise_context.append(packet.content)
                else:  # working memory
                    current_context.append(packet.content)
            else:
                current_context.append(packet.content)
        
        # 构建结构化模板
        sections = []
        
        # [Enterprise Context] - 企业记忆
        if enterprise_context:
            sections.append("[Enterprise Context]\n" + "\n---\n".join(enterprise_context))
        
        # [Knowledge Base] - 知识库
        if knowledge_base:
            sections.append("[Knowledge Base]\n" + "\n---\n".join(knowledge_base))
        
        # [Current Context] - 当前对话
        if current_context:
            sections.append("[Current Context]\n" + "\n".join(current_context))
        
        # [Task] - 用户任务
        sections.append(f"[Task]\n{user_query}")
        
        # [System Instructions] - 系统指令
        if system_instructions:
            sections.append("[System Instructions]\n" + "\n".join(system_instructions))
        
        # [Output Requirements] - 输出要求
        sections.append("[Output Requirements]\n请基于以上企业上下文、知识库和当前对话，提供准确、专业的回答。")
        
        return "\n\n".join(sections)
    
    def _compress(self, context: str, max_tokens: int) -> str:
        """
        压缩超限的上下文 (改进版：保证关键结构不丢失)
        
        策略：
        1. 检查是否超限
        2. 识别关键结构（Task和System Instructions必须保留）
        3. 分区压缩：优先保留重要内容
        4. 智能截断：保留关键信息
        
        Args:
            context: 原始上下文
            max_tokens: 最大token限制
            
        Returns:
            压缩后的上下文
        """
        current_tokens = self._count_tokens(context)
        
        if current_tokens <= max_tokens:
            return context  # 无需压缩
        
        print(f"🗜️ [上下文压缩] 开始压缩 ({current_tokens} > {max_tokens})")
        
        # 分区压缩：保持结构完整性
        sections = context.split("\n\n")
        
        # 识别关键结构（必须保留）
        critical_sections = []
        optional_sections = []
        
        for section in sections:
            if any(keyword in section for keyword in ["[Task]", "[System Instructions]", "[Output Requirements]"]):
                critical_sections.append(section)
            else:
                optional_sections.append(section)
        
        # 计算关键结构占用的tokens
        critical_tokens = sum(self._count_tokens(section) for section in critical_sections)
        remaining_tokens = max_tokens - critical_tokens
        
        # 如果关键结构已经超限，只保留关键结构
        if remaining_tokens <= 0:
            print("⚠️ [上下文压缩] 关键结构已占满预算，仅保留核心内容")
            compressed_context = "\n\n".join(critical_sections)
        else:
            # 从可选结构中选择最重要的内容
            compressed_sections = critical_sections.copy()
            current_total = critical_tokens
            
            # 按重要性排序可选结构
            priority_order = ["[Knowledge Base]", "[Enterprise Context]", "[Current Context]"]
            sorted_optional = []
            
            for priority in priority_order:
                for section in optional_sections:
                    if priority in section:
                        sorted_optional.append(section)
                        break
            
            # 添加剩余的可选结构
            for section in optional_sections:
                if section not in sorted_optional:
                    sorted_optional.append(section)
            
            # 贪心选择可选结构
            for section in sorted_optional:
                section_tokens = self._count_tokens(section)
                
                if current_total + section_tokens <= max_tokens:
                    # 完整保留
                    compressed_sections.append(section)
                    current_total += section_tokens
                else:
                    # 部分保留
                    remaining = max_tokens - current_total
                    if remaining > 50:  # 至少保留50 tokens才有意义
                        truncated = self._truncate_text(section, remaining - 20)
                        compressed_sections.append(truncated + "\n[... 内容已压缩 ...]")
                        current_total += remaining
                    break
            
            compressed_context = "\n\n".join(compressed_sections)
        
        final_tokens = self._count_tokens(compressed_context)
        print(f"✅ [上下文压缩] 完成: {current_tokens} -> {final_tokens} tokens")
        
        return compressed_context
    
    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """
        截断文本到指定token数量
        
        策略：
        1. 按字符比例估算
        2. 保留完整句子
        3. 优先保留开头内容
        
        Args:
            text: 原始文本
            max_tokens: 最大token数量
            
        Returns:
            截断后的文本
        """
        if self._count_tokens(text) <= max_tokens:
            return text
        
        # 按字符比例估算
        char_per_token = len(text) / max(self._count_tokens(text), 1)
        max_chars = int(max_tokens * char_per_token * 0.9)  # 留10%缓冲
        
        if max_chars >= len(text):
            return text
        
        # 尝试在句号处截断
        truncated = text[:max_chars]
        last_period = truncated.rfind('。')
        last_newline = truncated.rfind('\n')
        
        # 选择最近的合适截断点
        cut_point = max(last_period, last_newline)
        if cut_point > max_chars * 0.7:  # 如果截断点不会丢失太多内容
            return text[:cut_point + 1]
        else:
            return truncated
    
    async def _calculate_relevance(self, content: str, query: str) -> float:
        """
        计算内容与查询的相关性 (改进版：关键词 + 向量相似度)
        
        策略：
        1. 关键词重叠 (Jaccard相似度)
        2. 向量相似度 (如果可用)
        3. 加权融合
        
        Args:
            content: 内容文本
            query: 查询文本
            
        Returns:
            相关性分数(0.0-1.0)
        """
        # 方法1：关键词重叠
        keyword_score = self._calculate_keyword_relevance(content, query)
        
        # 方法2：向量相似度 (如果embedding服务可用)
        try:
            content_embedding = await embedding_service.get_embedding(content)
            query_embedding = await embedding_service.get_embedding(query)
            vector_score = self._calculate_cosine_similarity(content_embedding, query_embedding)
        except Exception:
            vector_score = 0.0
        
        # 加权融合：关键词30% + 向量70%
        if vector_score > 0:
            final_score = keyword_score * 0.3 + vector_score * 0.7
        else:
            final_score = keyword_score
        
        return max(0.0, min(1.0, final_score))
    
    def _calculate_keyword_relevance(self, content: str, query: str) -> float:
        """
        计算关键词相关性 (Jaccard相似度)
        
        Args:
            content: 内容文本
            query: 查询文本
            
        Returns:
            关键词相关性分数
        """
        # 提取关键词
        content_words = set(self._extract_keywords(content))
        query_words = set(self._extract_keywords(query))
        
        if not query_words:
            return 0.0
        
        # Jaccard相似度
        intersection = content_words & query_words
        union = content_words | query_words
        
        return len(intersection) / len(union) if union else 0.0
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取文本关键词
        
        策略：
        1. 中文词汇 (2-4字)
        2. 英文单词
        3. 过滤停用词
        
        Args:
            text: 文本内容
            
        Returns:
            关键词列表
        """
        # 停用词
        stopwords = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看",
            "好", "自己", "这", "那", "里", "可以", "什么", "吗", "呢", "啊"
        }
        
        keywords = []
        
        # 提取中文词汇
        chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        keywords.extend([w for w in chinese_words if w not in stopwords])
        
        # 提取英文单词
        english_words = re.findall(r'[a-zA-Z]+', text.lower())
        keywords.extend([w for w in english_words if len(w) > 2])
        
        return list(set(keywords))  # 去重
    
    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm_a = math.sqrt(sum(a * a for a in vec1))
            norm_b = math.sqrt(sum(b * b for b in vec2))
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return dot_product / (norm_a * norm_b)
        except Exception:
            return 0.0
    
    def _calculate_recency(self, timestamp: datetime) -> float:
        """
        计算时间近因性分数 (指数衰减模型)
        
        策略：
        - 1小时内：1.0
        - 1天内：0.8
        - 1周内：0.6
        - 1月内：0.4
        - 更久：0.2
        
        Args:
            timestamp: 信息时间戳
            
        Returns:
            新近性分数(0.0-1.0)
        """
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        
        # 指数衰减
        decay_factor = 0.1
        recency_score = math.exp(-decay_factor * age_hours / 24)
        
        return max(0.1, min(1.0, recency_score))
    
    def _memory_to_packet(self, memory: MemoryItem, memory_type: str) -> ContextPacket:
        """
        将记忆项转换为上下文信息包
        
        Args:
            memory: 记忆项
            memory_type: 记忆类型
            
        Returns:
            上下文信息包
        """
        # 根据记忆类型设置优先级
        priority_map = {
            "working": 1,    # 当前对话最重要
            "semantic": 2,   # 长期知识次之
            "episodic": 3    # 历史对话最后
        }
        
        return ContextPacket(
            content=memory.content,
            timestamp=memory.timestamp,
            token_count=self._count_tokens(memory.content),
            relevance_score=memory.importance,  # 使用记忆的重要性作为初始相关性
            metadata={
                "type": memory_type,
                "memory_id": memory.id,
                "access_count": memory.access_count,
                **memory.metadata
            },
            source_type="memory",
            priority=priority_map.get(memory_type, 3)
        )
    
    def _count_tokens(self, text: str) -> int:
        """
        估算文本的token数量
        
        策略：
        - 中文：1字符 ≈ 1 token
        - 英文：1单词 ≈ 1.3 tokens
        - 标点和空格：按字符计算
        
        Args:
            text: 文本内容
            
        Returns:
            token数量
        """
        if not text:
            return 0
        
        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        
        # 统计英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        # 统计其他字符 (标点、数字、空格等)
        other_chars = len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text))
        
        # 计算总token数
        total_tokens = chinese_chars + int(english_words * 1.3) + int(other_chars * 0.5)
        
        return max(1, total_tokens)  # 至少1个token