"""
结果合成器 (Result Synthesizer) - 智能组件版

一个专业的智能组件，负责：
1. 多专家结果合成与整合
2. 冲突检测与智能解决
3. 置信度评估与质量审查
4. 输出格式化与美化

设计定位：智能组件，非智能体
- 不具备自主性和推理能力
- 不继承BaseAgent基类
- 提供专业的结果处理服务
"""

import asyncio
import re
from app.utils.json_compat import json
import random
import uuid
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SynthesisStrategy(str, Enum):
    """合成策略枚举"""
    CONCATENATE = "concatenate"      # 简单拼接
    MERGE = "merge"                  # 合并整合
    HIERARCHICAL = "hierarchical"    # 层次化组织
    NARRATIVE = "narrative"          # 叙事化生成（使用LLM）
    CUSTOM = "custom"                # 自定义模板


class ConflictResolution(str, Enum):
    """冲突解决策略枚举"""
    LATEST = "latest"                # 使用最新结果
    HIGHEST_CONFIDENCE = "highest_confidence"  # 使用置信度最高的结果
    VOTE = "vote"                    # 多数投票
    PRIORITY = "priority"            # 按优先级选择
    MANUAL = "manual"                # 需要人工介入


@dataclass
class SynthesisInput:
    """合成输入数据结构"""
    task_id: str
    source_agent: str
    source_type: str
    content: Any
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "source_agent": self.source_agent,
            "source_type": self.source_type,
            "content": self.content,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }


@dataclass
class ConflictInfo:
    """冲突信息"""
    conflict_id: str
    source_ids: List[str]
    conflict_type: str
    resolution: str = ""


@dataclass
class SynthesisResult:
    """合成结果"""
    synthesis_id: str
    task_id: str
    strategy: SynthesisStrategy
    raw_inputs: List[SynthesisInput]
    conflicts: List[Dict[str, Any]]
    resolved_content: Dict[str, Any]
    final_response: str
    confidence: float
    quality_score: float
    execution_time: float
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "synthesis_id": self.synthesis_id,
            "task_id": self.task_id,
            "strategy": self.strategy.value if isinstance(self.strategy, SynthesisStrategy) else self.strategy,
            "raw_inputs": [inp.to_dict() for inp in self.raw_inputs],
            "conflicts": self.conflicts,
            "resolved_content": self.resolved_content,
            "final_response": self.final_response,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "execution_time": self.execution_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata
        }


class OutputReviewResult(BaseModel):
    """输出审查结果"""
    is_approved: bool = Field(description="是否通过审查")
    score: float = Field(0.0, description="质量评分 0-10")
    issues: List[str] = Field(default_factory=list, description="发现的问题列表")
    suggestion: str = Field("", description="改进建议")
    needs_regenerate: bool = Field(False, description="是否需要重新生成")


class SpecialistInsight(BaseModel):
    """专家洞察结构"""
    specialist_type: str = Field(description="专家类型：finance/tax/legal")
    key_findings: List[str] = Field(description="关键发现列表")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="关键指标")
    recommendations: List[str] = Field(default_factory=list, description="建议列表")
    risks: List[str] = Field(default_factory=list, description="风险提示")
    confidence: float = Field(description="置信度 0-1")


class ExecutiveSummary(BaseModel):
    """高管摘要"""
    overall_status: str = Field(description="整体状态：良好/一般/需要关注")
    key_concerns: List[str] = Field(description="核心关注点")
    immediate_actions: List[str] = Field(description="立即行动项")
    summary_text: str = Field(description="摘要说明（2-3句话）")


class FinalExecutiveReport(BaseModel):
    """最终执行报告 - 强类型结构化输出"""
    executive_summary: ExecutiveSummary = Field(description="高管摘要")
    specialist_insights: List[SpecialistInsight] = Field(description="各专家洞察")
    critical_alerts: List[str] = Field(default_factory=list, description="红牌警告")
    key_metrics: Dict[str, Any] = Field(default_factory=dict, description="关键指标汇总")
    next_steps: List[str] = Field(default_factory=list, description="后续步骤")
    confidence_level: float = Field(description="整体置信度 0-1")
    data_sources: List[str] = Field(default_factory=list, description="数据来源")


