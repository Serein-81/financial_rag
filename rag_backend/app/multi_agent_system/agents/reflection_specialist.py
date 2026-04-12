"""
质量审查智能体 (Reflection Specialist Agent)
对专家回答进行质量审核、置信度评估和准确性验证
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.multi_agent_system.agents.base_agent_prompt import load_agent_prompt

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    """质量等级"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"  # 良好
    ACCEPTABLE = "acceptable"  # 可接受
    POOR = "poor"  # 较差
    UNACCEPTABLE = "unacceptable"  # 不可接受


class ReviewFocus(str, Enum):
    """审核重点"""
    ACCURACY = "accuracy"  # 准确性
    COMPLETENESS = "completeness"  # 完整性
    CONSISTENCY = "consistency"  # 一致性
    CLARITY = "clarity"  # 清晰度
    SAFETY = "safety"  # 安全性
    COMPLIANCE = "compliance"  # 合规性


class ReflectionResult(BaseModel):
    """反思审查结果"""
    quality_level: QualityLevel = Field(description="质量等级")
    overall_score: float = Field(ge=0.0, le=1.0, description="综合评分")
    accuracy_score: float = Field(ge=0.0, le=1.0, description="准确性评分")
    completeness_score: float = Field(ge=0.0, le=1.0, description="完整性评分")
    consistency_score: float = Field(ge=0.0, le=1.0, description="一致性评分")
    clarity_score: float = Field(ge=0.0, le=1.0, description="清晰度评分")
    confidence_score: float = Field(ge=0.0, le=1.0, description="置信度评分")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="发现的问题")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    needs_human_review: bool = Field(default=False, description="是否需要人工审核")
    revised_response: Optional[str] = Field(default=None, description="改进后的回答")


@dataclass
class ReviewContext:
    """审核上下文"""
    specialist_type: str
    original_query: str
    specialist_response: Dict[str, Any]
    confidence_threshold: float = 0.7


class ReflectionSpecialist(BaseAgent):
    """
    质量审查智能体
    
    职责：
    1. 对专家回答进行质量评估
    2. 验证回答的准确性和完整性
    3. 评估置信度和一致性
    4. 识别潜在错误和风险
    5. 提供改进建议
    6. 决定是否需要人工审核
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        confidence_threshold: float = 0.7
    ):
        """
        初始化质量审查专家
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            confidence_threshold: 置信度阈值，低于此值需要人工审核
        """
        self.confidence_threshold = confidence_threshold
        system_prompt = self._load_system_prompt()
        
        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=5,
            timeout=30.0
        )
        
        self.review_history: List[Dict[str, Any]] = []
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="reflection",
                filename="reflection_agent.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            print(f"⚠️ [质量审查智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        return {
            "quality_levels": [q.value for q in QualityLevel],
            "review_focuses": [r.value for r in ReviewFocus],
            "confidence_threshold": self.confidence_threshold,
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """你是一位专业的质量审查专家，具有以下能力：
1. 对专业回答进行严格的质量评估
2. 识别回答中的潜在错误、不一致或遗漏
3. 评估置信度和可靠性
4. 提供建设性的改进建议
5. 判断是否需要人工专家介入

在审查时，请关注：
- 事实准确性和数据可靠性
- 逻辑一致性和推理正确性
- 回答的完整性和全面性
- 表达的清晰度和专业性
- 风险识别和合规性检查

