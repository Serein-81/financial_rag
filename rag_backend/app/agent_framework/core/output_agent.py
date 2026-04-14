"""
输出智能体 (Output Agent) - 融合版

融合了 ResultSynthesizer 的功能，统一负责：
1. 多智能体结果合成
2. 冲突检测与解决
3. 置信度评估
4. 输出质量审查
5. 安全格式美化

提示词管理：
- 所有提示词存储在 app/prompts/output_agent/ 目录下
- 使用 PromptLoader 从文件加载提示词
"""

import re
import json
import random
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.utils.output_formatter import OutputFormatter

logger = logging.getLogger(__name__)

try:
    from app.prompts.output_agent import (
        get_system_prompt,
        get_quick_review_prompt,
        get_deep_review_prompt,
        get_regeneration_hint_prompt,
    )
    PROMPTS_AVAILABLE = True
except ImportError:
    PROMPTS_AVAILABLE = False


class SynthesisStrategy(str, Enum):
    """合成策略"""
    CONCATENATE = "concatenate"
    MERGE = "merge"
    HIERARCHICAL = "hierarchical"
    NARRATIVE = "narrative"
    CUSTOM = "custom"


class ConflictResolution(str, Enum):
    """冲突解决策略"""
    LATEST = "latest"
    HIGHEST_CONFIDENCE = "highest_confidence"
    VOTE = "vote"
    PRIORITY = "priority"
    MANUAL = "manual"


@dataclass
class SynthesisInput:
    """合成输入"""
    task_id: str
    source_agent: str
    source_type: str
    content: Any
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
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


class OutputAgentPrompts:
    """输出智能体提示词（从 app/prompts/agents/output_agent/ 目录加载）"""

    _prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "agents" / "output_agent"

    @classmethod
    def _load_prompt_file(cls, filename: str) -> str:
        """从文件加载提示词"""
        file_path = cls._prompt_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def get_system_prompt() -> str:
        """获取系统提示词"""
        try:
            from app.prompts.prompt_registry import get_prompt_registry
            registry = get_prompt_registry()
            prompt = registry.load_system_prompt("output_agent")
            if prompt:
                return prompt
        except Exception:
            pass
        return "你是一位专业的企业级输出整合师..."

    @staticmethod
    def get_synthesis_prompt(user_query: str, specialist_results: str) -> str:
        """获取整合提示词"""
        try:
            from app.agent_framework.core.output_agent import OutputAgentPrompts
            template = OutputAgentPrompts._load_prompt_file("synthesis.md")
            if template:
                return template.format(user_query=user_query, specialist_results=specialist_results)
        except Exception:
            pass
        return f"请整合以下专家结果回答用户问题：{user_query}\n\n{specialist_results}"

    @staticmethod
    def get_quick_review_prompt(user_query: str, output: str) -> str:
        """获取快速审查提示词"""
        try:
            from app.agent_framework.core.output_agent import OutputAgentPrompts
            template = OutputAgentPrompts._load_prompt_file("quick_review.md")
            if template:
                return template.format(user_query=user_query, output=output)
        except Exception:
            pass
        return f"请审查以下输出：\n{output}"

    @staticmethod
    def get_deep_review_prompt(user_query: str, output: str) -> str:
        """获取深度审查提示词"""
        try:
            from app.agent_framework.core.output_agent import OutputAgentPrompts
            template = OutputAgentPrompts._load_prompt_file("deep_review.md")
            if template:
                return template.format(user_query=user_query, output=output)
        except Exception:
            pass
        return f"请审查以下输出：\n{output}"

    @staticmethod
    def get_regeneration_hint_prompt(user_query: str, original_output: str, feedback: str) -> str:
        """获取改进提示词"""
        try:
            from app.agent_framework.core.output_agent import OutputAgentPrompts
            template = OutputAgentPrompts._load_prompt_file("regeneration.md")
            if template:
                return template.format(user_query=user_query, original_output=original_output, feedback=feedback)
        except Exception:
            pass
        return f"请根据反馈改进：{feedback}"

    @staticmethod
    def get_final_output_prompt(user_query: str, tool_result: str) -> str:
        """获取最终输出提示词"""
        try:
            from app.agent_framework.core.output_agent import OutputAgentPrompts
            template = OutputAgentPrompts._load_prompt_file("final_output.md")
            if template:
                return template.format(user_query=user_query, tool_result=tool_result)
        except Exception:
            pass
        return f"请回答用户问题：{user_query}"

    NO_RESULT_ANSWERS = [
        "抱歉，我暂时没有找到相关的信息。能否请您提供更多细节或换个方式描述您的问题？",
        "对不起，知识库中暂未收录相关内容。建议您换个关键词试试，或者联系相关人员获取帮助。",
        "很抱歉，我未能找到匹配的信息。请您尝试调整问题描述，我会尽力为您提供帮助。",
    ]

    @classmethod
    def get_random_no_result_answer(cls) -> str:
        return random.choice(cls.NO_RESULT_ANSWERS)