class ResultSynthesizerPrompts:
    """结果合成器提示词管理器"""
    
    _prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "agents" / "output"
    _prompts_cache: Dict[str, str] = {}
    
    NO_RESULT_ANSWERS = [
        "抱歉，我暂时没有找到相关的信息。能否请您提供更多细节或换个方式描述您的问题？",
        "对不起，知识库中暂未收录相关内容。建议您换个关键词试试，或者联系相关人员获取帮助。",
        "很抱歉，我未能找到匹配的信息。请您尝试调整问题描述，我会尽力为您提供帮助。",
    ]
    
    @classmethod
    def _load_prompt_file(cls, filename: str) -> str:
        """从文件加载提示词"""
        file_path = cls._prompt_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return ""
    
    @classmethod
    def _extract_prompt_section(cls, content: str, section_name: str) -> str:
        """从合并的提示词文件中提取特定部分"""
        pattern = rf'## \d+\. [^\n]+\({section_name}\)\n(.*?)(?=\n---\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    @classmethod
    def _load_merged_prompts(cls) -> Dict[str, str]:
        """加载合并的提示词文件"""
        if cls._prompts_cache:
            return cls._prompts_cache
        
        prompts_file = cls._prompt_dir / "prompts.md"
        if prompts_file.exists():
            content = prompts_file.read_text(encoding="utf-8")
            cls._prompts_cache = {
                "final_output": cls._extract_prompt_section(content, "final_output"),
                "regeneration": cls._extract_prompt_section(content, "regeneration"),
                "editor_in_chief": cls._extract_prompt_section(content, "editor_in_chief"),
                "synthesis": cls._extract_prompt_section(content, "synthesis"),
                "quick_review": cls._extract_prompt_section(content, "quick_review"),
                "deep_review": cls._extract_prompt_section(content, "deep_review"),
            }
        return cls._prompts_cache
    
    @classmethod
    def get_synthesis_prompt(cls, user_query: str, specialist_results: str) -> str:
        """获取整合提示词"""
        prompts = cls._load_merged_prompts()
        template = prompts.get("synthesis", "")
        if template:
            try:
                return template.format(user_query=user_query, specialist_results=specialist_results)
            except KeyError as e:
                logger.error(f"❌ [整合提示词] 模板变量缺失: {e}，使用备用提示词")
        return f"请整合以下专家结果回答用户问题：{user_query}\n\n{specialist_results}"
    
    @classmethod
    def get_random_no_result_answer(cls) -> str:
        """获取随机无结果回答"""
        return random.choice(cls.NO_RESULT_ANSWERS)
    
    @classmethod
    def get_editor_in_chief_prompt(cls, user_query: str, specialist_results: str) -> str:
        """主编提示词 - 从外部文件加载"""
        prompts = cls._load_merged_prompts()
        template = prompts.get("editor_in_chief", "")
        
        if template:
            # 使用更智能的占位符提取：排除 JSON Schema 中的 {{}} 和 {{
            placeholder_pattern = r'(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\{)'
            placeholders = re.findall(placeholder_pattern, template)
            logger.debug(f"📝 [主编提示词] 模板占位符: {placeholders}")
            
            required_vars = {'user_query', 'specialist_results'}
            template_vars = set(placeholders)
            logger.warning(f"📝 [主编提示词] 需要的变量: {required_vars}, 模板中的变量: {template_vars}")
            
            if required_vars.issubset(template_vars):
                try:
                    format_kwargs = {
                        "user_query": user_query,
                        "specialist_results": specialist_results
                    }
                    for var in template_vars:
                        if var not in format_kwargs:
                            format_kwargs[var] = ""
                    
                    # 处理 JSON Schema 中的 {{}} - 替换为临时占位符后再 format
                    temp_template = template.replace("{{", "<<DOUBLE_BRACE>>").replace("}}", "<<DOUBLE_BRACE_END>>")
                    result = temp_template.format(**format_kwargs)
                    # 恢复 {{ 和 }}
                    result = result.replace("<<DOUBLE_BRACE>>", "{").replace("<<DOUBLE_BRACE_END>>", "}")
                    logger.info(f"✅ [主编提示词] 格式化成功")
                    return result
                except KeyError as e:
                    logger.error(f"❌ [主编提示词] 格式化失败 KeyError: {e}")
                    logger.error(f"📝 [主编提示词] 调试: template_vars={template_vars}, e={e}")
            else:
                missing = required_vars - template_vars
                logger.error(f"❌ [主编提示词] 模板缺少必要占位符: {missing}")
        
        logger.warning("⚠️ [主编提示词] 使用备用提示词")
        return f"""你是顶级企业咨询公司的主编合伙人，负责将多位专家的生肉数据分析整合成一份专业的执行报告。

【用户问题】
{user_query}

【专家生肉数据】
{specialist_results}

### 你的任务
1. 分析整合各专家返回的生肉数据
2. 去重合并，保留最有价值的洞察
3. 输出一份专业的 Markdown 格式报告
4. 绝对不要编造数据
5. 数字必须精确
6. **绝对不要使用 markdown 代码块包裹全文** - 直接输出 Markdown 正文

### 输出要求
直接输出 Markdown 格式的报告文章，不要使用 ```markdown 或 ``` 包裹全文！"""


