"""
增强版上下文构建器 (Enhanced Context Builder)

融合示例代码的优点和我们项目的特色：
- Token预算管理
- 统一上下文结构
- 智能相关性计算
- 企业级特性
- 动态复杂度检测和自适应预算调整
"""

import math
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from .base_memory import MemoryItem
from .memory_manager import MemoryManager
from app.services.embedding_service import embedding_service
from app.memory_system.model_context_manager import model_context_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """查询复杂度等级"""
    SIMPLE = "simple"
    NORMAL = "normal"
    COMPLEX = "complex"


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
    needs_relevance_check: bool = False  # 标记是否需要重新计算相关性


@dataclass
class ContextConfig:
    """上下文构建配置"""
    relevance_weight: float = 0.7
    recency_weight: float = 0.3
    min_relevance: float = 0.3
    max_tokens: int = 0  # 0 表示使用模型上下文限制动态计算
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
    6. 动态复杂度检测和自适应预算调整
    """
    
    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
        self._query_embedding_cache: Optional[List[float]] = None
        self._query_for_cached_embedding: Optional[str] = None
        self._complexity_keywords = {
            QueryComplexity.COMPLEX: [
                "分析", "对比", "总结", "比较", "归纳", "推理", "评估", "预测",
                "详细说明", "深入分析", "完整报告", "综合分析", "多角度",
                "影响因素", "发展趋势", "对比分析", "优缺点", "优先级",
                "推荐", "建议", "方案", "策略", "优化"
            ]
        }
        
    
    def _analyze_query_complexity(self, query: str) -> QueryComplexity:
        """
        分析查询复杂度
        
        策略：
        1. 简单查询：问句 < 20 字
        2. 普通查询：问句 20-50 字
        3. 复杂查询：问句 > 50 字 或 包含复杂关键词
        
        Args:
            query: 用户查询
            
        Returns:
            复杂度等级
        """
        query_len = len(query)
        query_lower = query.lower()
        
        if query_len < 20:
            return QueryComplexity.SIMPLE
        
        if query_len > 50:
            for keyword in self._complexity_keywords[QueryComplexity.COMPLEX]:
                if keyword in query_lower:
                    return QueryComplexity.COMPLEX
            return QueryComplexity.NORMAL
        
        for keyword in self._complexity_keywords[QueryComplexity.COMPLEX]:
            if keyword in query_lower:
                return QueryComplexity.COMPLEX
        
        return QueryComplexity.NORMAL
    
    def _log_token_usage(
        self,
        query: str,
        budget: int,
        actual: int,
        compression_ratio: float = 1.0,
        session_id: Optional[str] = None
    ):
        """
        记录 Token 使用情况（复用 logging 模块）
        
        Args:
            query: 用户查询
            budget: 预算
            actual: 实际使用
            compression_ratio: 压缩比例
            session_id: 会话 ID
        """
        usage_ratio = actual / budget if budget > 0 else 0
        
        extra_data = {
            "query_preview": query[:50],
            "budget": budget,
            "actual": actual,
            "usage_ratio": f"{usage_ratio:.1%}",
            "compression": f"{compression_ratio:.1%}",
            "session_id": session_id
        }
        
        if usage_ratio >= 1.0:
            logger.warning(
                f"[TOKEN] ⚠️ 截断发生 | 预算: {budget} | 实际: {actual} | "
                f"使用率: {usage_ratio:.1%} | 查询: {query[:30]}...",
                extra=extra_data
            )
        elif usage_ratio >= 0.8:
            logger.info(
                f"[TOKEN] 使用率高 | 预算: {budget} | 实际: {actual} | "
                f"使用率: {usage_ratio:.1%}",
                extra=extra_data
            )
        else:
            logger.debug(
                f"[TOKEN] 正常 | 预算: {budget} | 实际: {actual} | "
                f"使用率: {usage_ratio:.1%}",
                extra=extra_data
            )
    
    async def build_context(
        self,
        user_query: str,
        memory_manager: MemoryManager,
        knowledge_context: str = "",
        system_instructions: str = "",
        custom_packets: Optional[List[ContextPacket]] = None,
        max_tokens: Optional[int] = None,
        session_id: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> str:
        """
        构建完整的上下文

        流程：
        1. 动态上下文预算（基于模型能力）
        2. 汇集候选信息 (_gather)
        3. 选择最相关信息 (_select)
        4. 结构化组织 (_structure)
        5. 压缩超限内容 (_compress)
        6. Token 监控日志

        Args:
            user_query: 用户查询
            memory_manager: 记忆管理器
            knowledge_context: 知识库上下文
            system_instructions: 系统指令
            custom_packets: 自定义信息包
            max_tokens: 最大token数（None 时自动根据模型能力调整）
            session_id: 会话 ID（用于日志记录）
            model_name: 模型名称（None 时使用配置中的 LLM_PROVIDER）

        Returns:
            结构化的上下文字符串
        """
        initial_tokens = self._count_tokens(user_query) + self._count_tokens(system_instructions)
        
        if max_tokens is None:
            if model_name is None:
                model_name = self._get_current_model_name()
            
            max_tokens = model_context_manager.get_context_limit(model_name)
            
            complexity = self._analyze_query_complexity(user_query)
            complexity_budget = {
                QueryComplexity.SIMPLE: max_tokens * 0.5,
                QueryComplexity.NORMAL: max_tokens * 0.7,
                QueryComplexity.COMPLEX: max_tokens * 0.9,
            }
            max_tokens = int(complexity_budget.get(complexity, max_tokens * 0.7))
            
            

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
        compression_ratio = final_tokens / max_tokens if max_tokens > 0 else 1.0
        
        
        
        self._log_token_usage(
            query=user_query,
            budget=max_tokens,
            actual=final_tokens,
            compression_ratio=compression_ratio,
            session_id=session_id
        )

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
            memories = memories or {}

            # 转换工作记忆
            for m in (memories.get("working") or []):
                packets.append(self._memory_to_packet(m, "working"))

            # 转换情景记忆
            for m in (memories.get("episodic") or []):
                packets.append(self._memory_to_packet(m, "episodic"))

            # 转换语义记忆
            for m in (memories.get("semantic") or []):
                packets.append(self._memory_to_packet(m, "semantic"))

        except (ValueError, KeyError) as e:
            logger.warning(f"[上下文构建] 获取语义记忆数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"[上下文构建] 获取语义记忆IO错误: {e}")
        except Exception as e:
            logger.warning(f"[上下文构建] 记忆检索失败: {e}")

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

        # 4. 添加用户记忆上下文（事实、偏好、纠正）
        try:
            user_memory = await memory_manager.get_user_memory_context(top_k=10)
            if user_memory:
                packets.append(ContextPacket(
                    content=user_memory,
                    timestamp=datetime.now(),
                    token_count=self._count_tokens(user_memory),
                    relevance_score=0.9,  # 用户记忆高相关性
                    metadata={"type": "user_memory"},
                    source_type="user_memory",
                    priority=1
                ))
                logger.debug("[上下文构建] 添加用户记忆上下文")
        except (ValueError, KeyError) as e:
            logger.warning(f"[上下文构建] 获取用户记忆上下文数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"[上下文构建] 获取用户记忆上下文IO错误: {e}")
        except Exception as e:
            logger.warning(f"[上下文构建] 获取用户记忆上下文失败: {e}")

        # 5. 添加自定义信息包
        if custom_packets:
            packets.extend(custom_packets)

        
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
        # 1. 分离系统指令、工作记忆和其他信息
        system_packets = [p for p in packets if p.source_type == "system"]
        working_packets = [p for p in packets if p.source_type == "memory" and p.metadata.get("type") == "working"]
        other_packets = [p for p in packets if p.source_type not in ["system"] and not (p.source_type == "memory" and p.metadata.get("type") == "working")]

        # 2. 计算系统指令占用的token
        system_tokens = sum(p.token_count for p in system_packets)
        working_tokens = sum(p.token_count for p in working_packets)
        remaining_tokens = available_tokens - system_tokens - working_tokens

        if remaining_tokens <= 0:
            
            return system_packets + working_packets

        # 3. 为工作记忆设置高优先级（当前会话必须保留）
        for packet in working_packets:
            packet.relevance_score = max(packet.relevance_score, 0.9)
            packet.priority = min(packet.priority, 1)

        # 4. 为其他信息计算综合分数
        scored_packets = []
        for packet in other_packets:
            # 🔧 修复：检查 needs_relevance_check 标志，而不是依赖 magic number 0.5
            # 记忆类内容必须重新计算与查询的相关性
            if packet.needs_relevance_check:
                relevance = await self._calculate_relevance(packet.content, user_query)
                packet.relevance_score = relevance
                

            recency = self._calculate_recency(packet.timestamp)
            priority_boost = max(0, (5 - packet.priority) * 0.1)

            combined_score = (
                self.config.relevance_weight * packet.relevance_score +
                self.config.recency_weight * recency +
                priority_boost
            )

            if packet.relevance_score >= self.config.min_relevance:
                scored_packets.append((combined_score, packet))

        # 5. 按分数降序排序
        scored_packets.sort(key=lambda x: x[0], reverse=True)

        # 6. 贪心选择:先加入工作记忆，再加入其他信息直到token上限
        selected = system_packets.copy()
        current_tokens = system_tokens

        for packet in working_packets:
            if current_tokens + packet.token_count <= available_tokens:
                selected.append(packet)
                current_tokens += packet.token_count
            else:
                

                for score, packet in scored_packets:
                    if current_tokens + packet.token_count <= available_tokens:
                        selected.append(packet)
                        current_tokens += packet.token_count
                    else:
                        break

        
        
        # 🆕 去重处理：移除重复的内容（基于内容和来源类型）
        selected = self._deduplicate_packets(selected)
        
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
        user_memory_context = []

        for packet in selected_packets:
            source_type = packet.source_type
            packet_type = packet.metadata.get("type", "general")

            if source_type == "system":
                system_instructions.append(packet.content)
            elif source_type == "knowledge":
                knowledge_base.append(packet.content)
            elif source_type == "user_memory":
                # 用户记忆上下文（事实、偏好、纠正）
                user_memory_context.append(packet.content)
            elif source_type == "memory":
                if packet_type in ["semantic", "episodic"]:
                    # 历史对话 / 长期知识 → 企业背景区
                    enterprise_context.append(packet.content)
                elif packet_type == "working":
                    # 🔧 Bug2修复：工作记忆（当前对话）→ 当前上下文区
                    current_context.append(packet.content)
                else:
                    # 兜底：未知记忆类型归入当前上下文
                    current_context.append(packet.content)
            else:
                current_context.append(packet.content)

        # 构建结构化模板
        sections = []

        # [Enterprise Context] - 企业记忆
        if enterprise_context:
            sections.append("[Enterprise Context]\n" + "\n---\n".join(enterprise_context))

        # [User Memory] - 用户记忆（事实、偏好、纠正）
        if user_memory_context:
            sections.append("[User Memory]\n" + "\n".join(user_memory_context))

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
        压缩超限的上下文 (增强版：保证关键结构不丢失，优先回答质量)

        策略：
        1. 检查是否超限
        2. 识别关键结构（Task、System Instructions、User Memory 必须保留）
        3. 分区压缩：按 "质量 > 完整性 > 相关性" 排序
        4. 智能截断：保留完整句子和有结论的内容

        Args:
            context: 原始上下文
            max_tokens: 最大token限制

        Returns:
            压缩后的上下文
        """
        current_tokens = self._count_tokens(context)

        if current_tokens <= max_tokens:
            return context

        

        sections = context.split("\n\n")

        critical_sections = []
        optional_sections = []

        for section in sections:
            if any(keyword in section for keyword in ["[Task]", "[System Instructions]", "[Output Requirements]", "[User Memory]"]):
                critical_sections.append(section)
            else:
                optional_sections.append(section)

        critical_tokens = sum(self._count_tokens(section) for section in critical_sections)
        remaining_tokens = max_tokens - critical_tokens

        if remaining_tokens <= 0:
            
            compressed_context = "\n\n".join(critical_sections)
        else:
            compressed_sections = critical_sections.copy()
            current_total = critical_tokens

            scored_optional = []
            for section in optional_sections:
                score = self._calculate_section_quality(section)
                scored_optional.append((score, section))

            scored_optional.sort(key=lambda x: x[0], reverse=True)

            for score, section in scored_optional:
                section_tokens = self._count_tokens(section)

                if current_total + section_tokens <= max_tokens:
                    compressed_sections.append(section)
                    current_total += section_tokens
                else:
                    remaining = max_tokens - current_total
                    if remaining > 100:
                        truncated = self._truncate_text(section, remaining - 30)
                        truncated_tokens = self._count_tokens(truncated)
                        if self._is_content_complete(truncated):
                            compressed_sections.append(truncated)
                        else:
                            compressed_sections.append(truncated + "\n[... 更多内容已省略 ...]")
                        current_total += truncated_tokens
                    break

            compressed_context = "\n\n".join(compressed_sections)

        final_tokens = self._count_tokens(compressed_context)
        

        return compressed_context

    def _calculate_section_quality(self, section: str) -> float:
        """
        计算区块质量分数（用于智能排序）

        评估维度：
        1. 区块类型优先级
        2. 内容完整性
        3. 信息密度

        Args:
            section: 区块内容

        Returns:
            质量分数 (0-1)
        """
        base_priority = {
            "[Knowledge Base]": 1.0,
            "[User Memory]": 0.95,
            "[Enterprise Context]": 0.8,
            "[Current Context]": 0.7,
        }

        score = 0.5
        for marker, priority in base_priority.items():
            if marker in section:
                score = priority
                break

        if self._is_content_complete(section):
            score += 0.2

        density = self._estimate_content_density(section)
        score += density * 0.2

        return min(score, 1.0)

    def _is_content_complete(self, text: str) -> bool:
        """
        判断内容是否完整（有结尾）

        Args:
            text: 文本内容

        Returns:
            是否完整
        """
        if not text:
            return False

        complete_indicators = ["。", "！", "？", "结论", "因此", "总之", "综上所述", "。\n"]

        for indicator in complete_indicators:
            if text.rstrip().endswith(indicator):
                return True

        paragraph_count = text.count("\n")
        if paragraph_count > 2:
            last_line = text.split("\n")[-1] if "\n" in text else text
            if len(last_line) > 20:
                return True

        return False

    def _estimate_content_density(self, text: str) -> float:
        """
        估算内容信息密度

        Args:
            text: 文本内容

        Returns:
            密度分数 (0-1)
        """
        if not text:
            return 0.0

        info_markers = [
            "是", "不是", "应该", "必须", "需要",
            "包含", "具有", "属于", "通过", "因为",
            "数据", "统计", "分析", "结果", "方案"
        ]

        marker_count = sum(1 for marker in info_markers if marker in text)
        density = min(marker_count / 10.0, 1.0)

        return density

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
        keyword_score = self._calculate_keyword_relevance(content, query)

        try:
            content_embedding = await embedding_service.get_embedding(content)
            
            if self._query_for_cached_embedding != query:
                self._query_embedding_cache = await embedding_service.get_embedding(query)
                self._query_for_cached_embedding = query
                print("📦 [向量缓存] 新查询向量已缓存")
            
            query_embedding = self._query_embedding_cache
            vector_score = self._calculate_cosine_similarity(content_embedding, query_embedding)
        except (ValueError, KeyError):
            vector_score = 0.0
        except (OSError, IOError):
            vector_score = 0.0
        except TypeError:
            vector_score = 0.0
        except Exception:
            vector_score = 0.0

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

    def _calculate_cosine_similarity(self, vec1: Any, vec2: Any) -> float:
        """
        计算余弦相似度
        💡 增强修改：加入了对 NumPy 数组的原生支持，极大提升高维向量的运算速度，
        并且同时兼容普通的 Python List。
        """
        try:
            # 尝试使用 numpy 进行高速计算
            import numpy as np
            if isinstance(vec1, np.ndarray) or isinstance(vec2, np.ndarray):
                v1 = np.asarray(vec1)
                v2 = np.asarray(vec2)
                norm_a = np.linalg.norm(v1)
                norm_b = np.linalg.norm(v2)
                if norm_a == 0 or norm_b == 0:
                    return 0.0
                return float(np.dot(v1, v2) / (norm_a * norm_b))

            # 降级：如果不是 numpy，使用 Python 原生计算
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
        from datetime import timezone

        # 💡 修复点 3：统一时区计算
        if timestamp.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()

        age_hours = (now - timestamp).total_seconds() / 3600

        # 指数衰减
        decay_factor = 0.1
        recency_score = math.exp(-decay_factor * age_hours / 24)

        return max(0.1, min(1.0, recency_score))

    def _deduplicate_packets(self, packets: List[ContextPacket]) -> List[ContextPacket]:
        """
        🆕🧠 去重信息包（增强版：支持语义相似度去重）
        
        策略：
        1. 第一步：精确去重（基于 memory_id 和完整内容）
        2. 第二步：语义去重（识别相似查询，如"我们的项目"vs"我们项目"）
        3. 保留最新的（时间戳最新的）
        4. 合并高度相似的内容
        
        Args:
            packets: 信息包列表
            
        Returns:
            去重后的信息包列表
        """
        
        # 第一步：精确去重（保持原有逻辑）
        seen_content = {}  # (source_type, content) -> packet
        seen_memory_id = {}  # memory_id -> packet
        
        for packet in packets:
            content_key = (packet.source_type, packet.content)
            memory_id = packet.metadata.get("memory_id")
            
            if memory_id:
                if memory_id in seen_memory_id:
                    if packet.timestamp > seen_memory_id[memory_id].timestamp:
                        seen_memory_id[memory_id] = packet
                    continue
                else:
                    seen_memory_id[memory_id] = packet
            
            if content_key in seen_content:
                if packet.timestamp > seen_content[content_key].timestamp:
                    seen_content[content_key] = packet
                continue
            else:
                seen_content[content_key] = packet
        
        result = list(seen_content.values())
        
        # 第二步：🧠 语义去重 - 识别并合并相似内容
        result = self._semantic_deduplicate(result)
        
        if len(packets) != len(result):
            
        
            return result
    
    def _semantic_deduplicate(self, packets: List[ContextPacket]) -> List[ContextPacket]:
        """
        🧠🆕 语义去重：识别相似查询并合并
        
        识别模式：
        - 标点符号差异："我们项目有什么功能" vs "我们项目有什么功能？"
        - 语序差异："项目有什么功能" vs "有什么项目功能"
        - 关键词差异："我们的项目" vs "我们项目" vs "现在的项目"
        - 相似查询："公司的年假政策" vs "公司年假政策"
        
        Args:
            packets: 信息包列表
            
        Returns:
            去重后的信息包列表
        """
        import re
        from difflib import SequenceMatcher
        
        if len(packets) <= 1:
            return packets
        
        SIMILARITY_THRESHOLD = 0.75  # 相似度阈值，超过则认为是重复
        
        def normalize_text(text: str) -> str:
            """文本标准化：去除噪声，提取核心语义"""
            # 去除标点符号
            text = re.sub(r'[^\w\s]', '', text)
            # 去除多余空格
            text = re.sub(r'\s+', ' ', text).strip()
            # 转小写（但保留中文语义）
            return text.lower()
        
        def extract_keywords(text: str) -> set:
            """提取关键词集合（用于快速比较）"""
            text = normalize_text(text)
            # 提取连续的中文字符序列作为关键词
            chinese_words = set(re.findall(r'[\u4e00-\u9fff]+', text))
            # 提取英文字符序列
            english_words = set(re.findall(r'[a-zA-Z]+', text))
            return chinese_words | english_words
        
        def calculate_keyword_overlap(text1: str, text2: str) -> float:
            """计算关键词重叠度"""
            keywords1 = extract_keywords(text1)
            keywords2 = extract_keywords(text2)
            
            if not keywords1 or not keywords2:
                return 0.0
            
            intersection = keywords1 & keywords2
            union = keywords1 | keywords2
            
            return len(intersection) / len(union) if union else 0.0
        
        def calculate_similarity(text1: str, text2: str) -> float:
            """计算两个文本的相似度"""
            # 方法1：基于字符序列的相似度
            seq_matcher = SequenceMatcher(None, normalize_text(text1), normalize_text(text2))
            seq_similarity = seq_matcher.ratio()
            
            # 方法2：基于关键词重叠度
            keyword_similarity = calculate_keyword_overlap(text1, text2)
            
            # 综合相似度（加权平均）
            return 0.6 * seq_similarity + 0.4 * keyword_similarity
        
        # 只对 memory 和 user_memory 类型的内容进行语义去重
        memory_packets = [p for p in packets if p.source_type in ["memory", "user_memory"]]
        other_packets = [p for p in packets if p.source_type not in ["memory", "user_memory"]]
        
        # 对记忆类内容进行语义去重
        unique_packets = []
        for packet in memory_packets:
            is_duplicate = False
            
            for existing_packet in unique_packets:
                # 检查是否属于同一来源
                if packet.source_type != existing_packet.source_type:
                    continue
                
                # 计算相似度
                similarity = calculate_similarity(packet.content, existing_packet.content)
                
                if similarity >= SIMILARITY_THRESHOLD:
                    # 🧠 发现语义相似的内容，选择更好的（更长、相关性更高的）
                    # 保留原则：优先保留内容更丰富或相关性更高的
                    existing_score = existing_packet.relevance_score + (len(existing_packet.content) / 1000)
                    new_score = packet.relevance_score + (len(packet.content) / 1000)
                    
                    if new_score > existing_score:
                        # 替换为更好的
                        unique_packets.remove(existing_packet)
                        unique_packets.append(packet)
                        
                    
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_packets.append(packet)
        
        # 合并所有类型
        result = other_packets + unique_packets
        
        # 按优先级和时间戳排序
        result.sort(key=lambda p: (p.priority, -p.timestamp.timestamp()), reverse=False)
        
        return result

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
            relevance_score=memory.importance,
            metadata={
                "type": memory_type,
                "memory_id": memory.id,
                "access_count": memory.access_count,
                **memory.metadata
            },
            source_type="memory",
            priority=priority_map.get(memory_type, 3),
            needs_relevance_check=True  # 🔧 记忆必须重新计算与查询的相关性
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

    def _get_current_model_name(self) -> str:
        """
        获取当前配置的模型名称

        策略：
        1. 优先使用 LLM_PROVIDER_DEFAULT
        2. 其次使用 LLM_PROVIDER
        3. 如果都不存在，返回默认值

        Returns:
            模型名称
        """
        model_name = ""

        if settings.LLM_PROVIDER_DEFAULT:
            provider = settings.LLM_PROVIDER_DEFAULT
        else:
            provider = settings.LLM_PROVIDER

        provider_to_model = {
            "zhipu": settings.ZHIPU_MODEL if hasattr(settings, "ZHIPU_MODEL") else "glm-4-flash",
            "openai": settings.OPENAI_MODEL if hasattr(settings, "OPENAI_MODEL") else "gpt-4o-mini",
            "claude": settings.CLAUDE_MODEL if hasattr(settings, "CLAUDE_MODEL") else "claude-3-sonnet",
            "deepseek": settings.DEEPSEEK_MODEL if hasattr(settings, "DEEPSEEK_MODEL") else "deepseek/deepseek-chat-v3-0324",
            "qwen": settings.QWEN_MODEL if hasattr(settings, "QWEN_MODEL") else "qwen/qwen3.6-plus:free",
            "minimax": settings.MINIMAX_MODEL if hasattr(settings, "MINIMAX_MODEL") else "MiniMax-Text-01",
            "baichuan": settings.BAICHUAN_MODEL if hasattr(settings, "BAICHUAN_MODEL") else "baichuan4",
            "gpt": settings.GPT_MODEL if hasattr(settings, "GPT_MODEL") else "openai/gpt-4o-mini",
        }

        model_name = provider_to_model.get(provider.lower(), settings.ZHIPU_MODEL if hasattr(settings, "ZHIPU_MODEL") else "glm-4-flash")

        return model_name