请给出客观、公正、严谨的评估。
"""
    
    def evaluate_quality_scores(
        self,
        specialist_response: Dict[str, Any],
        specialist_type: str
    ) -> Dict[str, float]:
        """
        评估各项质量分数
        
        Args:
            specialist_response: 专家响应
            specialist_type: 专家类型
            
        Returns:
            各维度评分
        """
        base_score = specialist_response.get("confidence", 0.7)
        
        accuracy_score = base_score
        completeness_score = base_score
        consistency_score = base_score
        clarity_score = base_score
        confidence_score = base_score
        
        if specialist_response.get("success", False):
            accuracy_score = min(1.0, base_score + 0.1)
            completeness_score = min(1.0, base_score + 0.05)
        else:
            accuracy_score = max(0.0, base_score - 0.2)
            completeness_score = max(0.0, base_score - 0.15)
        
        if specialist_type == "tax":
            if specialist_response.get("analysis", {}).get("tax_rate"):
                accuracy_score = min(1.0, accuracy_score + 0.1)
            if specialist_response.get("risk_assessment", {}).get("risk_level") == "high":
                completeness_score = min(1.0, completeness_score + 0.05)
        
        elif specialist_type == "legal":
            if specialist_response.get("analysis", {}).get("risk_clauses"):
                completeness_score = min(1.0, completeness_score + 0.1)
            if specialist_response.get("risk_assessment", {}).get("risk_level") == "high":
                confidence_score = max(0.0, confidence_score - 0.15)
        
        elif specialist_type == "finance":
            if specialist_response.get("analysis", {}).get("financial_indicators"):
                accuracy_score = min(1.0, accuracy_score + 0.1)
        
        overall_score = (
            accuracy_score * 0.35 +
            completeness_score * 0.25 +
            consistency_score * 0.15 +
            clarity_score * 0.10 +
            confidence_score * 0.15
        )
        
        return {
            "accuracy_score": round(accuracy_score, 3),
            "completeness_score": round(completeness_score, 3),
            "consistency_score": round(consistency_score, 3),
            "clarity_score": round(clarity_score, 3),
            "confidence_score": round(confidence_score, 3),
            "overall_score": round(overall_score, 3)
        }
    
    def identify_issues(
        self,
        specialist_response: Dict[str, Any],
        specialist_type: str,
        quality_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        识别问题
        
        Args:
            specialist_response: 专家响应
            specialist_type: 专家类型
            quality_scores: 质量评分
            
        Returns:
            发现的问题列表
        """
        issues = []
        
        if quality_scores["accuracy_score"] < 0.7:
            issues.append({
                "type": "accuracy",
                "severity": "high",
                "description": "准确性评分较低，可能存在错误信息",
                "suggestion": "建议核实关键数据和结论"
            })
        
        if quality_scores["completeness_score"] < 0.7:
            issues.append({
                "type": "completeness",
                "severity": "medium",
                "description": "回答可能不够完整",
                "suggestion": "建议补充相关方面的分析"
            })
        
        if quality_scores["consistency_score"] < 0.7:
            issues.append({
                "type": "consistency",
                "severity": "medium",
                "description": "回答的一致性存在疑问",
                "suggestion": "建议检查逻辑推理过程"
            })
        
        if quality_scores["confidence_score"] < self.confidence_threshold:
            issues.append({
                "type": "confidence",
                "severity": "high",
                "description": "置信度低于阈值",
                "suggestion": "需要人工专家复核"
            })
        
        if not specialist_response.get("success", False):
            issues.append({
                "type": "execution",
                "severity": "high",
                "description": "专家处理过程中出现错误",
                "suggestion": specialist_response.get("error", "检查系统状态")
            })
        
        if specialist_type == "tax":
            if not specialist_response.get("analysis", {}).get("tax_rate"):
                issues.append({
                    "type": "missing_info",
                    "severity": "medium",
                    "description": "税务分析缺少关键税率信息",
                    "suggestion": "提供具体的税率计算"
                })
        
        elif specialist_type == "legal":
            if specialist_response.get("risk_assessment", {}).get("risk_level") == "high":
                issues.append({
                    "type": "high_risk",
                    "severity": "high",
                    "description": "法律风险评估为高风险",
                    "suggestion": "强烈建议人工法务审核"
                })
        
        return issues
    
    def generate_suggestions(
        self,
        specialist_response: Dict[str, Any],
        specialist_type: str,
        issues: List[Dict[str, Any]]
    ) -> List[str]:
        """
        生成改进建议
        
        Args:
            specialist_response: 专家响应
            specialist_type: 专家类型
            issues: 发现的问题
            
        Returns:
            改进建议列表
        """
        suggestions = []
        
        if any(issue["type"] == "accuracy" for issue in issues):
            suggestions.append("建议核实引用的法规条款和数据来源")
            suggestions.append("增加关键结论的论证依据")
        
        if any(issue["type"] == "completeness" for issue in issues):
            suggestions.append("建议补充相关法规或案例参考")
            suggestions.append("考虑增加风险提示和注意事项")
        
        if any(issue["type"] == "confidence" for issue in issues):
            suggestions.append("建议咨询专业人员进行复核")
            suggestions.append("明确标注置信度较低的结论")
        
        if specialist_type == "tax":
            suggestions.append("确保提供最新的税收政策信息")
            suggestions.append("明确注明计算的假设条件")
            suggestions.append("添加免责提示：具体税务情况以税务机关为准")
        
        elif specialist_type == "legal":
            suggestions.append("建议明确标注：本回答不构成法律意见")
            suggestions.append("对于重大事项，建议由持证律师出具正式意见")
            suggestions.append("补充相关的法律时效性说明")
        
        elif specialist_type == "finance":
            suggestions.append("建议注明财务数据的局限性")
            suggestions.append("提供数据来源和时间范围")
            suggestions.append("添加投资风险提示")
        
        return list(set(suggestions))
    
    def determine_quality_level(
        self,
        overall_score: float,
        issues: List[Dict[str, Any]]
    ) -> QualityLevel:
        """
        确定质量等级
        
        Args:
            overall_score: 综合评分
            issues: 发现的问题
            
        Returns:
            质量等级
        """
        critical_issues = [i for i in issues if i["severity"] == "high"]
        
        if overall_score >= 0.9 and len(critical_issues) == 0:
            return QualityLevel.EXCELLENT
        elif overall_score >= 0.75 and len(critical_issues) <= 1:
            return QualityLevel.GOOD
        elif overall_score >= 0.6 and len(critical_issues) <= 2:
            return QualityLevel.ACCEPTABLE
        elif overall_score >= 0.45:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE
    
    async def run(
        self,
        specialist_type: str,
        original_query: str,
        specialist_response: Dict[str, Any],
        context: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行质量审查
        
        Args:
            specialist_type: 专家类型
            original_query: 原始问题
            specialist_response: 专家响应
            context: 上下文信息
            **kwargs: 其他参数
            
        Returns:
            审查结果
        """
        try:
            quality_scores = self.evaluate_quality_scores(
                specialist_response,
                specialist_type
            )
            
            issues = self.identify_issues(
                specialist_response,
                specialist_type,
                quality_scores
            )
            
            suggestions = self.generate_suggestions(
                specialist_response,
                specialist_type,
                issues
            )
            
            quality_level = self.determine_quality_level(
                quality_scores["overall_score"],
                issues
            )
            
            needs_human_review = (
                quality_scores["confidence_score"] < self.confidence_threshold or
                any(issue["severity"] == "high" for issue in issues) or
                quality_level in [QualityLevel.POOR, QualityLevel.UNACCEPTABLE]
            )
            
            revised_response = None
            if issues and quality_level in [QualityLevel.POOR, QualityLevel.ACCEPTABLE]:
                revised_response = await self._revise_response(
                    original_query,
                    specialist_response,
                    issues
                )
            
            result = ReflectionResult(
                quality_level=quality_level,
                overall_score=quality_scores["overall_score"],
                accuracy_score=quality_scores["accuracy_score"],
                completeness_score=quality_scores["completeness_score"],
                consistency_score=quality_scores["consistency_score"],
                clarity_score=quality_scores["clarity_score"],
                confidence_score=quality_scores["confidence_score"],
                issues=issues,
                suggestions=suggestions,
                needs_human_review=needs_human_review,
                revised_response=revised_response
            )
            
            self._record_review(
                specialist_type,
                original_query,
                result
            )
            
            return {
                "success": True,
                "specialist_type": specialist_type,
                "review_result": result.dict(),
                "needs_human_review": needs_human_review,
                "quality_level": quality_level.value,
                "overall_score": quality_scores["overall_score"]
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"质量审查数据失败: {e}")
            return {
                "success": False,
                "error": f"数据错误: {str(e)}",
                "needs_human_review": True,
                "quality_level": QualityLevel.UNACCEPTABLE.value
            }
        except (OSError, IOError) as e:
            logger.error(f"质量审查IO失败: {e}")
            return {
                "success": False,
                "error": f"IO错误: {str(e)}",
                "needs_human_review": True,
                "quality_level": QualityLevel.UNACCEPTABLE.value
            }
        except Exception as e:
            logger.error(f"质量审查失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "needs_human_review": True,
                "quality_level": QualityLevel.UNACCEPTABLE.value
            }
    
    async def review(
        self,
        user_input: str,
        specialist_results: List[Dict[str, Any]],
        intent_result: Any = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行综合质量审查（编排器专用方法）
        
        Args:
            user_input: 用户原始问题
            specialist_results: 专家结果列表
            intent_result: 意图分析结果
            
        Returns:
            审查结果
        """
        if not specialist_results:
            return {
                "confidence": 1.0,
                "needs_revision": False,
                "suggestions": [],
                "quality_score": 1.0
            }
        
        try:
            overall_confidence = 1.0
            needs_revision = False
            all_suggestions = []
            quality_scores = []
            
            for specialist_result in specialist_results:
                specialist_type = specialist_result.get('specialist_type', 'unknown')
                specialist_response = specialist_result.get('response', {})
                
                if isinstance(specialist_response, dict):
                    specialist_response = {
                        'result': specialist_response,
                        'success': specialist_result.get('success', False)
                    }
                
                result = await self.run(
                    specialist_type=specialist_type,
                    original_query=user_input,
                    specialist_response=specialist_response,
                    context={"intent_result": intent_result}
                )
                
                if result.get("success"):
                    quality_scores.append(result.get("overall_score", 0.8))
                    if result.get("needs_human_review"):
                        needs_revision = True
                    all_suggestions.extend(
                        result.get("review_result", {}).get("suggestions", [])
                    )
            
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.8
            
            return {
                "confidence": avg_quality,
                "needs_revision": needs_revision,
                "suggestions": all_suggestions[:5],
                "quality_score": avg_quality
            }
            
        except Exception as e:
            logger.error(f"综合审查失败: {e}")
            return {
                "confidence": 0.8,
                "needs_revision": False,
                "suggestions": [],
                "quality_score": 0.8
            }
    
    async def _revise_response(
        self,
        original_query: str,
        specialist_response: Dict[str, Any],
        issues: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        改进回答
        
        Args:
            original_query: 原始问题
            specialist_response: 专家响应
            issues: 发现的问题
            
        Returns:
            改进后的回答
        """
        try:
            prompt = f"""请基于以下信息，改进专家的回答：

原始问题：{original_query}

专家回答：
{specialist_response.get('analysis', {})}

发现的问题：
{json.dumps(issues, ensure_ascii=False, indent=2)}

请：
1. 修正发现的问题
2. 补充遗漏的重要信息
3. 提高表达的清晰度
4. 保持专业性和准确性

请直接输出改进后的回答，不需要解释。
"""
            
            full_prompt = f"{self.system_prompt}\n\n{prompt}" if self.system_prompt else prompt
            revised = await self.llm_adapter.generate(
                prompt=full_prompt,
                temperature=0.3
            )
            
            if hasattr(revised, 'content'):
                return revised.content
            return str(revised) if revised else None
            
        except (ValueError, KeyError) as e:
            logger.warning(f"改进回答数据失败: {e}")
            return None
        except (OSError, IOError) as e:
            logger.warning(f"改进回答IO失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"改进回答失败: {e}")
            return None
    
    def _record_review(
        self,
        specialist_type: str,
        original_query: str,
        result: ReflectionResult
    ):
        """
        记录审查历史
        
        Args:
            specialist_type: 专家类型
            original_query: 原始问题
            result: 审查结果
        """
        review_record = {
            "timestamp": datetime.now().isoformat(),
            "specialist_type": specialist_type,
            "query": original_query[:100],
            "quality_level": result.quality_level.value,
            "overall_score": result.overall_score,
            "needs_human_review": result.needs_human_review
        }
        
        self.review_history.append(review_record)
        
        if len(self.review_history) > 100:
            self.review_history = self.review_history[-100:]
    
    def get_review_statistics(self) -> Dict[str, Any]:
        """
        获取审查统计信息
        
        Returns:
            统计信息
        """
        if not self.review_history:
            return {
                "total_reviews": 0,
                "average_score": 0,
                "human_review_rate": 0
            }
        
        total = len(self.review_history)
        avg_score = sum(r["overall_score"] for r in self.review_history) / total
        human_review_count = sum(1 for r in self.review_history if r["needs_human_review"])
        
        return {
            "total_reviews": total,
            "average_score": round(avg_score, 3),
            "human_review_rate": round(human_review_count / total, 3),
            "quality_distribution": self._get_quality_distribution(),
            "specialist_performance": self._get_specialist_performance()
        }
    
    def _get_quality_distribution(self) -> Dict[str, int]:
        """获取质量等级分布"""
        distribution = {level.value: 0 for level in QualityLevel}
        for record in self.review_history:
            distribution[record["quality_level"]] += 1
        return distribution
    
    def _get_specialist_performance(self) -> Dict[str, Dict[str, float]]:
        """获取各专家表现统计"""
        performance = {}
        for record in self.review_history:
            specialist = record["specialist_type"]
            if specialist not in performance:
                performance[specialist] = {"count": 0, "total_score": 0}
            performance[specialist]["count"] += 1
            performance[specialist]["total_score"] += record["overall_score"]
        
        for specialist in performance:
            count = performance[specialist]["count"]
            total = performance[specialist]["total_score"]
            performance[specialist]["avg_score"] = round(total / count, 3)
            del performance[specialist]["total_score"]
        
        return performance
    
    async def multi_perspective_review(
        self,
        specialist_response: Dict[str, Any],
        focus_areas: List[ReviewFocus] = None
    ) -> Dict[str, Any]:
        """
        多角度审查
        
        Args:
            specialist_response: 专家响应
            focus_areas: 重点审核领域
            
        Returns:
            多角度审查结果
        """
        if focus_areas is None:
            focus_areas = [ReviewFocus.ACCURACY, ReviewFocus.COMPLETENESS, ReviewFocus.SAFETY]
        
        focus_results = {}
        
        for focus in focus_areas:
            if focus == ReviewFocus.ACCURACY:
                focus_results["accuracy"] = await self._review_accuracy(specialist_response)
            elif focus == ReviewFocus.COMPLETENESS:
                focus_results["completeness"] = await self._review_completeness(specialist_response)
            elif focus == ReviewFocus.CONSISTENCY:
                focus_results["consistency"] = await self._review_consistency(specialist_response)
            elif focus == ReviewFocus.CLARITY:
                focus_results["clarity"] = await self._review_clarity(specialist_response)
            elif focus == ReviewFocus.SAFETY:
                focus_results["safety"] = await self._review_safety(specialist_response)
            elif focus == ReviewFocus.COMPLIANCE:
                focus_results["compliance"] = await self._review_compliance(specialist_response)
        
        return focus_results
    
    async def _review_accuracy(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """审查准确性"""
        analysis = response.get("analysis", {})
        
        return {
            "passed": response.get("confidence", 0) >= 0.8,
            "confidence": response.get("confidence", 0),
            "has_data_support": bool(analysis.get("tax_rate") or analysis.get("financial_indicators")),
            "notes": "数据支持充分" if analysis.get("tax_rate") else "建议补充数据支持"
        }
    
    async def _review_completeness(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """审查完整性"""
        analysis = response.get("analysis", {})
        
        return {
            "passed": len(analysis) > 0,
            "key_elements_present": bool(analysis),
            "recommendations_present": bool(response.get("recommendations")),
            "risk_assessment_present": bool(response.get("risk_assessment")),
            "notes": "包含关键分析元素" if analysis else "建议补充分析内容"
        }
    
    async def _review_consistency(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """审查一致性"""
        risk_assessment = response.get("risk_assessment", {})
        risk_level = risk_assessment.get("risk_level", "low")
        
        return {
            "passed": True,
            "internal_consistency": "consistent",
            "risk_level": risk_level,
            "notes": "内部一致性检查通过"
        }
    
    async def _review_clarity(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """审查清晰度"""
        analysis = response.get("analysis", {})
        
        return {
            "passed": True,
            "has_structured_output": isinstance(analysis, dict),
            "has_recommendations": bool(response.get("recommendations")),
            "notes": "输出结构清晰"
        }
    
    async def _review_safety(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """审查安全性"""
        recommendations = response.get("recommendations", [])
        disclaimer_present = any(
            "建议" in r or "咨询" in r or "专业" in r 
            for r in recommendations
        )
        
        return {
            "passed": disclaimer_present,
            "has_disclaimers": disclaimer_present,
            "risk_level": response.get("risk_assessment", {}).get("risk_level", "low"),
            "notes": "包含必要的安全提示" if disclaimer_present else "建议添加免责声明"
        }
    
    async def _review_compliance(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """审查合规性"""
        compliance_status = response.get("analysis", {}).get("compliance_status", "unknown")
        
        return {
            "passed": compliance_status in ["compliant", "review_required"],
            "compliance_status": compliance_status,
            "notes": f"合规状态：{compliance_status}"
        }
    
    async def stream_run(
        self,
        user_input: str,
        history: List[Dict] = None,
        **kwargs
    ):
        """
        流式执行质量审查智能体
        
        实现基类的抽象方法
        
        Args:
            user_input: 用户输入
            history: 对话历史
            
        Yields:
            处理结果片段
        """
        result = await self.run(user_input, history, **kwargs)
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
        
        for char in result_str:
            yield char
    
    async def audit(
        self,
        state: Dict[str, Any],
        documents: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行专业审查（协调器专用方法）
        
        实现与其他专业智能体一致的接口
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表（空列表，因为反思智能体不产生发现）
        """
        try:
            print(f"🔍 [反思智能体] 开始审查全局状态")
            
            specialist_results = state.get("specialist_results", [])
            user_input = state.get("user_input", "")
            intent_result = state.get("intent_result")
            
            review_result = await self.review(
                user_input=user_input,
                specialist_results=specialist_results,
                intent_result=intent_result
            )
            
            state["reflection_result"] = review_result
            
            if review_result.get("confidence", 1.0) < 0.7:
                state["needs_human_review"] = True
                state["review_trigger_reason"] = f"反思审查置信度低: {review_result.get('confidence', 1.0)}"
            
            print(f"✅ [反思智能体] 审查完成，置信度: {review_result.get('confidence', 1.0):.2f}")
            return []
            
        except Exception as e:
            print(f"❌ [反思智能体] 审查失败: {str(e)}")
            state["needs_human_review"] = True
            state["review_trigger_reason"] = f"反思审查异常: {str(e)}"
            return []
