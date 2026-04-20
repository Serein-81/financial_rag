"""
关键词激活器 (Keyword Activator)
群聊静默监听与智能激活系统
核心功能：
1. 轻量级正则/规则拦截器 - 省钱滤网
2. 关键词激活与匹配
3. 静默监控模式
4. 多租户规则管理
"""

import asyncio
import re
import uuid
import logging
from typing import Dict, List, Any, Optional, Callable, Set, Pattern, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


class ActivationLevel(str, Enum):
    """激活级别"""
    IGNORE = "ignore"        # 完全忽略
    LOW = "low"             # 低优先级处理
    NORMAL = "normal"       # 正常处理
    HIGH = "high"           # 高优先级处理
    URGENT = "urgent"       # 紧急处理


class TriggerType(str, Enum):
    """触发类型"""
    KEYWORD = "keyword"           # 关键词触发
    PATTERN = "pattern"           # 正则模式触发
    MENTION = "mention"           # @提及触发
    EMOTION = "emotion"           # 情感触发
    CONTEXT = "context"           # 上下文触发


@dataclass
class TriggerRule:
    """触发规则"""
    rule_id: str
    name: str
    tenant_id: str
    
    trigger_type: TriggerType
    trigger_value: str  # 关键词或正则表达式
    
    # 激活配置
    activation_level: ActivationLevel = ActivationLevel.NORMAL
    target_agents: List[str] = field(default_factory=list)  # 目标Agent列表
    action: Optional[str] = None  # 动作类型
    
    # 条件配置
    conditions: Dict[str, Any] = field(default_factory=dict)  # 额外条件
    required_context: Optional[List[str]] = None  # 需要的上下文字段
    
    # 统计
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None
    
    # 元数据
    enabled: bool = True
    priority: int = 100  # 越小优先级越高
    tags: Set[str] = field(default_factory=set)
    
    # 性能配置
    compiled_pattern: Optional[Pattern] = None  # 编译后的正则
    is_regex: bool = False
    
    def __post_init__(self):
        """后处理初始化"""
        if self.trigger_type == TriggerType.PATTERN:
            try:
                self.compiled_pattern = re.compile(self.trigger_value)
                self.is_regex = True
            except re.error as e:
                logger.error(f"正则编译失败: {self.trigger_value}, error: {e}")
                self.compiled_pattern = None
                self.is_regex = False
    
    def matches(self, text: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """检查文本是否匹配规则"""
        if not self.enabled:
            return False
        
        matched = False
        
        # 关键词/正则匹配
        if self.trigger_type == TriggerType.KEYWORD:
            matched = self.trigger_value in text
        elif self.trigger_type == TriggerType.PATTERN and self.compiled_pattern:
            matched = bool(self.compiled_pattern.search(text))
        elif self.trigger_type == TriggerType.MENTION:
            matched = self.trigger_value in text  # @智能体
        elif self.trigger_type == TriggerType.EMOTION:
            matched = self.trigger_value in text
        
        if not matched:
            return False
        
        # 检查额外条件
        if self.conditions and context:
            for key, value in self.conditions.items():
                if key not in context:
                    return False
                if context[key] != value:
                    return False
        
        # 更新统计
        if matched:
            self.hit_count += 1
            self.last_hit_at = datetime.now()
        
        return matched
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "trigger_type": self.trigger_type.value,
            "trigger_value": self.trigger_value,
            "activation_level": self.activation_level.value,
            "target_agents": self.target_agents,
            "action": self.action,
            "conditions": self.conditions,
            "required_context": self.required_context,
            "hit_count": self.hit_count,
            "last_hit_at": self.last_hit_at.isoformat() if self.last_hit_at else None,
            "enabled": self.enabled,
            "priority": self.priority,
            "tags": list(self.tags)
        }


@dataclass
class ActivationResult:
    """激活结果"""
    activation_id: str
    message_id: str
    tenant_id: str
    
    # 激活信息
    should_process: bool
    activation_level: ActivationLevel
    matched_rules: List[str]  # 匹配的规则ID列表
    
    # 任务分发
    target_tasks: List[Dict[str, Any]]  # 目标任务列表
    
    # 元数据
    confidence: float = 1.0
    reasoning: str = ""
    processing_time: float = 0.0
    
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "activation_id": self.activation_id,
            "message_id": self.message_id,
            "tenant_id": self.tenant_id,
            "should_process": self.should_process,
            "activation_level": self.activation_level.value,
            "matched_rules": self.matched_rules,
            "target_tasks": self.target_tasks,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass 
