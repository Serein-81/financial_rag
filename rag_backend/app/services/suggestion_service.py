"""
追问建议生成服务

基于对话历史和上下文生成智能追问建议：
1. 对话分析 - 分析对话主题和意图
2. 追问生成 - 生成多类型追问建议
3. 上下文扩展 - 基于已有答案扩展问题
4. 智能排序 - 按相关度排序建议
"""

import logging
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import re
from collections import Counter
import random

logger = logging.getLogger(__name__)


class SuggestionType(str, Enum):
    """追问类型"""
    DEEPEN = "deepen"  # 深入追问 - 深入探讨当前话题
    EXPAND = "expand"  # 扩展追问 - 扩展到相关话题
    COMPARE = "compare"  # 对比追问 - 与其他事物对比
    EXAMPLE = "example"  # 举例追问 - 请求具体例子
    CONSEQUENCE = "consequence"  # 后果追问 - 探讨结果和影响
    CAUSE = "cause"  # 原因追问 - 探讨原因
    DIFFERENCE = "difference"  # 区别追问 - 探讨区别
    SUMMARY = "summary"  # 总结追问 - 请求总结


@dataclass
class Suggestion:
    """追问建议"""
    id: str
    type: SuggestionType
    text: str
    confidence: float  # 置信度 0-1
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def display_text(self) -> str:
        """获取显示文本"""
        return self.text
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
            "confidence": self.confidence,
            "keywords": self.keywords,
            "metadata": self.metadata,
        }


@dataclass
class ConversationContext:
    """对话上下文"""
    topic: str = ""
    entities: List[str] = field(default_factory=list)
    intents: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    complexity: str = "medium"
    domain: str = ""