class ResultSynthesizer:
    """
    结果合成器 - 智能组件
    
    核心功能：
    1. 多源结果整合：将多个专家的分析结果合成为统一输出
    2. 冲突智能解决：检测并解决不同专家结果间的矛盾
    3. 质量自动审查：确保输出符合质量标准
    4. 格式专业美化：生成美观、易读的最终报告
    
    设计原则：
    - 组件化：作为功能组件，非智能体
    - 专业性：专注于结果合成和格式化
    - 可靠性：提供稳定的质量保障
    - 易用性：简洁清晰的API接口
    """
    
    def __init__(
        self,
        llm_adapter=None,
        default_strategy: SynthesisStrategy = SynthesisStrategy.MERGE,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE,
        max_inputs: int = 10
    ):
        """
        初始化结果合成器
        
        Args:
            llm_adapter: LLM适配器（可选，用于叙事化合成）
            default_strategy: 默认合成策略
            conflict_resolution: 冲突解决策略
            max_inputs: 最大输入数量
        """
        self.llm = llm_adapter
        self.prompts = ResultSynthesizerPrompts()
        self.default_strategy = default_strategy
        self.conflict_resolution = conflict_resolution
        self.max_inputs = max_inputs
        
        self._inputs: List[SynthesisInput] = []
        self._conflicts: List[ConflictInfo] = []
        self._current_task_id: Optional[str] = None
        
        # 敏感信息检测模式
        self.SENSITIVE_PATTERNS = [
            r'密码[：:]\s*\S+',
            r'secret[：:]\s*\S+',
            r'秘[密钥][：:]\s*\S+',
            r'\d{6,}[-_]?\d{6,}',
            r'报销暗号[：:]\s*\S+',
            r'启动密码[：:]\s*\S+',
            r'接口密钥[：:]\s*\S+',
            r'api[_-]?key[：:]\s*\S+',
            r'token[：:]\s*\S+',
            r'Bearer\s+\S+',
        ]
        
        # 内部标记检测模式
        self.INTERNAL_PATTERNS = [
            r'\[.*?\]',
            r'__\w+__',
            r'Observation:',
            r'Thought:',
            r'Action:',
            r'Action Input:',
            r'Final Answer:',
            r'\[工具调用\]',
            r'\[检索结果\]',
            r'\[错误\]',
            r'\[超时\]',
            r'\[重试\]',
        ]
        
        # 不良开头检测模式
        self.BAD_START_PATTERNS = [
            r'^抱歉.*?[，,]\s*(我|系统|这个)',
            r'^对不起.*?[，,]\s*(我|系统)',
            r'^根据.*?(显示|查询|检索)',
            r'^\[检索结果为空\]$',
            r'^很抱歉.*?[，,]',
            r'^对不起.*?[，,]',
        ]
        
        logger.info(f"✅ [ResultSynthesizer] 初始化完成，默认策略: {default_strategy}")
    
    def add_input(
        self,
        task_id: str,
        source_agent: str,
        source_type: str,
        content: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        添加单个合成输入
        
        Args:
            task_id: 任务ID
            source_agent: 来源智能体
            source_type: 来源类型 (finance, tax, legal, etc.)
            content: 内容
            confidence: 置信度 0-1
            metadata: 元数据
            
        Returns:
            是否添加成功
        """
        if len(self._inputs) >= self.max_inputs:
            logger.warning(f"⚠️ [ResultSynthesizer] 输入数量已达上限 {self.max_inputs}")
            return False
        
        synthesis_input = SynthesisInput(
            task_id=task_id,
            source_agent=source_agent,
            source_type=source_type,
            content=content,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        self._inputs.append(synthesis_input)
        self._current_task_id = task_id
        
        logger.debug(f"📥 [ResultSynthesizer] 添加输入: {source_agent} ({source_type})")
        return True
    
    def add_result(
        self,
        task_id: str,
        source_agent: str,
        source_type: str,
        content: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        添加单个结果（add_input 的别名，保持兼容性）
        """
        return self.add_input(
            task_id=task_id,
            source_agent=source_agent,
            source_type=source_type,
            content=content,
            confidence=confidence,
            metadata=metadata
        )
    
    def add_inputs_batch(self, results: List[Dict[str, Any]]) -> int:
        """
        批量添加合成输入
        
        Args:
            results: 结果列表
            
        Returns:
            成功添加的数量
        """
        added = 0
        for result in results:
            success = self.add_input(
                task_id=result.get("task_id", str(uuid.uuid4())),
                source_agent=result.get("source_agent", "unknown"),
                source_type=result.get("source_type", "general"),
                content=result.get("content", {}),
                confidence=result.get("confidence", 1.0),
                metadata=result.get("metadata", {})
            )
            if success:
                added += 1
        return added
    
    def clear_inputs(self) -> None:
        """清空所有输入"""
        self._inputs.clear()
        self._conflicts.clear()
        self._current_task_id = None
    
    def get_inputs_summary(self) -> Dict[str, Any]:
        """获取输入摘要"""
        return {
            "count": len(self._inputs),
            "sources": list(set(inp.source_agent for inp in self._inputs)),
            "types": list(set(inp.source_type for inp in self._inputs)),
            "conflicts": len(self._conflicts)
        }
    
    async def detect_conflicts(self) -> List[ConflictInfo]:
        """检测所有输入之间的冲突"""
        conflicts = []
        
        for i, input1 in enumerate(self._inputs):
            for input2 in self._inputs[i + 1:]:
                conflict = await self._check_pair_conflict(input1, input2)
                if conflict:
                    conflicts.append(conflict)
        
        self._conflicts = conflicts
        
        if conflicts:
            logger.warning(f"⚠️ [ResultSynthesizer] 检测到 {len(conflicts)} 个冲突")
        
        return conflicts
    
    async def _check_pair_conflict(
        self,
        input1: SynthesisInput,
        input2: SynthesisInput
    ) -> Optional[ConflictInfo]:
        """检查两个输入之间的冲突"""
        
        if input1.source_type == input2.source_type:
            content1_str = json.dumps(input1.content, ensure_ascii=False)
            content2_str = json.dumps(input2.content, ensure_ascii=False)
            
            if content1_str == content2_str:
                return None
        
        if abs((input1.timestamp - input2.timestamp).total_seconds()) > 3600:
            return ConflictInfo(
                conflict_id=str(uuid.uuid4()),
                source_ids=[input1.task_id, input2.task_id],
                conflict_type="temporal",
                resolution=""
            )
        
        return ConflictInfo(
            conflict_id=str(uuid.uuid4()),
            source_ids=[input1.task_id, input2.task_id],
            conflict_type="semantic",
            resolution=""
        )
    
    async def resolve_conflicts(self, strategy: Optional[ConflictResolution] = None) -> Dict[str, str]:
        """
        解决所有冲突
        
        Args:
            strategy: 冲突解决策略（覆盖默认）
            
        Returns:
            冲突ID到解决方案的映射
        """
        strategy = strategy or self.conflict_resolution
        resolutions = {}
        
        for conflict in self._conflicts:
            resolution = await self._resolve_single_conflict(conflict, strategy)
            conflict.resolution = resolution
            resolutions[conflict.conflict_id] = resolution
        
        return resolutions
    
    async def _resolve_single_conflict(
        self,
        conflict: ConflictInfo,
        strategy: ConflictResolution
    ) -> str:
        """解决单个冲突"""
        if strategy == ConflictResolution.HIGHEST_CONFIDENCE:
            confidences = {
                inp.task_id: inp.confidence
                for inp in self._inputs
                if inp.task_id in conflict.source_ids
            }
            winner_id = max(confidences, key=confidences.get)
            
            for inp in self._inputs:
                if inp.task_id == winner_id:
                    return f"采用来自 {inp.source_agent} 的结果（置信度: {inp.confidence:.2f}）"
        
        elif strategy == ConflictResolution.LATEST:
            timestamps = {
                inp.task_id: inp.timestamp
                for inp in self._inputs
                if inp.task_id in conflict.source_ids
            }
            winner_id = max(timestamps, key=timestamps.get)
            
            for inp in self._inputs:
                if inp.task_id == winner_id:
                    return f"采用最新结果（时间: {inp.timestamp.strftime('%Y-%m-%d %H:%M')}）"
        
        elif strategy == ConflictResolution.PRIORITY:
            priorities = {
                inp.task_id: inp.metadata.get("priority", 0)
                for inp in self._inputs
                if inp.task_id in conflict.source_ids
            }
            winner_id = min(priorities, key=priorities.get)
            
            for inp in self._inputs:
                if inp.task_id == winner_id:
                    return f"采用高优先级结果（{inp.source_type}）"
        
        elif strategy == ConflictResolution.MANUAL:
            return "需要人工介入解决"
        
        return "采用默认合并策略"
    
    def _merge_all_inputs(self) -> Dict[str, Any]:
        """合并所有输入"""
        merged = {
            "sources": [],
            "summary": {},
            "details": {}
        }
        
        for inp in self._inputs:
            merged["sources"].append({
                "agent": inp.source_agent,
                "type": inp.source_type,
                "confidence": inp.confidence,
                "timestamp": inp.timestamp.isoformat()
            })
            
            # 安全处理 content，无论它是字典还是字符串
            if isinstance(inp.content, dict):
                try:
                    for key, value in inp.content.items():
                        if key not in merged["summary"]:
                            merged["summary"][key] = []
                        merged["summary"][key].append({
                            "value": value,
                            "source": inp.source_agent,
                            "confidence": inp.confidence
                        })
                    
                    merged["details"][inp.source_type] = inp.content
                except Exception as e:
                    # 如果字典处理失败，将整个 content 作为字符串处理
                    logger.warning(f"⚠️ [ResultSynthesizer] 处理字典内容失败: {e}")
                    content_str = json.dumps(inp.content, ensure_ascii=False) if inp.content else str(inp.content)
                    merged["details"][inp.source_type] = {"content": content_str}
            else:
                # 如果是字符串，直接作为 content 存储
                content_str = inp.content if isinstance(inp.content, str) else str(inp.content)
                merged["details"][inp.source_type] = {"content": content_str}
        
        return merged
    
    async def synthesize(
        self,
        user_query: Optional[str] = None,
        strategy: Optional[SynthesisStrategy] = None,
        custom_template: Optional[str] = None
    ) -> SynthesisResult:
        """
        执行合成（融合了审查和质量保障）
        
        Args:
            user_query: 用户原始查询
            strategy: 合成策略（覆盖默认）
            custom_template: 自定义模板
            
        Returns:
            SynthesisResult: 合成结果
        """
        start_time = datetime.now()
        
        if not self._inputs:
            return SynthesisResult(
                synthesis_id=str(uuid.uuid4()),
                task_id=self._current_task_id or "unknown",
                strategy=strategy or self.default_strategy,
                raw_inputs=[],
                conflicts=[],
                resolved_content={},
                final_response=self._format_default_answer("no_result"),
                confidence=0.0,
                quality_score=0.0,
                execution_time=0.0
            )
        
        strategy = strategy or self.default_strategy
        
        logger.info(f"🔄 [ResultSynthesizer] 开始合成，输入数量: {len(self._inputs)}")
        
        try:
            detected_conflicts = await self.detect_conflicts()
            self._conflicts = detected_conflicts
        except Exception as e:
            logger.warning(f"⚠️ [ResultSynthesizer] 冲突检测失败: {e}")
            detected_conflicts = []
            self._conflicts = []
        
        try:
            resolved_content = self._merge_all_inputs()
        except KeyError as e:
            logger.error(f"❌ [ResultSynthesizer] 合并内容时键缺失: {e}")
            # 返回默认响应而不是抛出异常
            return SynthesisResult(
                synthesis_id=str(uuid.uuid4()),
                task_id=self._current_task_id or "unknown",
                strategy=strategy,
                raw_inputs=self._inputs.copy(),
                conflicts=[],
                resolved_content={},
                final_response=self._format_default_answer("no_result"),
                confidence=0.0,
                quality_score=0.0,
                execution_time=0.0
            )
        
        final_response = await self._generate_response(
            resolved_content,
            strategy,
            user_query,
            custom_template
        )
        
        review_result = self.quick_review(final_response, user_query or "")
        
        quality_score = self._evaluate_quality(resolved_content, final_response, review_result)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        confidence = self._calculate_overall_confidence(quality_score, detected_conflicts)
        
        result = SynthesisResult(
            synthesis_id=str(uuid.uuid4()),
            task_id=self._current_task_id or "unknown",
            strategy=strategy,
            raw_inputs=self._inputs.copy(),
            conflicts=[c.__dict__ for c in detected_conflicts],
            resolved_content=resolved_content,
            final_response=final_response,
            confidence=confidence,
            quality_score=quality_score,
            execution_time=execution_time,
            metadata={"review_passed": review_result.is_approved}
        )
        
        logger.info(f"✅ [ResultSynthesizer] 合成完成，质量评分: {quality_score:.2f}, 审查通过: {review_result.is_approved}")
        
        self._inputs.clear()
        self._conflicts.clear()
        
        return result
    
    async def _generate_response(
        self,
        content: Dict[str, Any],
        strategy: SynthesisStrategy,
        user_query: Optional[str],
        custom_template: Optional[str]
    ) -> str:
        """生成最终响应"""
        
        if strategy == SynthesisStrategy.CONCATENATE:
            response = self._generate_concatenate_response(content)
        elif strategy == SynthesisStrategy.MERGE:
            response = self._generate_merge_response(content)
        elif strategy == SynthesisStrategy.HIERARCHICAL:
            response = self._generate_hierarchical_response(content)
        elif strategy == SynthesisStrategy.NARRATIVE:
            response = await self._generate_narrative_response(content, user_query)
        elif strategy == SynthesisStrategy.CUSTOM:
            response = self._generate_custom_response(content, custom_template)
        else:
            response = self._generate_concatenate_response(content)
        
        # 清理输出文本
        return self._clean_output(response)
    
    def _generate_concatenate_response(self, content: Dict[str, Any]) -> str:
        """生成简单拼接响应"""
        parts = []
        
        for source_type, details in content.get("details", {}).items():
            parts.append(f"【{source_type.upper()}】")
            
            if isinstance(details, dict):
                for key, value in details.items():
                    parts.append(f"  {key}: {value}")
            else:
                parts.append(f"  {details}")
            
            parts.append("")
        
        return "\n".join(parts).strip()
    
    def _generate_merge_response(self, content: Dict[str, Any]) -> str:
        """生成合并响应"""
        public_reports = self._extract_public_reports(content)
        if public_reports:
            return "\n\n".join(public_reports)

        merged_items = []
        hidden_keys = {
            "success",
            "has_tax_db_data",
            "tax_data",
            "tax_data_error",
            "entities",
            "metadata",
            "raw_data",
            "debug",
            "trace",
            "tool_output",
        }
        public_keys = {
            "summary",
            "analysis_report",
            "recommendations",
            "risks",
            "risk_points",
            "compliance_status",
            "risk_assessment",
            "confidence",
        }
        
        for key, values in content.get("summary", {}).items():
            if key in hidden_keys or (key not in public_keys and key.endswith("_data")):
                continue
            if len(values) == 1:
                formatted_value = self._format_public_value(values[0]["value"])
                if formatted_value:
                    merged_items.append(f"• {self._display_key(key)}: {formatted_value}")
            else:
                unique_values = list({json.dumps(v, sort_keys=True): v for v in values}.values())
                
                if len(unique_values) == 1:
                    formatted_value = self._format_public_value(unique_values[0]["value"])
                    if formatted_value:
                        merged_items.append(f"• {self._display_key(key)}: {formatted_value}")
                else:
                    display_key = self._display_key(key)
                    child_items = []
                    for v in unique_values:
                        formatted_value = self._format_public_value(v["value"])
                        if formatted_value:
                            child_items.append(f"  - {formatted_value}（来源: {v['source']}）")
                    if child_items:
                        merged_items.append(f"• {display_key}:")
                        merged_items.extend(child_items)

        if not merged_items:
            for source_type, details in content.get("details", {}).items():
                public_details = self._format_public_details(details)
                if public_details:
                    merged_items.append(f"### {self._display_key(source_type)}")
                    merged_items.extend(public_details)
        
        header = "📊 综合分析结果：\n"
        if merged_items:
            return header + "\n".join(merged_items)
        return "抱歉，暂未生成可展示的分析结论。请补充更具体的业务背景后重试。"

    def _extract_public_reports(self, content: Dict[str, Any]) -> List[str]:
        reports = []
        report_keys = ("analysis_report", "report", "final_report", "content")
        for details in content.get("details", {}).values():
            if isinstance(details, str) and details.strip() and not self._looks_internal_text(details):
                reports.append(details.strip())
                continue
            if not isinstance(details, dict):
                continue
            for key in report_keys:
                value = details.get(key)
                if isinstance(value, str) and value.strip() and not self._looks_internal_text(value):
                    reports.append(value.strip())
                    break
        return reports

    def _format_public_details(self, details: Any) -> List[str]:
        if isinstance(details, str):
            return [details.strip()] if details.strip() and not self._looks_internal_text(details) else []
        if not isinstance(details, dict):
            return []

        lines = []
        recommendations = details.get("recommendations")
        if isinstance(recommendations, list) and recommendations:
            lines.append("#### 建议")
            lines.extend(f"- {item}" for item in recommendations if item)

        risk_assessment = details.get("risk_assessment")
        if isinstance(risk_assessment, dict):
            risk_level = risk_assessment.get("risk_level")
            risk_factors = risk_assessment.get("risk_factors")
            if risk_level:
                lines.append(f"- 风险等级：{self._translate_value(risk_level)}")
            if isinstance(risk_factors, list) and risk_factors:
                lines.append("#### 风险提示")
                lines.extend(f"- {item}" for item in risk_factors if item)

        analysis = details.get("analysis")
        if isinstance(analysis, dict):
            compliance_status = analysis.get("compliance_status")
            if compliance_status:
                lines.append(f"- 合规状态：{self._translate_value(compliance_status)}")
            risk_points = analysis.get("risk_points")
            if isinstance(risk_points, list) and risk_points and "#### 风险提示" not in lines:
                lines.append("#### 风险提示")
                lines.extend(f"- {item}" for item in risk_points if item)

        confidence = details.get("confidence")
        if isinstance(confidence, (int, float)):
            lines.append(f"- 置信度：{confidence:.0%}")

        return lines

    def _format_public_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return ""
        if isinstance(value, list):
            return "；".join(str(item) for item in value if item)
        if isinstance(value, dict):
            return ""
        return self._translate_value(value)

    def _display_key(self, key: str) -> str:
        return {
            "tax": "税务分析",
            "taxspecialist": "税务分析",
            "tax_specialist": "税务分析",
            "recommendations": "建议",
            "risk_points": "风险提示",
            "risks": "风险提示",
            "compliance_status": "合规状态",
            "risk_assessment": "风险评估",
            "confidence": "置信度",
            "analysis_report": "分析报告",
        }.get(str(key).lower(), str(key).replace("_", " "))

    def _translate_value(self, value: Any) -> str:
        text = str(value)
        return {
            "high": "高",
            "medium": "中",
            "low": "低",
            "review_required": "需要复核",
            "compliant": "合规",
            "non_compliant": "不合规",
            "TaxType.OTHER": "其他税种",
        }.get(text, text)

    def _looks_internal_text(self, text: str) -> bool:
        stripped = text.strip()
        internal_markers = (
            "has_tax_db_data",
            "tax_data",
            "tax_data_error",
            "TaxType.",
            "<TaxType.",
            "'success':",
            '"success":',
        )
        return stripped.startswith("{") or any(marker in stripped for marker in internal_markers)
    
    def _generate_hierarchical_response(self, content: Dict[str, Any]) -> str:
        """生成层次化响应"""
        sections = []
        
        sources = content.get("sources", [])
        if sources:
            source_names = [s["agent"] for s in sources]
            sections.append("## 📋 数据来源")
            sections.append(", ".join(source_names))
            sections.append("")
        
        for source_type, details in content.get("details", {}).items():
            sections.append(f"### {source_type.upper()}")
            
            if isinstance(details, dict):
                for key, value in details.items():
                    sections.append(f"**{key}**: {value}")
            else:
                sections.append(str(details))
            
            sections.append("")
        
        return "\n".join(sections).strip()
    
    async def _generate_narrative_response(
        self,
        content: Dict[str, Any],
        user_query: Optional[str]
    ) -> str:
        """生成叙事化响应（使用 LLM）"""
        
        if not self.llm:
            logger.warning("⚠️ [ResultSynthesizer] LLM适配器未提供，回退到合并响应")
            return self._generate_merge_response(content)
        
        context_parts = []
        
        for source_type, details in content.get("details", {}).items():
            context_parts.append(f"## {source_type.upper()} 领域分析:")
            
            if isinstance(details, dict):
                for key, value in details.items():
                    context_parts.append(f"- {key}: {value}")
            else:
                context_parts.append(str(details))
            
            context_parts.append("")
        
        full_prompt = f"""{self.prompts.get_synthesis_prompt(user_query or '无特定问题', chr(10).join(context_parts))}

请生成一段自然、流畅的综合回复，整合以上各领域的分析结果。
"""
        
        try:
            if hasattr(self.llm, 'chat'):
                response = await self.llm.chat([
                    {"role": "user", "content": full_prompt}
                ], stream=False)
                
                content_text = response.content if hasattr(response, 'content') else str(response)
                return self._clean_output(content_text.strip())
            else:
                return self._generate_merge_response(content)
                
        except Exception as e:
            logger.error(f"❌ [ResultSynthesizer] 叙事生成失败: {e}")
            return self._generate_merge_response(content)
    
    def _generate_custom_response(
        self,
        content: Dict[str, Any],
        template: Optional[str]
    ) -> str:
        """生成自定义模板响应"""
        if not template:
            return self._generate_merge_response(content)
        
        try:
            return template.format(**content)
        except KeyError as e:
            logger.warning(f"⚠️ [ResultSynthesizer] 模板变量缺失: {e}")
            return template
    
    def _format_default_answer(self, answer_type: str) -> str:
        """格式化默认回答"""
        if answer_type == "no_result":
            return self.prompts.get_random_no_result_answer()
        return "抱歉，暂时无法提供相关信息。"
    
    def _evaluate_quality(
        self,
        content: Dict[str, Any],
        response: str,
        review_result: OutputReviewResult
    ) -> float:
        """评估质量（融合审查结果）"""
        score = 0.3
        
        if len(self._inputs) > 0:
            avg_confidence = sum(inp.confidence for inp in self._inputs) / len(self._inputs)
            score += avg_confidence * 0.2
        
        if len(response) > 100:
            score += 0.1
        
        if content.get("sources"):
            score += 0.1
        
        if not self._conflicts:
            score += 0.1
        
        score += (review_result.score / 10.0) * 0.2
        
        return min(score, 1.0)
    
    def _calculate_overall_confidence(
        self,
        quality_score: float,
        conflicts: List[ConflictInfo]
    ) -> float:
        """计算整体置信度"""
        if not self._inputs:
            return 0.0
        
        avg_confidence = sum(inp.confidence for inp in self._inputs) / len(self._inputs)
        
        conflict_penalty = len(conflicts) * 0.05
        
        return max(0.0, min(1.0, (avg_confidence * 0.7 + quality_score * 0.3 - conflict_penalty)))
    
    def quick_review(self, output: str, user_query: str) -> OutputReviewResult:
        """
        快速审查（无需 LLM 调用）
        
        使用正则表达式快速检测明显问题：
        - 敏感信息
        - 内部标记
        - 机械化开头
        - 内容长度异常
        """
        issues = []
        score = 10.0
        
        if not output or len(output.strip()) < 5:
            return OutputReviewResult(
                is_approved=False,
                score=0.0,
                issues=["输出内容为空或过短"],
                suggestion=self.prompts.get_random_no_result_answer(),
                needs_regenerate=True
            )
        
        if len(output.strip()) > 8000:
            issues.append("输出内容过长，可能需要精简")
            score -= 2
        
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                issues.append("检测到可能包含敏感信息")
                score -= 5
                break
        
        for pattern in self.INTERNAL_PATTERNS:
            if re.search(pattern, output):
                issues.append("检测到内部处理标记")
                score -= 3
                break
        
        for pattern in self.BAD_START_PATTERNS:
            if re.match(pattern, output):
                issues.append("开头语气机械化，不够友好")
                score -= 2
                break
        
        return OutputReviewResult(
            is_approved=score >= 6.0,
            score=score,
            issues=issues,
            suggestion="建议优化输出格式和语气" if issues else "",
            needs_regenerate=score < 5.0
        )
    
    async def synthesize_and_format(
        self,
        specialist_results: Dict[str, Any],
        user_query: str
    ) -> str:
        """
        整合专家结果并美化输出（主编级核心方法）
        
        严格遵循数据与视图分离原则：
        1. 接收生肉数据（Dict），绝不提前格式化
        2. 使用主编提示词 + structured_output 生成结构化报告
        3. 最后才渲染成美观的 Markdown
        
        Args:
            specialist_results: 专家结果字典 {专家名称: 生肉数据字典}
            user_query: 用户原始查询
            
        Returns:
            美观的 Markdown 报告
        """
        logger.info(f"🔄 [主编] 开始整合 {len(specialist_results)} 位专家结果")
        for key, value in specialist_results.items():
            logger.info(f"📊 [主编] 专家 '{key}' 数据 keys: {list(value.keys()) if isinstance(value, dict) else 'N/A'}")
            if isinstance(value, dict):
                for k, v in value.items():
                    logger.debug(f"   - {k}: {type(v).__name__} = {str(v)[:100] if v else 'None'}...")
        
        try:
            specialist_data_json = json.dumps(specialist_results, ensure_ascii=False, indent=2)
            logger.debug(f"📦 [主编] 生肉数据 JSON 大小: {len(specialist_data_json)} 字符")
            
            # 步骤2：获取主编提示词
            editor_prompt = ResultSynthesizerPrompts.get_editor_in_chief_prompt(
                user_query=user_query,
                specialist_results=specialist_data_json
            )
            
            # 步骤3：调用 LLM 生成结构化报告
            if self.llm:
                logger.info("🤖 [主编] 调用 LLM 生成结构化报告...")
                
                try:
                    # 尝试使用 structured_output（如果 LLM 适配器支持）
                    if hasattr(self.llm, 'structured_output'):
                        report = await self.llm.structured_output(
                            prompt=editor_prompt,
                            output_schema=FinalExecutiveReport
                        )
                        # 步骤4：渲染成 Markdown
                        return self.render_to_beautiful_markdown(report)
                    else:
                        # 回退：使用普通 chat 调用
                        response = await self.llm.chat([
                            {"role": "user", "content": editor_prompt}
                        ], stream=False)
                        
                        content = response.content if hasattr(response, 'content') else str(response)
                        
                        # 尝试解析为 JSON
                        try:
                            report_dict = json.loads(content)
                            report = FinalExecutiveReport(**report_dict)
                            return self.render_to_beautiful_markdown(report)
                        except:
                            # 如果不是 JSON，直接返回
                            return content
                except Exception as e:
                    logger.warning(f"⚠️ [主编] LLM 生成失败: {e}，使用降级方案")
                    return self._format_fallback_response(specialist_results)
            else:
                logger.warning("⚠️ [主编] LLM 未配置，使用降级方案")
                return self._format_fallback_response(specialist_results)
                
        except Exception as e:
            logger.error(f"❌ [主编] 整合失败: {e}", exc_info=True)
            return self._format_fallback_response(specialist_results, f"整合失败: {str(e)}")
    
    def render_to_beautiful_markdown(self, report: FinalExecutiveReport) -> str:
        """
        渲染 FinalExecutiveReport 为美观的 Markdown
        
        这是 Data 与 View 分离的关键：只在这里进行最终的格式化渲染！
        
        Args:
            report: 结构化报告对象
            
        Returns:
            美观的 Markdown 字符串
        """
        parts = []
        
        # 1. 高管摘要（必须醒目）
        parts.append("## 🎯 执行摘要\n")
        summary = report.executive_summary
        
        status_emoji = {
            "良好": "✅",
            "一般": "⚠️",
            "需要关注": "🚨"
        }.get(summary.overall_status, "📊")
        
        parts.append(f"{status_emoji} **整体状态**: {summary.overall_status}\n\n")
        
        if summary.summary_text:
            parts.append(f"{summary.summary_text}\n\n")
        
        # 2. 核心关注点
        if summary.key_concerns:
            parts.append("### 🔍 核心关注点\n")
            for concern in summary.key_concerns:
                parts.append(f"- {concern}\n")
            parts.append("\n")
        
        # 3. 立即行动项
        if summary.immediate_actions:
            parts.append("### ⚡ 立即行动项\n")
            for i, action in enumerate(summary.immediate_actions, 1):
                parts.append(f"{i}. {action}\n")
            parts.append("\n")
        
        # 4. 红牌警告（如果有）
        if report.critical_alerts:
            parts.append("## 🚨 红牌警告\n")
            for alert in report.critical_alerts:
                parts.append(f"> ⚠️ {alert}\n")
            parts.append("\n")
        
        # 5. 各专家洞察
        if report.specialist_insights:
            parts.append("## 📊 专家洞察\n")
            
            specialist_emoji = {
                "finance": "💰",
                "tax": "📋",
                "legal": "⚖️"
            }
            
            for insight in report.specialist_insights:
                emoji = specialist_emoji.get(insight.specialist_type, "📌")
                parts.append(f"### {emoji} {insight.specialist_type.upper()} 专家\n\n")
                
                # 关键发现
                if insight.key_findings:
                    for finding in insight.key_findings:
                        parts.append(f"- {finding}\n")
                    parts.append("\n")
                
                # 关键指标（表格形式）
                if insight.metrics:
                    parts.append("| 指标 | 数值 |\n")
                    parts.append("|------|------|\n")
                    for key, value in insight.metrics.items():
                        parts.append(f"| {key} | {value} |\n")
                    parts.append("\n")
                
                # 风险提示
                if insight.risks:
                    parts.append("**⚠️ 风险提示:**\n")
                    for risk in insight.risks:
                        parts.append(f"- {risk}\n")
                    parts.append("\n")
                
                # 建议
                if insight.recommendations:
                    parts.append("**💡 建议:**\n")
                    for i, rec in enumerate(insight.recommendations, 1):
                        parts.append(f"{i}. {rec}\n")
                    parts.append("\n")
        
        # 6. 关键指标汇总
        if report.key_metrics:
            parts.append("## 📈 关键指标汇总\n")
            parts.append("| 指标 | 数值 |\n")
            parts.append("|------|------|\n")
            for key, value in report.key_metrics.items():
                if isinstance(value, (int, float)):
                    if abs(value) >= 100000000:
                        display_value = f"{value/100000000:.2f}亿"
                    elif abs(value) >= 10000:
                        display_value = f"{value/10000:.2f}万"
                    else:
                        display_value = f"{value:.2f}"
                else:
                    display_value = str(value)
                parts.append(f"| {key} | {display_value} |\n")
            parts.append("\n")
        
        # 7. 后续步骤
        if report.next_steps:
            parts.append("## 📋 后续步骤\n")
            for i, step in enumerate(report.next_steps, 1):
                parts.append(f"{i}. {step}\n")
            parts.append("\n")
        
        # 8. 数据来源
        if report.data_sources:
            parts.append("---\n")
            parts.append("*📚 数据来源: " + ", ".join(report.data_sources) + "*\n")
        
        # 9. 置信度说明
        confidence_percent = report.confidence_level * 100
        parts.append(f"\n---\n")
        parts.append(f"*🤖 分析置信度: {confidence_percent:.0f}% | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        return "".join(parts)
    
    def _format_fallback_response(
        self,
        specialist_results: Dict[str, Any],
        error_detail: str = None
    ) -> str:
        """格式化备用响应（当合成失败时使用）"""
        response_parts = []
        
        response_parts.append("## 📊 综合分析报告\n\n")
        
        if error_detail:
            response_parts.append(f"**提示**: {error_detail}\n\n---\n\n")
        
        for specialist_name, result in specialist_results.items():
            response_parts.append(f"### {specialist_name}\n\n")
            
            if isinstance(result, dict):
                # 尝试提取格式化结果
                content = result.get("formatted_result") or result.get("raw_result") or str(result)
                response_parts.append(f"{content[:3000]}\n\n")  # 限制长度
            else:
                content = str(result) if result else "(无内容)"
                response_parts.append(f"{content[:3000]}\n\n")
            
            response_parts.append("---\n\n")
        
        return "".join(response_parts).strip()
    
    async def synthesize_and_format_stream(
        self,
        specialist_results: Dict[str, Any],
        user_query: str,
        buffer_size: int = 10
    ) -> AsyncGenerator[str, None]:
        """
        流式整合专家结果并美化输出
        
        将多位专家的分析结果通过 LLM 整合成一份专业、美观的 Markdown 报告，
        并以流式方式逐步返回文本内容。
        
        Args:
            specialist_results: 专家结果字典 {专家名称: 结果内容}
            user_query: 用户原始查询
            buffer_size: 缓冲区大小（字符数）
            
        Yields:
            文本块
        """
        logger.info(f"🔄 [ResultSynthesizer] 开始流式整合 {len(specialist_results)} 位专家结果")
        
        # 先获取完整的响应
        full_response = await self.synthesize_and_format(specialist_results, user_query)
        
        # 流式返回
        for i in range(0, len(full_response), buffer_size):
            yield full_response[i:i + buffer_size]
            await asyncio.sleep(0.01)  # 小延迟，模拟流式效果
    
    def _clean_output(self, text: str) -> str:
        """
        清理输出文本，去除冗余字符和特殊符号
        
        Args:
            text: 原始输出文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        
        cleaned = text
        
        # 移除多余的连续空行（保留最多2个）
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # 移除行尾多余空格
        cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
        
        # 移除 Markdown 代码块标记（如果有）
        cleaned = re.sub(r'^```markdown\n', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^```\n', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\n```$', '', cleaned)
        
        # 移除行首多余的井号空格（保持标准 Markdown 格式）
        cleaned = re.sub(r'^#+\s*#+\s*', lambda m: m.group(0).replace('#', '', 1), cleaned, flags=re.MULTILINE)
        
        # 移除连续的短横线和空格（分隔线误判）
        cleaned = re.sub(r'^-\s*-{3,}$', '', cleaned, flags=re.MULTILINE)
        
        # 移除 Unicode 控制字符（除换行和Tab外）
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
        
        # 移除特殊空白字符
        cleaned = re.sub(r'[\u200b-\u200d\uFEFF]', '', cleaned)
        
        return cleaned.strip()