class KeywordStats:
    """关键词统计"""
    total_messages: int = 0
    filtered_messages: int = 0
    activated_messages: int = 0
    
    # 规则统计
    rules_total: int = 0
    rules_active: int = 0
    
    # 性能指标
    avg_processing_time: float = 0.0
    total_processing_time: float = 0.0
    
    # 时间窗口统计
    messages_last_minute: int = 0
    messages_last_hour: int = 0
    
    last_updated: datetime = field(default_factory=datetime.now)


class KeywordActivator:
    """
    关键词激活器
    核心功能：
    1. 轻量级正则/规则拦截器 - 省钱滤网
    2. 关键词激活与匹配
    3. 静默监控模式
    4. 多租户规则管理
    5. 智能任务提取
    """
    
    # 默认触发关键词（财务报销场景）
    DEFAULT_TRIGGER_KEYWORDS = [
        "报销", "出差", "花了", "发票", "天气",
        "@智能体", "@助手", "费用", "预算",
        "审批", "申请", "差旅", "机票", "酒店",
        "餐费", "交通", "补贴"
    ]
    
    # 紧急关键词（高优先级）
    HIGH_PRIORITY_KEYWORDS = [
        "紧急", "加急", "急", "马上", "立刻",
        "错误", "问题", "bug", "失败"
    ]
    
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        enable_default_rules: bool = True,
        enable_mention_detection: bool = True,
        max_rules_per_tenant: int = 100,
        case_sensitive: bool = False,
        cache_size: int = 1000
    ):
        """
        初始化关键词激活器
        
        Args:
            tenant_id: 租户ID
            enable_default_rules: 是否启用默认规则
            enable_mention_detection: 是否启用@检测
            max_rules_per_tenant: 每个租户最大规则数
            case_sensitive: 是否大小写敏感
            cache_size: 匹配结果缓存大小
        """
        self.tenant_id = tenant_id
        self.enable_mention_detection = enable_mention_detection
        self.max_rules_per_tenant = max_rules_per_tenant
        self.case_sensitive = case_sensitive
        
        # 规则存储
        self._rules: Dict[str, Dict[str, TriggerRule]] = defaultdict(dict)  # tenant_id -> rule_id -> rule
        
        # 缓存
        self._cache: Dict[str, bool] = {}  # message_hash -> match_result
        self._cache_size = cache_size
        
        # 统计信息
        self._stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
        
        # 回调函数
        self._activation_callbacks: List[Callable] = []
        
        # 初始化默认规则
        if enable_default_rules:
            self._init_default_rules()
        
        # 编译全局正则
        self._mention_pattern = re.compile(r'@[\w]+')
    
    def _init_default_rules(self) -> None:
        """初始化默认触发规则"""
        tenant = self.tenant_id or "default"
        
        # 财务相关关键词
        finance_keywords = [
            "报销", "发票", "费用", "预算", "审批", "申请",
            "差旅", "机票", "酒店", "餐费", "交通", "补贴",
            "付款", "收款", "账单", "结算"
        ]
        
        for keyword in finance_keywords:
            rule = TriggerRule(
                rule_id=self._generate_rule_id("finance", keyword),
                name=f"财务-{keyword}",
                tenant_id=tenant,
                trigger_type=TriggerType.KEYWORD,
                trigger_value=keyword if self.case_sensitive else keyword.lower(),
                target_agents=["FinanceSpecialist"],
                action="finance_query"
            )
            self.add_rule(rule)
        
        # 天气查询关键词
        weather_keywords = ["天气", "气温", "温度", "下雨", "晴天"]
        
        for keyword in weather_keywords:
            rule = TriggerRule(
                rule_id=self._generate_rule_id("weather", keyword),
                name=f"天气-{keyword}",
                tenant_id=tenant,
                trigger_type=TriggerType.KEYWORD,
                trigger_value=keyword if self.case_sensitive else keyword.lower(),
                target_agents=["DailyServiceSpecialist"],
                action="weather_query"
            )
            self.add_rule(rule)
        
        # 紧急关键词（高优先级）
        for keyword in self.HIGH_PRIORITY_KEYWORDS:
            rule = TriggerRule(
                rule_id=self._generate_rule_id("urgent", keyword),
                name=f"紧急-{keyword}",
                tenant_id=tenant,
                trigger_type=TriggerType.KEYWORD,
                trigger_value=keyword if self.case_sensitive else keyword.lower(),
                activation_level=ActivationLevel.HIGH,
                target_agents=["FinanceSpecialist", "Coordinator"],
                action="urgent_processing"
            )
            self.add_rule(rule)
        
        # @智能体提及规则
        if self.enable_mention_detection:
            rule = TriggerRule(
                rule_id=self._generate_rule_id("mention", "any"),
                name="智能体提及",
                tenant_id=tenant,
                trigger_type=TriggerType.MENTION,
                trigger_value="@智能体",
                activation_level=ActivationLevel.NORMAL,
                target_agents=["Coordinator"],
                action="direct_mention"
            )
            self.add_rule(rule)
        
        logger.info(f"初始化了 {len(self._rules.get(tenant, {}))} 条默认规则")
    
    def _generate_rule_id(self, category: str, keyword: str) -> str:
        """生成规则ID"""
        content = f"{category}:{keyword}:{datetime.now().isoformat()}"
        hash_str = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"rule_{category}_{hash_str}"
    
    def add_rule(self, rule: TriggerRule) -> bool:
        """
        添加触发规则
        
        Args:
            rule: 触发规则
            
        Returns:
            bool: 是否添加成功
        """
        tenant = rule.tenant_id
        
        # 检查规则数量限制
        if len(self._rules[tenant]) >= self.max_rules_per_tenant:
            logger.warning(f"租户 {tenant} 规则数量已达上限 ({self.max_rules_per_tenant})")
            return False
        
        # 检查重复规则
        if rule.rule_id in self._rules[tenant]:
            logger.warning(f"规则 {rule.rule_id} 已存在")
            return False
        
        # 编译正则（如果需要）
        if rule.trigger_type == TriggerType.PATTERN:
            try:
                pattern = rule.trigger_value if self.case_sensitive else rule.trigger_value.lower()
                rule.compiled_pattern = re.compile(pattern)
                rule.is_regex = True
            except re.error as e:
                logger.error(f"正则编译失败: {rule.trigger_value}, error: {e}")
                return False
        
        self._rules[tenant][rule.rule_id] = rule
        
        # 更新统计
        if tenant in self._stats:
            self._stats[tenant].rules_total += 1
            self._stats[tenant].rules_active += 1
        
        logger.info(f"添加规则: {rule.rule_id} (keyword={rule.trigger_value})")
        return True
    
    def remove_rule(self, tenant_id: str, rule_id: str) -> bool:
        """删除规则"""
        if rule_id in self._rules[tenant_id]:
            rule = self._rules[tenant_id].pop(rule_id)
            
            # 更新统计
            if tenant_id in self._stats:
                self._stats[tenant_id].rules_active -= 1
            
            logger.info(f"删除规则: {rule_id}")
            return True
        return False
    
    def get_rules(self, tenant_id: Optional[str] = None) -> List[TriggerRule]:
        """获取规则列表"""
        if tenant_id:
            return list(self._rules.get(tenant_id, {}).values())
        return [rule for rules in self._rules.values() for rule in rules.values()]
    
    def enable_rule(self, tenant_id: str, rule_id: str, enabled: bool = True) -> bool:
        """启用/禁用规则"""
        if rule_id in self._rules[tenant_id]:
            self._rules[tenant_id][rule_id].enabled = enabled
            
            if tenant_id in self._stats:
                if enabled:
                    self._stats[tenant_id].rules_active += 1
                else:
                    self._stats[tenant_id].rules_active -= 1
            
            return True
        return False
    
    def should_process(self, message: str, tenant_id: Optional[str] = None) -> bool:
        """
        快速检查消息是否需要处理（省钱滤网核心）
        
        Args:
            message: 消息文本
            tenant_id: 租户ID
            
        Returns:
            bool: 是否应该处理
        """
        start_time = datetime.now()
        tenant = tenant_id or self.tenant_id or "default"
        
        # 更新统计
        if tenant not in self._stats:
            self._stats[tenant] = KeywordStats()
        self._stats[tenant].total_messages += 1
        
        # 检查缓存
        message_hash = self._compute_hash(message)
        if message_hash in self._cache:
            return self._cache[message_hash]
        
        # 快速关键词预检
        if not self._quick_keyword_check(message, tenant):
            self._stats[tenant].filtered_messages += 1
            self._cache_result(message_hash, False)
            return False
        
        # 详细规则匹配
        result = self._match_rules(message, None, tenant)
        
        # 缓存结果
        self._cache_result(message_hash, result.should_process)
        
        if result.should_process:
            self._stats[tenant].activated_messages += 1
        
        # 更新处理时间统计
        processing_time = (datetime.now() - start_time).total_seconds()
        self._stats[tenant].total_processing_time += processing_time
        self._stats[tenant].avg_processing_time = (
            self._stats[tenant].total_processing_time / max(1, self._stats[tenant].total_messages)
        )
        
        return result.should_process
    
    def _compute_hash(self, message: str) -> str:
        """计算消息哈希"""
        return hashlib.md5(message.encode()).hexdigest()
    
    def _cache_result(self, message_hash: str, result: bool) -> None:
        """缓存匹配结果"""
        if len(self._cache) >= self._cache_size:
            # LRU: 删除最早的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[message_hash] = result
    
    def _quick_keyword_check(self, message: str, tenant_id: str) -> bool:
        """
        快速关键词预检
        这是省钱滤网的核心 - 在调用大模型之前先做轻量级检查
        """
        # 如果启用了默认规则，只检查默认关键词
        if tenant_id in self._rules and self._rules[tenant_id]:
            # 获取所有关键词
            keywords = set()
            for rule in self._rules[tenant_id].values():
                if rule.trigger_type == TriggerType.KEYWORD:
                    keywords.add(rule.trigger_value)
            
            # 检查是否包含任何关键词
            text = message if self.case_sensitive else message.lower()
            for keyword in keywords:
                if keyword in text:
                    return True
            
            return False
        
        # 默认检查
        text = message if self.case_sensitive else message.lower()
        
        for keyword in self.DEFAULT_TRIGGER_KEYWORDS:
            if keyword in text:
                return True
        
        # @检测
        if self.enable_mention_detection and self._mention_pattern.search(message):
            return True
        
        return False
    
    def _match_rules(self, message: str, context: Optional[Dict[str, Any]], tenant_id: str) -> ActivationResult:
        """匹配所有规则"""
        activation_id = str(uuid.uuid4())
        
        # 获取租户规则
        rules = self._rules.get(tenant_id, {})
        
        # 按优先级排序
        sorted_rules = sorted(
            rules.values(),
            key=lambda r: r.priority
        )
        
        # 匹配检查
        matched_rules = []
        highest_level = ActivationLevel.IGNORE
        text = message if self.case_sensitive else message.lower()
        
        for rule in sorted_rules:
            if not rule.enabled:
                continue
            
            if rule.matches(text, context):
                matched_rules.append(rule.rule_id)
                
                # 更新最高激活级别
                if rule.activation_level.value > highest_level.value:
                    highest_level = rule.activation_level
        
        # 确定是否处理
        should_process = (
            len(matched_rules) > 0 and 
            highest_level != ActivationLevel.IGNORE
        )
        
        return ActivationResult(
            activation_id=activation_id,
            message_id="",
            tenant_id=tenant_id,
            should_process=should_process,
            activation_level=highest_level,
            matched_rules=matched_rules
        )
    
    def activate(
        self,
        message: str,
        message_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        extract_tasks: bool = True
    ) -> ActivationResult:
        """
        激活处理
        
        Args:
            message: 消息文本
            message_id: 消息ID
            tenant_id: 租户ID
            context: 额外上下文
            extract_tasks: 是否提取任务
            
        Returns:
            ActivationResult: 激活结果
        """
        start_time = datetime.now()
        tenant = tenant_id or self.tenant_id or "default"
        
        # 匹配规则
        result = self._match_rules(message, context, tenant)
        result.message_id = message_id or str(uuid.uuid4())
        
        # 提取任务（如果需要）
        if extract_tasks and result.should_process:
            result.target_tasks = self._extract_tasks(message, result.matched_rules, tenant)
        
        # 生成推理
        result.reasoning = self._generate_reasoning(result)
        
        # 计算置信度
        result.confidence = self._calculate_confidence(result)
        
        # 更新处理时间
        result.processing_time = (datetime.now() - start_time).total_seconds()
        
        # 触发回调
        self._trigger_callbacks(result)
        
        return result
    
    def _extract_tasks(self, message: str, matched_rule_ids: List[str], tenant_id: str) -> List[Dict[str, Any]]:
        """从消息中提取任务"""
        tasks = []
        
        # 获取匹配的规则
        rules = self._rules.get(tenant_id, {})
        matched_rules = [rules[rid] for rid in matched_rule_ids if rid in rules]
        
        # 按规则提取任务
        for rule in matched_rules:
            # 根据规则的动作类型生成任务
            if rule.action:
                task = {
                    "task_id": str(uuid.uuid4()),
                    "target_agent": rule.target_agents[0] if rule.target_agents else "Coordinator",
                    "action": rule.action,
                    "params": self._extract_params(message, rule),
                    "priority": rule.priority,
                    "activation_level": rule.activation_level.value
                }
                tasks.append(task)
        
        # 去重
        seen = set()
        unique_tasks = []
        for task in tasks:
            key = f"{task['target_agent']}:{task['action']}"
            if key not in seen:
                seen.add(key)
                unique_tasks.append(task)
        
        return unique_tasks
    
    def _extract_params(self, message: str, rule: TriggerRule) -> Dict[str, Any]:
        """提取任务参数"""
        params = {
            "original_message": message,
            "trigger_keyword": rule.trigger_value
        }
        
        # 简单参数提取（可用LLM增强）
        text = message if self.case_sensitive else message.lower()
        
        # 金额提取
        amount_pattern = r'(\d+(?:\.\d+)?)\s*(?:元|块|千|万)'
        amounts = re.findall(amount_pattern, text)
        if amounts:
            params["amounts"] = [float(a) for a in amounts]
        
        # 地点提取
        location_keywords = ["去", "到", "在", "出差"]
        for keyword in location_keywords:
            if keyword in text:
                idx = text.find(keyword)
                # 简单提取（实际应该用NER）
                params["location_hint"] = message[idx:idx+10]
                break
        
        return params
    
    def _generate_reasoning(self, result: ActivationResult) -> str:
        """生成推理说明"""
        if not result.should_process:
            return f"消息未匹配任何规则（检查了 {len(result.matched_rules)} 条规则），已静默过滤以节省Token"
        
        matched = len(result.matched_rules)
        level = result.activation_level.value
        
        reasoning_parts = [
            f"匹配了 {matched} 条触发规则",
            f"激活级别: {level}",
        ]
        
        if matched > 1:
            reasoning_parts.append("消息涉及多个领域，将并行分发处理")
        
        return "。".join(reasoning_parts)
    
    def _calculate_confidence(self, result: ActivationResult) -> float:
        """计算置信度"""
        if not result.should_process:
            return 0.0
        
        # 基于匹配规则数量
        base_confidence = min(0.9, 0.6 + 0.1 * len(result.matched_rules))
        
        # 基于激活级别
        level_weights = {
            ActivationLevel.URGENT: 1.0,
            ActivationLevel.HIGH: 0.9,
            ActivationLevel.NORMAL: 0.8,
            ActivationLevel.LOW: 0.7
        }
        level_weight = level_weights.get(result.activation_level, 0.8)
        
        return base_confidence * level_weight
    
    def register_callback(self, callback: Callable[[ActivationResult], None]) -> None:
        """注册激活回调"""
        self._activation_callbacks.append(callback)
    
    def _trigger_callbacks(self, result: ActivationResult) -> None:
        """触发回调"""
        for callback in self._activation_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")
    
    def get_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        if tenant_id:
            stats = self._stats.get(tenant_id)
            if stats:
                return {
                    "total_messages": stats.total_messages,
                    "filtered_messages": stats.filtered_messages,
                    "activated_messages": stats.activated_messages,
                    "filter_rate": f"{stats.filtered_messages/max(1,stats.total_messages)*100:.1f}%",
                    "rules_total": stats.rules_total,
                    "rules_active": stats.rules_active,
                    "avg_processing_time": f"{stats.avg_processing_time*1000:.2f}ms"
                }
            return {}
        
        # 聚合统计
        total_stats = KeywordStats()
        for stats in self._stats.values():
            total_stats.total_messages += stats.total_messages
            total_stats.filtered_messages += stats.filtered_messages
            total_stats.activated_messages += stats.activated_messages
            total_stats.total_processing_time += stats.total_processing_time
        
        total_stats.avg_processing_time = (
            total_stats.total_processing_time / max(1, total_stats.total_messages)
        )
        
        return {
            "total_messages": total_stats.total_messages,
            "filtered_messages": total_stats.filtered_messages,
            "activated_messages": total_stats.activated_messages,
            "filter_rate": f"{total_stats.filtered_messages/max(1,total_stats.total_messages)*100:.1f}%",
            "avg_processing_time": f"{total_stats.avg_processing_time*1000:.2f}ms",
            "tenant_count": len(self._stats)
        }
    
    def reset_stats(self, tenant_id: Optional[str] = None) -> None:
        """重置统计"""
        if tenant_id:
            if tenant_id in self._stats:
                self._stats[tenant_id] = KeywordStats()
        else:
            self._stats.clear()
    
    def export_rules(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """导出规则"""
        rules = self.get_rules(tenant_id)
        return [rule.to_dict() for rule in rules]
    
    def import_rules(self, rules_data: List[Dict[str, Any]], tenant_id: Optional[str] = None) -> int:
        """
        批量导入规则
        
        Args:
            rules_data: 规则数据列表
            tenant_id: 租户ID
            
        Returns:
            int: 成功导入的规则数量
        """
        imported = 0
        
        for rule_data in rules_data:
            try:
                # 处理枚举值
                if 'trigger_type' in rule_data:
                    rule_data['trigger_type'] = TriggerType(rule_data['trigger_type'])
                if 'activation_level' in rule_data:
                    rule_data['activation_level'] = ActivationLevel(rule_data['activation_level'])
                
                # 处理set类型
                if 'tags' in rule_data and isinstance(rule_data['tags'], list):
                    rule_data['tags'] = set(rule_data['tags'])
                
                rule = TriggerRule(**rule_data)
                
                # 覆盖租户ID
                if tenant_id:
                    rule.tenant_id = tenant_id
                
                if self.add_rule(rule):
                    imported += 1
                    
            except Exception as e:
                logger.error(f"导入规则失败: {rule_data.get('rule_id', 'unknown')}, error: {e}")
        
        return imported


class StreamingKeywordActivator(KeywordActivator):
    """流式关键词激活器 - 支持流式处理"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._streaming_active = False
        self._streaming_buffer = ""
    
    async def activate_stream(
        self,
        message_stream: str,
        message_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> AsyncGenerator[ActivationResult, None]:
        """
        流式激活处理
        
        Args:
            message_stream: 消息流
            message_id: 消息ID
            tenant_id: 租户ID
            
        Yields:
            ActivationResult: 激活结果
        """
        self._streaming_active = True
        self._streaming_buffer = ""
        
        buffer_size = 100  # 每100字符检查一次
        
        async for chunk in self._chunk_generator(message_stream, buffer_size):
            self._streaming_buffer += chunk
            
            # 检查是否需要处理
            if len(self._streaming_buffer) >= buffer_size:
                result = self._quick_check_and_activate(
                    self._streaming_buffer,
                    message_id,
                    tenant_id
                )
                
                if result:
                    yield result
    
    async def _chunk_generator(self, text: str, chunk_size: int) -> AsyncGenerator[str, None]:
        """异步分块生成器"""
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]
            await asyncio.sleep(0)  # 让出控制权
    
    def _quick_check_and_activate(
        self,
        buffer: str,
        message_id: Optional[str],
        tenant_id: Optional[str]
    ) -> Optional[ActivationResult]:
        """快速检查并激活"""
        # 简单实现：只在缓冲区末尾检查
        if self.should_process(buffer, tenant_id):
            return self.activate(buffer, message_id, tenant_id, extract_tasks=False)
        return None