class OutputAgent:
    """统一输出智能体（融合版）"""
    
    def __init__(
        self,
        llm_adapter=None,
        default_strategy: SynthesisStrategy = SynthesisStrategy.MERGE,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE,
        max_inputs: int = 10
    ):
        self.llm = llm_adapter
        self.prompts = OutputAgentPrompts()
        self.default_strategy = default_strategy
        self.conflict_resolution = conflict_resolution
        self.max_inputs = max_inputs
        
        self._inputs: List[SynthesisInput] = []
        self._conflicts: List[ConflictInfo] = []
        self._current_task_id: Optional[str] = None
        
        try:
            from app.utils.output_formatter import output_formatter
            self.output_formatter = output_formatter
        except ImportError:
            self.output_formatter = None
        
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
        
        self.BAD_START_PATTERNS = [
            r'^抱歉.*?[，,]\s*(我|系统|这个)',
            r'^对不起.*?[，,]\s*(我|系统)',
            r'^根据.*?(显示|查询|检索)',
            r'^\[检索结果为空\]$',
            r'^很抱歉.*?[，,]',
            r'^对不起.*?[，,]',
        ]

    def _get_system_prompt(self) -> str:
        return self.prompts.get_system_prompt()

    def _get_synthesis_prompt(self, user_query: str, specialist_results: str) -> str:
        return self.prompts.get_synthesis_prompt(user_query, specialist_results)

    def _get_deep_review_prompt(self, user_query: str, output: str) -> str:
        return self.prompts.get_deep_review_prompt(user_query, output)

    def _get_regeneration_hint_prompt(
        self,
        user_query: str,
        original_output: str,
        feedback: str
    ) -> str:
        return self.prompts.get_regeneration_hint_prompt(
            user_query, original_output, feedback
        )

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
            logger.warning(f"⚠️ [OutputAgent] 输入数量已达上限 {self.max_inputs}")
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
        
        logger.debug(f"📥 [OutputAgent] 添加输入: {source_agent} ({source_type})")
        return True

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
            logger.warning(f"⚠️ [OutputAgent] 检测到 {len(conflicts)} 个冲突")
        
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
            
            if isinstance(inp.content, dict):
                for key, value in inp.content.items():
                    if key not in merged["summary"]:
                        merged["summary"][key] = []
                    merged["summary"][key].append({
                        "value": value,
                        "source": inp.source_agent,
                        "confidence": inp.confidence
                    })
                
                merged["details"][inp.source_type] = inp.content
        
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
                final_response=self.format_default_answer("no_result"),
                confidence=0.0,
                quality_score=0.0,
                execution_time=0.0
            )
        
        strategy = strategy or self.default_strategy
        
        logger.info(f"🔄 [OutputAgent] 开始合成，输入数量: {len(self._inputs)}")
        
        detected_conflicts = await self.detect_conflicts()
        self._conflicts = detected_conflicts
        
        resolved_content = self._merge_all_inputs()
        
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
        
        logger.info(f"✅ [OutputAgent] 合成完成，质量评分: {quality_score:.2f}, 审查通过: {review_result.is_approved}")
        
        self._inputs.clear()
        self._conflicts.clear()
        
        return result

    async def _generate_response(
        self,
        resolved_content: Dict[str, Any],
        strategy: SynthesisStrategy,
        user_query: Optional[str],
        custom_template: Optional[str]
    ) -> str:
        """生成最终响应"""
        
        if strategy == SynthesisStrategy.CONCATENATE:
            response = self._generate_concatenate_response(resolved_content)
        elif strategy == SynthesisStrategy.MERGE:
            response = self._generate_merge_response(resolved_content)
        elif strategy == SynthesisStrategy.HIERARCHICAL:
            response = self._generate_hierarchical_response(resolved_content)
        elif strategy == SynthesisStrategy.NARRATIVE:
            response = await self._generate_narrative_response(resolved_content, user_query)
        elif strategy == SynthesisStrategy.CUSTOM:
            response = self._generate_custom_response(resolved_content, custom_template)
        else:
            response = self._generate_concatenate_response(resolved_content)
        
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
        merged_items = []
        
        for key, values in content.get("summary", {}).items():
            if len(values) == 1:
                merged_items.append(f"• {key}: {values[0]['value']}")
            else:
                unique_values = list({json.dumps(v, sort_keys=True): v for v in values}.values())
                
                if len(unique_values) == 1:
                    merged_items.append(f"• {key}: {unique_values[0]['value']}")
                else:
                    merged_items.append(f"• {key}:")
                    for v in unique_values:
                        merged_items.append(f"  - {v['value']}（来源: {v['source']}）")
        
        header = "📊 综合分析结果：\n"
        return header + "\n".join(merged_items)

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
        
        context_parts = []
        
        for source_type, details in content.get("details", {}).items():
            context_parts.append(f"## {source_type.upper()} 领域分析:")
            
            if isinstance(details, dict):
                for key, value in details.items():
                    context_parts.append(f"- {key}: {value}")
            else:
                context_parts.append(str(details))
            
            context_parts.append("")
        
        full_prompt = f"""{self.prompts.SYNTHESIS_NARRATIVE_PROMPT}

用户问题: {user_query or '无特定问题'}

各领域分析结果:
{chr(10).join(context_parts)}

请生成一段自然、流畅的综合回复，整合以上各领域的分析结果。
"""
        
        try:
            if hasattr(self.llm, 'chat'):
                response = await self.llm.chat([
                    {"role": "user", "content": full_prompt}
                ], stream=False)
                
                content = response.content if hasattr(response, 'content') else str(response)
                return self._clean_output(content.strip())
            else:
                return self._generate_merge_response(content)
                
        except Exception as e:
            logger.error(f"❌ [OutputAgent] 叙事生成失败: {e}")
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
            logger.warning(f"⚠️ [OutputAgent] 模板变量缺失: {e}")
            return template

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
                suggestion=OutputAgentPrompts.get_random_no_result_answer(),
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
        
        if "[检索结果为空]" in output and len(output.strip()) < 50:
            issues.append("仅包含空结果提示")
            score -= 4
        
        is_approved = score >= 7.0 and len(issues) == 0
        
        return OutputReviewResult(
            is_approved=is_approved,
            score=max(0, score),
            issues=issues,
            needs_regenerate=not is_approved
        )

    async def deep_review(self, output: str, user_query: str) -> OutputReviewResult:
        """
        深度审查（使用 LLM）

        使用 LLM 进行全面的质量评估：
        - 相关性判断
        - 完整性检查
        - 准确性验证
        - 可读性评估
        - 美观度判断
        - 语气友好度
        """
        if not self.llm:
            return self.quick_review(output, user_query)

        try:
            prompt = self._get_deep_review_prompt(user_query, output)
            system_prompt = self._get_system_prompt()

            response = await self.llm.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ], stream=False)

            content = response.content if hasattr(response, 'content') else str(response)

            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result_dict = json.loads(json_match.group())
                return OutputReviewResult(
                    is_approved=result_dict.get("is_approved", False),
                    score=result_dict.get("score", 5.0),
                    issues=result_dict.get("issues", []),
                    suggestion=result_dict.get("suggestion", ""),
                    needs_regenerate=not result_dict.get("is_approved", False)
                )
        except Exception as e:
            logger.warning(f"⚠️ [OutputAgent] LLM深度审查失败: {e}, 回退到规则审查")

        return self.quick_review(output, user_query)

    async def synthesize_and_format(
        self,
        specialist_results: Dict[str, Any],
        user_query: str
    ) -> str:
        """
        整合专家结果并美化输出（核心方法）

        将多位专家的分析结果通过 LLM 整合成一份专业、美观的 Markdown 报告。

        Args:
            specialist_results: 专家结果字典，格式为 {"专家名称": 结果内容, ...}
            user_query: 用户原始问题

        Returns:
            整合美化后的 Markdown 报告
        """
        if not self.llm:
            return self._fallback_format(specialist_results, user_query)

        try:
            specialist_results_text = self._format_specialist_results_for_prompt(specialist_results)
            synthesis_prompt = self._get_synthesis_prompt(user_query, specialist_results_text)
            system_prompt = self._get_system_prompt()

            response = await self.llm.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": synthesis_prompt}
            ], stream=False, max_tokens=4000)

            content = response.content if hasattr(response, 'content') else str(response)
            
            # 清理输出文本
            cleaned_content = self._clean_output(content)
            logger.info(f"📤 [输出智能体] LLM整合完成，原始长度: {len(content)} 字符，清理后: {len(cleaned_content)} 字符")
            return cleaned_content

        except Exception as e:
            logger.warning(f"⚠️ [输出智能体] LLM整合失败: {e}，使用备用格式")
            return self._fallback_format(specialist_results, user_query)

    def _format_specialist_results_for_prompt(self, specialist_results: Dict[str, Any]) -> str:
        """将专家结果格式化为提示词文本"""
        parts = []
        for specialist_name, result in specialist_results.items():
            parts.append(f"\n【{specialist_name}的分析结果】\n{self._extract_content(result)}\n")
        return "\n".join(parts)

    def _extract_content(self, result: Any) -> str:
        """提取结果中的文本内容"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            content = result.get("content", result.get("response", str(result)))
            return content if isinstance(content, str) else str(content)
        elif isinstance(result, list):
            return "\n".join(str(item) for item in result)
        return str(result)

    def _fallback_format(self, specialist_results: Dict[str, Any], user_query: str) -> str:
        """备用格式化（当 LLM 不可用时）"""
        parts = [f"## 综合分析\n\n基于您的问题「{user_query}」，以下是各专家的分析结果：\n"]

        specialist_display_names = {
            "finance": "💰 财务专家",
            "tax": "📋 税务专家",
            "legal": "⚖️ 法务专家",
            "financial": "💰 财务专家",
        }

        for specialist, result in specialist_results.items():
            display_name = specialist_display_names.get(specialist.lower(), specialist)
            content = self._extract_content(result)
            parts.append(f"\n### {display_name}\n\n{content}\n")

        return "\n".join(parts)

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
        
        # 移除行首或段落开头的多余空格（但保留表格缩进）
        lines = cleaned.split('\n')
        processed_lines = []
        for line in lines:
            # 只移除非表格行的多余空格
            if line.strip().startswith('|'):
                # 保留表格行原样
                processed_lines.append(line)
            else:
                # 非表格行移除首尾空格
                processed_lines.append(line.strip())
        cleaned = '\n'.join(processed_lines)
        
        # 移除连续超过3个的emoji
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251]+",
            flags=re.UNICODE
        )
        
        # 移除连续超过3个的emoji（但在表格外）
        lines = cleaned.split('\n')
        processed_lines = []
        for line in lines:
            if line.strip().startswith('|'):
                # 表格行：保留emoji但移除控制字符
                line = emoji_pattern.sub('', line)
            else:
                # 非表格行：限制每行最多3个emoji
                emojis = emoji_pattern.findall(line)
                if len(emojis) > 3:
                    line = emoji_pattern.sub(lambda m: '' if m.group() in emojis[3:] else m.group(), line)
            processed_lines.append(line)
        cleaned = '\n'.join(processed_lines)
        
        cleaned = cleaned.strip()
        
        return cleaned

    async def optimize(
        self,
        output: str,
        user_query: str,
        enable_deep_review: bool = False
    ) -> str:
        """
        优化输出（合成 + 审查）
        
        Args:
            output: 原始输出
            user_query: 用户问题
            enable_deep_review: 是否启用深度审查
            
        Returns:
            优化后的输出
        """
        if enable_deep_review:
            review_result = await self.deep_review(output, user_query)
        else:
            review_result = self.quick_review(output, user_query)
        
        if review_result.is_approved:
            return output
        
        if review_result.score < 3.0:
            return self.format_default_answer("default")
        
        regenerated = await self.regenerate_with_hint(
            output,
            user_query,
            review_result.suggestion
        )
        
        final_review = self.quick_review(regenerated, user_query)
        
        if final_review.is_approved:
            return regenerated
        
        return regenerated

    async def regenerate_with_hint(
        self, 
        original_output: str, 
        user_query: str, 
        feedback: str
    ) -> str:
        """
        根据反馈生成改进的回答
        
        Args:
            original_output: 原始回答
            user_query: 用户问题
            feedback: 审查反馈
            
        Returns:
            改进后的回答
        """
        if not self.llm:
            return original_output
        
        try:
            prompt = self._get_regeneration_hint_prompt(
                user_query, original_output, feedback
            )
            system_prompt = self._get_system_prompt()
            
            response = await self.llm.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ], stream=False)
            
            content = response.content if hasattr(response, 'content') else str(response)
            return content.strip()
        except Exception as e:
            logger.warning(f"⚠️ [OutputAgent] 改进生成失败: {e}")
            return original_output

    def should_regenerate(self, result: OutputReviewResult, attempt: int) -> Tuple[bool, str]:
        """
        判断是否应该重新生成
        
        Args:
            result: 审查结果
            attempt: 当前尝试次数
            
        Returns:
            (是否重试, 原因)
        """
        if attempt >= 2:
            return False, "已达到最大重试次数限制"
        
        if not result.needs_regenerate:
            return False, "审查通过"
        
        if result.score < 3.0:
            return False, f"质量问题严重（评分 {result.score}），使用默认友好回复"
        
        if result.issues and "敏感信息" in result.issues[0]:
            return False, "存在敏感信息风险，使用默认回复"
        
        return True, result.suggestion

    def format_for_display(self, content: Any, task_type: str = "default") -> str:
        """
        格式化输出用于前端展示
        
        Args:
            content: 要格式化的内容（可以是字符串、字典、列表等）
            task_type: 任务类型（risk_analysis, general, report等）
            
        Returns:
            格式化后的字符串
        """
        if isinstance(content, dict):
            return self._format_dict_content(content, task_type)
        elif isinstance(content, list):
            return self._format_list_content(content, task_type)
        elif isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, (dict, list)):
                    return self.format_for_display(parsed, task_type)
            except json.JSONDecodeError:
                return content
        
        return str(content)
    
    def _format_dict_content(self, content: Dict[str, Any], task_type: str) -> str:
        """格式化字典内容"""
        if task_type == "risk_analysis":
            return self._format_risk_analysis(content)
        if task_type == "tax_analysis":
            return self._format_tax_analysis(content)
        
        formatted_parts = []
        
        specialist_map = {
            "finance": "💰 财务专家",
            "tax": "📋 税务专家",
            "legal": "⚖️ 法务专家",
            "financial": "💰 财务专家",
            "FINANCE": "💰 财务专家",
            "TAX": "📋 税务专家",
            "LEGAL": "⚖️ 法务专家"
        }
        
        for key, value in content.items():
            if isinstance(value, dict):
                specialist_name = specialist_map.get(key, key)
                formatted_parts.append(f"\n## {specialist_name}\n")
                formatted_parts.append(self._format_nested_dict(value))
            elif isinstance(value, list):
                formatted_parts.append(f"### {key}:\n")
                for item in value[:10]:
                    if isinstance(item, dict):
                        formatted_parts.append(f"- {json.dumps(item, ensure_ascii=False)}")
                    else:
                        formatted_parts.append(f"- {item}")
                formatted_parts.append("")
            else:
                formatted_parts.append(f"- **{key}**: {value}")
        
        return "\n".join(formatted_parts) if formatted_parts else str(content)
    
    def _format_nested_dict(self, data: Dict[str, Any], indent: int = 0) -> str:
        """格式化嵌套字典"""
        lines = []
        prefix = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}- **{key}**:")
                lines.append(self._format_nested_dict(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}- **{key}**:")
                for item in value[:5]:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  - {json.dumps(item, ensure_ascii=False)}")
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                display_value = value
                if isinstance(value, float):
                    if 0 < abs(value) < 1:
                        display_value = f"{value:.2%}" if key.endswith('ratio') or key.endswith('rate') else f"{value:.4f}"
                    else:
                        display_value = f"{value:.2f}"
                
                lines.append(f"{prefix}- **{key}**: {display_value}")
        
        return "\n".join(lines)
    
    def _format_tax_analysis(self, content: Dict[str, Any]) -> str:
        """格式化税务分析内容"""
        sections = []
        
        tax_type_display_map = {
            "vat": "增值税",
            "income_tax": "企业所得税",
            "personal_income_tax": "个人所得税",
            "consumption_tax": "消费税",
            "business_tax": "营业税",
            "property_tax": "房产税",
            "land_use_tax": "城镇土地使用税",
            "stamp_tax": "印花税",
            "environment_tax": "环境保护税",
            "other": "其他税务",
        }
        
        status_emoji_map = {
            "compliant": "✅",
            "review_required": "⚠️",
            "non_compliant": "❌",
            "unknown": "❓"
        }
        status_text_map = {
            "compliant": "合规",
            "review_required": "需审核",
            "non_compliant": "不合规",
            "unknown": "待确认"
        }
        
        tax_type = content.get("tax_type", "other")
        if hasattr(tax_type, 'value'):
            tax_type_display = tax_type_display_map.get(tax_type.value, "其他税务")
        elif isinstance(tax_type, str):
            tax_type_display = tax_type_display_map.get(tax_type, "其他税务")
        else:
            tax_type_display = "其他税务"
        
        if content.get("needs_more_info"):
            sections.append("### ⚠️ 信息不足\n")
            sections.append(f"{content.get('suggestion', '请提供更多税务信息')}\n")
            sections.append(f"**置信度**: {content.get('confidence', 0.0) * 100:.0f}%\n")
            return "\n".join(sections)
        
        sections.append("### 🏢 税务信息\n")
        sections.append("| 项目 | 内容 |")
        sections.append("|------|------|")
        sections.append(f"| 📑 税种类型 | {tax_type_display} |")
        
        tax_rate = content.get("tax_rate") or content.get("analysis", {}).get("tax_rate")
        tax_amount = content.get("tax_amount") or content.get("analysis", {}).get("tax_amount")
        tax_period = content.get("tax_period") or content.get("analysis", {}).get("tax_period")
        
        if tax_rate:
            sections.append(f"| 💹 适用税率 | {tax_rate}% |")
        if tax_amount:
            sections.append(f"| 💰 税务金额 | {tax_amount} |")
        if tax_period:
            sections.append(f"| 📅 税务期间 | {tax_period} |")
        
        risk_points = content.get("risk_points") or content.get("analysis", {}).get("risk_points", [])
        compliance_status = content.get("compliance_status") or content.get("analysis", {}).get("compliance_status", "unknown")
        
        risk_emoji = "🔴" if len(risk_points) > 2 else ("🟡" if len(risk_points) > 0 else "🟢")
        status_emoji = status_emoji_map.get(compliance_status, "⚠️")
        status_text = status_text_map.get(compliance_status, "待确认")
        
        sections.append(f"\n### 📊 合规性评估\n")
        sections.append("| 评估维度 | 结果 |")
        sections.append("|---------|------|")
        sections.append(f"| {risk_emoji} 风险等级 | {'高风险' if len(risk_points) > 2 else ('中风险' if len(risk_points) > 0 else '低风险')} |")
        sections.append(f"| {status_emoji} 合规状态 | {status_text} |")
        
        confidence = content.get('confidence', 0.0) or content.get('analysis', {}).get('confidence', 0.0)
        sections.append(f"| 📈 置信度 | {confidence * 100:.0f}% |")
        
        deductions = content.get("deductions") or content.get("analysis", {}).get("deductions", [])
        if deductions:
            sections.append(f"\n### 💵 可扣除项目\n")
            for item in deductions[:5]:
                sections.append(f"- {item}")
        
        exemptions = content.get("exemptions") or content.get("analysis", {}).get("exemptions", [])
        if exemptions:
            sections.append(f"\n### 🆓 免税项目\n")
            for item in exemptions[:5]:
                sections.append(f"- {item}")
        
        if risk_points:
            sections.append(f"\n### ⚠️ 风险提示\n")
            for point in risk_points:
                sections.append(f"- {point}")
        
        recommendations = content.get("recommendations", [])
        if recommendations:
            sections.append(f"\n### 💡 专业建议\n")
            for rec in recommendations[:3]:
                sections.append(f"- {rec}")
        
        return "\n".join(sections)
    
    def _format_risk_analysis(self, content: Dict[str, Any]) -> str:
        """格式化风险分析内容"""
        sections = []
        
        specialist_name_map = {
            "finance": "💰 财务专家分析",
            "tax": "📋 税务专家分析",
            "legal": "⚖️ 法务专家分析"
        }
        
        for specialist_key, specialist_data in content.items():
            specialist_name = specialist_name_map.get(specialist_key, f"🤖 {specialist_key}")
            
            sections.append(f"\n## {specialist_name}\n")
            
            if not isinstance(specialist_data, dict):
                sections.append(str(specialist_data))
                continue
            
            if specialist_key in ["finance", "financial", "FINANCE"]:
                if specialist_data.get("financial_indicators"):
                    sections.append("### 📊 财务指标\n")
                    for key, value in specialist_data.get("financial_indicators", {}).items():
                        display_key = {
                            "current_ratio": "流动比率",
                            "quick_ratio": "速动比率",
                            "debt_to_equity": "资产负债率",
                            "gross_margin": "毛利率",
                            "net_margin": "净利率",
                            "roe": "净资产收益率(ROE)",
                            "roa": "资产收益率(ROA)"
                        }.get(key, key)
                        if isinstance(value, float) and 0 < abs(value) < 1:
                            sections.append(f"- **{display_key}**: {value:.2%}")
                        else:
                            sections.append(f"- **{display_key}**: {value}")
                    sections.append("")
                
                if specialist_data.get("key_metrics"):
                    sections.append("### 📈 关键指标\n")
                    for metric in specialist_data.get("key_metrics", [])[:5]:
                        sections.append(f"- {metric}")
                    sections.append("")
                
                if specialist_data.get("risk_factors"):
                    sections.append("### ⚠️ 风险因素\n")
                    for risk in specialist_data.get("risk_factors", [])[:5]:
                        sections.append(f"- {risk}")
                    sections.append("")
                
                if specialist_data.get("recommendations"):
                    sections.append("### 💡 建议\n")
                    for rec in specialist_data.get("recommendations", [])[:5]:
                        sections.append(f"- {rec}")
                    sections.append("")
            
            elif specialist_key in ["tax", "TAX"]:
                if specialist_data.get("risk_points"):
                    sections.append("### ⚠️ 税务风险\n")
                    for risk in specialist_data.get("risk_points", [])[:5]:
                        sections.append(f"- {risk}")
                    sections.append("")
                
                if specialist_data.get("recommendations"):
                    sections.append("### 💡 建议\n")
                    for rec in specialist_data.get("recommendations", [])[:5]:
                        sections.append(f"- {rec}")
                    sections.append("")
            
            elif specialist_key in ["legal", "LEGAL"]:
                if specialist_data.get("risk_points"):
                    sections.append("### ⚠️ 法律风险\n")
                    for risk in specialist_data.get("risk_points", [])[:5]:
                        sections.append(f"- {risk}")
                    sections.append("")
                
                if specialist_data.get("suggestions"):
                    sections.append("### 💡 建议\n")
                    for sug in specialist_data.get("suggestions", [])[:5]:
                        sections.append(f"- {sug}")
                    sections.append("")
            
            confidence = specialist_data.get("confidence", specialist_data.get("analysis", {}).get("confidence", 0.8))
            sections.append(f"**置信度**: {confidence * 100:.0f}%\n")
        
        return "\n".join(sections) if sections else str(content)
    
    def _format_list_content(self, content: List[Any], task_type: str) -> str:
        """格式化列表内容"""
        formatted_parts = []
        
        for i, item in enumerate(content[:10], 1):
            if isinstance(item, dict):
                formatted_parts.append(f"{i}. {json.dumps(item, ensure_ascii=False)}")
            else:
                formatted_parts.append(f"- {item}")
        
        return "\n".join(formatted_parts)
    
    def format_default_answer(self, answer_type: str = "default") -> str:
        """
        格式化默认回答
        
        Args:
            answer_type: 
                - "default": 普通默认回答
                - "no_result": 无结果回答
                - "error": 错误回答
                - "timeout": 超时回答
                
        Returns:
            友好的默认回答
        """
        if answer_type == "no_result":
            return OutputAgentPrompts.get_random_no_result_answer()
        elif answer_type == "error":
            return "抱歉，处理您的请求时遇到了一些问题，请稍后重试。"
        elif answer_type == "timeout":
            return "抱歉，请求处理时间过长，建议您简化问题或稍后重试。"
        else:
            return OutputAgentPrompts.DEFAULT_FRIENDLY_ANSWER


output_agent = OutputAgent()