class SuggestionService:
    """
    追问建议生成服务
    
    功能：
    1. 对话分析 - 分析对话主题和意图
    2. 追问生成 - 生成多类型追问建议
    3. 上下文扩展 - 基于已有答案扩展问题
    4. 智能排序 - 按相关度排序建议
    """
    
    # 默认建议数量
    DEFAULT_SUGGESTION_COUNT = 5
    
    # 最大建议数量
    MAX_SUGGESTION_COUNT = 10
    
    # 最低置信度阈值
    MIN_CONFIDENCE_THRESHOLD = 0.3
    
    def __init__(
        self,
        suggestion_count: int = None,
        min_confidence: float = None,
    ):
        self.suggestion_count = suggestion_count or self.DEFAULT_SUGGESTION_COUNT
        self.min_confidence = min_confidence or self.MIN_CONFIDENCE_THRESHOLD
        
        # 建议模板
        self._templates = self._init_templates()
        
        # 关键词模式
        self._keyword_patterns = self._init_keyword_patterns()
        
        # 统计信息
        self._stats = {
            "total_generations": 0,
            "total_suggestions": 0,
            "avg_confidence": 0.0,
        }
        
        logger.info(
            f"🚀 SuggestionService 初始化完成, "
            f"建议数: {self.suggestion_count}, "
            f"最低置信度: {self.min_confidence}"
        )
    
    def _init_templates(self) -> Dict[SuggestionType, List[str]]:
        """初始化追问模板"""
        return {
            SuggestionType.DEEPEN: [
                "能否详细说明一下{topic}的{aspect}？",
                "{topic}具体是如何实现的？",
                "能否深入解释一下{topic}的原理？",
                "{topic}有哪些关键细节需要注意？",
                "能否更详细地介绍{topic}？",
            ],
            SuggestionType.EXPAND: [
                "{topic}和{related}有什么关系？",
                "除了{topic}，还有哪些相关内容？",
                "{topic}在实际应用中有哪些场景？",
                "关于{topic}，还有什么我应该知道的？",
                "{topic}在不同情况下有什么变化？",
            ],
            SuggestionType.COMPARE: [
                "{topic}和{other}有什么区别？",
                "{topic}和{other}哪个更好？",
                "{topic}与其他方案相比有什么优势？",
                "{topic}和{other}的主要差异是什么？",
                "为什么选择{topic}而不是{other}？",
            ],
            SuggestionType.EXAMPLE: [
                "能否举个{topic}的具体例子？",
                "有{topic}的实际应用案例吗？",
                "能展示一个{topic}的实例吗？",
                "{topic}在现实中如何应用？",
                "能否用例子说明{topic}？",
            ],
            SuggestionType.CONSEQUENCE: [
                "{topic}会带来哪些影响？",
                "如果{condition}，会有什么问题？",
                "{topic}会导致什么结果？",
                "{topic}有哪些潜在的风险？",
                "采用{topic}后会产生什么变化？",
            ],
            SuggestionType.CAUSE: [
                "为什么会出现{topic}？",
                "{topic}的原因是什么？",
                "是什么导致了{topic}？",
                "{topic}是如何产生的？",
                "造成{topic}的因素有哪些？",
            ],
            SuggestionType.DIFFERENCE: [
                "{topic}和{other}有什么不同？",
                "{topic}与{other}的主要区别在哪里？",
                "{topic}和{other}各有何特点？",
                "如何区分{topic}和{other}？",
                "{topic}和{other}的优劣对比？",
            ],
            SuggestionType.SUMMARY: [
                "能否总结一下{topic}的要点？",
                "{topic}的核心内容是什么？",
                "关于{topic}，有什么需要特别注意的？",
                "能否概括{topic}的主要内容？",
                "{topic}的关键信息有哪些？",
            ],
        }
    
    def _init_keyword_patterns(self) -> Dict[str, List[str]]:
        """初始化关键词模式"""
        return {
            "implementation": ["实现", "方法", "步骤", "流程", "如何做"],
            "reason": ["原因", "为什么", "为何", "理由"],
            "difference": ["区别", "差异", "不同", "对比", "比较"],
            "advantage": ["优势", "优点", "好处", "好处", "特点"],
            "disadvantage": ["劣势", "缺点", "问题", "风险", "局限"],
            "example": ["例子", "案例", "实例", "例如", "比如"],
            "summary": ["总结", "概括", "要点", "核心"],
            "application": ["应用", "使用", "场景", "用途"],
        }
    
    async def analyze_context(
        self,
        messages: List[Dict[str, Any]],
        current_answer: Optional[str] = None,
    ) -> ConversationContext:
        """
        分析对话上下文
        
        Args:
            messages: 消息列表
            current_answer: 当前答案
            
        Returns:
            ConversationContext: 上下文信息
        """
        context = ConversationContext()
        
        try:
            # 提取对话内容
            user_messages = [m["content"] for m in messages if m.get("role") == "user"]
            assistant_messages = [m["content"] for m in messages if m.get("role") == "assistant"]
            
            if user_messages:
                # 提取最后几个问题
                recent_questions = user_messages[-3:] if len(user_messages) >= 3 else user_messages
                
                # 简单的主题提取（基于关键词）
                all_text = " ".join(user_messages + assistant_messages)
                context.topic = self._extract_topic(all_text)
                
                # 提取实体
                context.entities = self._extract_entities(all_text)
                
                # 分析意图
                context.intents = self._analyze_intents(recent_questions)
                
                # 分析复杂度
                context.complexity = self._analyze_complexity(all_text)
                
                # 推断领域
                context.domain = self._infer_domain(all_text)
            
            if current_answer:
                # 分析答案的语气和内容
                context.sentiment = self._analyze_sentiment(current_answer)
            
            return context
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 分析上下文数据失败: {e}")
            return context
        except (OSError, IOError) as e:
            logger.error(f"❌ 分析上下文IO失败: {e}")
            return context
        except Exception as e:
            logger.error(f"❌ 分析上下文失败: {e}")
            return context
    
    def _extract_topic(self, text: str) -> str:
        """提取主题"""
        # 移除标点
        text = re.sub(r'[^\w\s]', '', text)
        
        # 简单分词
        words = text.split()
        
        # 统计词频
        word_freq = Counter(words)
        
        # 过滤停用词
        stopwords = {'的', '了', '是', '在', '和', '与', '对', '有', '这', '那', '什么', '如何', '怎么', '吗', '呢', '啊', '哦', '嗯'}
        filtered_words = [w for w in words if w not in stopwords and len(w) > 1]
        
        if filtered_words:
            # 返回最常见的词
            topic = Counter(filtered_words).most_common(1)[0][0]
            return topic
        
        return "相关内容"
    
    def _extract_entities(self, text: str) -> List[str]:
        """提取实体"""
        entities = []
        
        # 简单的实体提取（识别引号内的内容）
        quoted = re.findall(r'["""]([^"""]+)["""]', text)
        entities.extend(quoted)
        
        # 识别常见的实体模式
        patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # 英文专有名词
            r'《([^》]+)》',  # 书名
            r'“([^”]+)”',  # 中文引号
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        # 去重
        return list(set(entities))[:10]
    
    def _analyze_intents(self, questions: List[str]) -> List[str]:
        """分析意图"""
        intents = []
        
        for q in questions:
            # 识别问题类型
            if any(w in q for w in ["如何", "怎么", "怎样", "方法", "实现"]):
                intents.append("method")
            if any(w in q for w in ["为什么", "原因", "为何"]):
                intents.append("reason")
            if any(w in q for w in ["区别", "差异", "不同", "比较"]):
                intents.append("comparison")
            if any(w in q for w in ["什么", "哪个", "哪些"]):
                intents.append("information")
            if any(w in q for w in ["举例", "例子", "案例"]):
                intents.append("example")
        
        return list(set(intents))
    
    def _analyze_complexity(self, text: str) -> str:
        """分析复杂度"""
        # 简单基于长度和句子数
        sentences = text.count('。') + text.count('!') + text.count('?')
        
        if sentences < 3:
            return "simple"
        elif sentences < 10:
            return "medium"
        else:
            return "complex"
    
    def _infer_domain(self, text: str) -> str:
        """推断领域"""
        domain_keywords = {
            "技术": ["代码", "程序", "开发", "系统", "接口", "API", "数据库", "服务器"],
            "财务": ["税务", "发票", "报销", "预算", "成本", "利润", "税收"],
            "法律": ["合同", "法规", "法律", "条款", "权益", "义务", "责任"],
            "商业": ["市场", "营销", "销售", "客户", "运营", "战略"],
            "教育": ["学习", "课程", "培训", "教育", "教学", "学生"],
        }
        
        for domain, keywords in domain_keywords.items():
            if any(kw in text for kw in keywords):
                return domain
        
        return "通用"
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析语气"""
        positive_words = ["很好", "优秀", "棒", "不错", "感谢"]
        negative_words = ["问题", "错误", "失败", "困难", "麻烦"]
        
        positive_count = sum(1 for w in positive_words if w in text)
        negative_count = sum(1 for w in negative_words if w in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    async def generate_suggestions(
        self,
        context: ConversationContext,
        current_answer: Optional[str] = None,
        suggestion_types: Optional[List[SuggestionType]] = None,
        count: int = None,
    ) -> List[Suggestion]:
        """
        生成追问建议
        
        Args:
            context: 对话上下文
            current_answer: 当前答案
            suggestion_types: 指定的建议类型
            count: 生成数量
            
        Returns:
            List[Suggestion]: 建议列表
        """
        self._stats["total_generations"] += 1
        
        try:
            suggestions = []
            topic = context.topic or "相关内容"
            
            # 确定要生成的类型
            if not suggestion_types:
                # 根据上下文自动选择类型
                suggestion_types = [
                    SuggestionType.DEEPEN,
                    SuggestionType.EXPAND,
                    SuggestionType.EXAMPLE,
                    SuggestionType.COMPARE,
                ]
            
            # 生成每个类型的建议
            for stype in suggestion_types:
                if len(suggestions) >= (count or self.suggestion_count):
                    break
                
                s = await self._generate_by_type(stype, topic, context, current_answer)
                if s and s.confidence >= self.min_confidence:
                    suggestions.append(s)
            
            # 计算置信度
            for s in suggestions:
                s.confidence = self._calculate_confidence(s, context)
            
            # 按置信度排序
            suggestions.sort(key=lambda x: x.confidence, reverse=True)
            
            # 更新统计
            self._stats["total_suggestions"] += len(suggestions)
            
            return suggestions[:count or self.suggestion_count]
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 生成追问建议数据失败: {e}")
            return []
        except (OSError, IOError) as e:
            logger.error(f"❌ 生成追问建议IO失败: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 生成追问建议失败: {e}")
            return []
    
    async def _generate_by_type(
        self,
        suggestion_type: SuggestionType,
        topic: str,
        context: ConversationContext,
        current_answer: Optional[str],
    ) -> Optional[Suggestion]:
        """根据类型生成建议"""
        templates = self._templates.get(suggestion_type, [])
        
        if not templates:
            return None
        
        # 选择模板
        template = random.choice(templates)
        
        # 填充模板
        try:
            related_topics = context.entities[:2] if context.entities else ["相关问题"]
            
            text = template.format(
                topic=topic,
                related=related_topics[0] if related_topics else "其他",
                other=related_topics[1] if len(related_topics) > 1 else "其他方案",
                aspect="细节",
                condition="某些情况",
            )
            
            # 生成ID
            suggestion_id = hashlib.md5(
                f"{suggestion_type.value}:{text}".encode()
            ).hexdigest()[:8]
            
            return Suggestion(
                id=suggestion_id,
                type=suggestion_type,
                text=text,
                confidence=0.7,  # 初始置信度
                keywords=[topic] + context.entities[:3],
                metadata={
                    "topic": topic,
                    "entities": context.entities,
                    "domain": context.domain,
                }
            )
            
        except (ValueError, KeyError) as e:
            logger.debug(f"模板填充数据失败: {e}")
            return None
        except (OSError, IOError) as e:
            logger.debug(f"模板填充IO失败: {e}")
            return None
        except Exception as e:
            logger.debug(f"模板填充失败: {e}")
            return None
    
    def _calculate_confidence(self, suggestion: Suggestion, context: ConversationContext) -> float:
        """计算置信度"""
        confidence = suggestion.confidence
        
        # 根据上下文匹配度调整
        if suggestion.metadata.get("topic") == context.topic:
            confidence += 0.1
        
        if suggestion.metadata.get("domain") == context.domain:
            confidence += 0.05
        
        # 根据类型调整
        if suggestion.type == SuggestionType.DEEPEN and context.complexity == "complex":
            confidence += 0.1
        
        if suggestion.type == SuggestionType.EXAMPLE and context.intents == ["information"]:
            confidence += 0.1
        
        # 限制范围
        return min(1.0, max(0.0, confidence))
    
    async def generate_from_chat_history(
        self,
        messages: List[Dict[str, Any]],
        current_answer: Optional[str] = None,
        count: int = None,
    ) -> List[Dict[str, Any]]:
        """
        从聊天历史生成追问建议
        
        Args:
            messages: 消息列表
            current_answer: 当前答案
            count: 生成数量
            
        Returns:
            List[Dict]: 建议列表
        """
        # 分析上下文
        context = await self.analyze_context(messages, current_answer)
        
        # 生成建议
        suggestions = await self.generate_suggestions(
            context=context,
            current_answer=current_answer,
            count=count or self.suggestion_count,
        )
        
        # 转换为字典
        return [s.to_dict() for s in suggestions]
    
    async def generate_quick_suggestions(
        self,
        topic: str,
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        生成快速建议（不需要上下文）
        
        Args:
            topic: 主题
            count: 生成数量
            
        Returns:
            List[Dict]: 建议列表
        """
        context = ConversationContext(topic=topic)
        
        suggestions = await self.generate_suggestions(
            context=context,
            count=count,
        )
        
        return [s.to_dict() for s in suggestions]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_confidence = (
            self._stats["total_suggestions"] / self._stats["total_generations"]
            if self._stats["total_generations"] > 0 else 0
        )
        
        return {
            **self._stats,
            "avg_confidence": avg_confidence,
        }


# 全局单例
suggestion_service = SuggestionService()
