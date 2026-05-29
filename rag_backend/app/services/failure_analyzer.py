"""
失败案例分析器

自动分析用户负面反馈，识别问题根因，生成改进建议。
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.feedback import (
    UserFeedback,
    FailureCase,
    ImprovementRecord,
    FeedbackType,
    FailureType,
    FailureStatus,
    ImprovementType
)

logger = logging.getLogger(__name__)


class FailureAnalyzer:
    """
    失败案例分析器

    功能:
    1. 自动识别失败类型
    2. 分析根本原因
    3. 生成修复建议
    4. 支持 LLM 分析和规则分析
    """

    def __init__(self, llm_service=None, db_session: Session = None):
        """
        初始化失败分析器

        Args:
            llm_service: LLM 服务（可选，用于深度分析）
            db_session: 数据库会话
        """
        self.llm_service = llm_service
        self.db = db_session

    async def analyze_feedback(
        self,
        feedback: UserFeedback,
        use_llm: bool = False
    ) -> FailureCase:
        """
        分析单个反馈，创建失败案例

        Args:
            feedback: 用户反馈
            use_llm: 是否使用 LLM 进行深度分析

        Returns:
            FailureCase: 创建的失败案例
        """
        logger.info(f"[FailureAnalyzer] 开始分析反馈 ID: {feedback.id}")

        try:
            # 1. 识别失败类型
            failure_type = self._classify_failure_type(feedback)

            # 2. 分析根因
            if use_llm and self.llm_service:
                analysis = await self._analyze_with_llm(feedback, failure_type)
            else:
                analysis = self._analyze_with_rules(feedback, failure_type)

            # 3. 生成修复建议
            fix_suggestions = self._generate_fix_suggestions(
                failure_type,
                analysis
            )

            # 4. 创建失败案例记录
            failure_case = FailureCase(
                feedback_id=feedback.id,
                failure_type=failure_type,
                analysis=analysis,
                fix_suggestions=fix_suggestions,
                status=FailureStatus.ANALYZING,
                auto_analyzed=True,
                confidence_score=analysis.get("confidence_score", 70),
                analyzed_at=datetime.now()
            )

            if self.db:
                self.db.add(failure_case)
                self.db.commit()
                self.db.refresh(failure_case)

            logger.info(
                f"[FailureAnalyzer] 分析完成 - "
                f"类型: {failure_type.value}, "
                f"置信度: {failure_case.confidence_score}"
            )

            return failure_case

        except Exception as e:
            logger.error(f"[FailureAnalyzer] 分析失败: {e}")
            raise

    def _classify_failure_type(self, feedback: UserFeedback) -> FailureType:
        """
        基于规则分类失败类型

        Args:
            feedback: 用户反馈

        Returns:
            FailureType: 失败类型
        """
        query = feedback.query.lower()
        response = feedback.response.lower()
        comment = (feedback.comment or "").lower()

        # 关键词匹配规则
        retrieval_keywords = [
            "没找到", "找不到", "没有相关", "无法检索",
            "缺少文档", "没有资料", "检索不到"
        ]

        hallucination_keywords = [
            "编造", "瞎说", "不准确", "错误信息",
            "没有依据", "凭空捏造", "虚假"
        ]

        incomplete_keywords = [
            "不完整", "缺少", "遗漏", "只有部分",
            "信息不足", "太简略", "不够详细"
        ]

        irrelevant_keywords = [
            "不相关", "答非所问", "没回答问题",
            "跑题", "偏离主题"
        ]

        generation_keywords = [
            "格式错误", "理解错误", "生成失败",
            "无法理解", "解释不清"
        ]

        # 检查关键词
        if any(kw in comment or kw in response for kw in retrieval_keywords):
            return FailureType.RETRIEVAL

        if any(kw in comment for kw in hallucination_keywords):
            return FailureType.HALLUCINATION

        if any(kw in comment or kw in response for kw in incomplete_keywords):
            return FailureType.INCOMPLETE

        if any(kw in comment or kw in response for kw in irrelevant_keywords):
            return FailureType.IRRELEVANT

        if any(kw in comment for kw in generation_keywords):
            return FailureType.GENERATION

        # 默认根据评分判断
        if feedback.rating and feedback.rating <= 2:
            # 检查是否有使用的文档块
            if not feedback.chunks_used or len(feedback.chunks_used) == 0:
                return FailureType.RETRIEVAL
            else:
                return FailureType.GENERATION

        return FailureType.OTHER

    def _analyze_with_rules(
        self,
        feedback: UserFeedback,
        failure_type: FailureType
    ) -> Dict[str, Any]:
        """
        基于规则分析失败原因

        Args:
            feedback: 用户反馈
            failure_type: 失败类型

        Returns:
            分析结果字典
        """
        analysis = {
            "failure_type": failure_type.value,
            "confidence_score": 70,
            "root_causes": [],
            "missing_info": [],
            "context_issues": [],
            "recommendations": []
        }

        # 根据失败类型进行分析
        if failure_type == FailureType.RETRIEVAL:
            analysis["root_causes"].append("检索未找到相关文档")

            # 检查检索方法
            if feedback.retrieval_method == "simple":
                analysis["recommendations"].append(
                    "建议使用 GraphRAG 或 Agentic RAG 增强检索能力"
                )

            # 检查文档块数量
            chunks_count = len(feedback.chunks_used or [])
            if chunks_count == 0:
                analysis["root_causes"].append("知识库中可能缺少相关文档")
                analysis["recommendations"].append("建议补充知识库文档")

        elif failure_type == FailureType.INCOMPLETE:
            analysis["root_causes"].append("检索到的信息不完整")

            # 分析缺失的方面
            if "税率" in feedback.query and "税率" not in feedback.response:
                analysis["missing_info"].append("具体税率数值")

            if "优惠" in feedback.query and "优惠" not in feedback.response:
                analysis["missing_info"].append("优惠政策详情")

            if "如何" in feedback.query or "怎么" in feedback.query:
                analysis["missing_info"].append("具体操作步骤")

            analysis["recommendations"].append("增加检索轮次，补充缺失信息")
            analysis["recommendations"].append("使用 Agentic RAG 进行多轮检索")

        elif failure_type == FailureType.HALLUCINATION:
            analysis["root_causes"].append("生成内容超出上下文范围")
            analysis["context_issues"].append("上下文不足或不相关")

            analysis["recommendations"].append("加强上下文约束")
            analysis["recommendations"].append("优化 Prompt，要求严格基于上下文回答")
            analysis["recommendations"].append("添加幻觉检测机制")

        elif failure_type == FailureType.IRRELEVANT:
            analysis["root_causes"].append("检索结果与查询不相关")
            analysis["context_issues"].append("查询理解错误或检索偏离")

            analysis["recommendations"].append("优化查询改写策略")
            analysis["recommendations"].append("调整相似度阈值")
            analysis["recommendations"].append("使用混合检索提高相关性")

        elif failure_type == FailureType.GENERATION:
            analysis["root_causes"].append("生成环节出错")

            if "格式" in (feedback.comment or ""):
                analysis["context_issues"].append("输出格式不符合要求")
                analysis["recommendations"].append("优化 Prompt，明确输出格式要求")

            if "理解" in (feedback.comment or ""):
                analysis["context_issues"].append("模型理解错误")
                analysis["recommendations"].append("改进 Prompt 的指令清晰度")

        # 性能分析
        if feedback.total_time and feedback.total_time > 10000:  # 超过 10秒
            analysis["context_issues"].append("响应时间过长")
            analysis["recommendations"].append("优化检索性能，考虑缓存机制")

        return analysis

    async def _analyze_with_llm(
        self,
        feedback: UserFeedback,
        failure_type: FailureType
    ) -> Dict[str, Any]:
        """
        使用 LLM 进行深度分析

        Args:
            feedback: 用户反馈
            failure_type: 失败类型

        Returns:
            分析结果字典
        """
        prompt = f"""你是一个 RAG 系统质量分析专家。请分析以下失败案例，识别根本原因并给出改进建议。

用户查询: {feedback.query}

系统响应: {feedback.response}

用户反馈:
- 反馈类型: {feedback.feedback_type.value}
- 评分: {feedback.rating}/5
- 评论: {feedback.comment}

检索信息:
- 检索方法: {feedback.retrieval_method}
- 使用的文档块数: {len(feedback.chunks_used or [])}

初步判断的失败类型: {failure_type.value}

请分析:
1. 根本原因是什么？
2. 缺少了哪些关键信息？
3. 上下文存在什么问题？
4. 具体的改进建议是什么？

返回 JSON 格式:
{{
    "root_causes": ["原因1", "原因2"],
    "missing_info": ["缺失1", "缺失2"],
    "context_issues": ["问题1", "问题2"],
    "recommendations": ["建议1", "建议2"],
    "confidence_score": 85
}}

只返回 JSON，不要其他内容。
"""

        try:
            response = await self.llm_service.generate(prompt, max_tokens=1000)

            # 解析 JSON
            analysis = json.loads(response)

            # 添加失败类型
            analysis["failure_type"] = failure_type.value

            return analysis

        except Exception as e:
            logger.error(f"[FailureAnalyzer] LLM 分析失败: {e}")
            # 降级到规则分析
            return self._analyze_with_rules(feedback, failure_type)

    def _generate_fix_suggestions(
        self,
        failure_type: FailureType,
        analysis: Dict[str, Any]
    ) -> List[str]:
        """
        生成修复建议

        Args:
            failure_type: 失败类型
            analysis: 分析结果

        Returns:
            修复建议列表
        """
        suggestions = []

        # 从分析结果中提取建议
        if "recommendations" in analysis:
            suggestions.extend(analysis["recommendations"])

        # 根据失败类型添加通用建议
        if failure_type == FailureType.RETRIEVAL:
            suggestions.append("考虑扩充知识库内容")
            suggestions.append("优化文档分块策略")

        elif failure_type == FailureType.INCOMPLETE:
            suggestions.append("启用多轮检索补充信息")
            suggestions.append("使用 Agentic RAG 自动识别缺失方面")

        elif failure_type == FailureType.HALLUCINATION:
            suggestions.append("在 Prompt 中强调只使用给定上下文")
            suggestions.append("添加引用标注，方便验证")

        elif failure_type == FailureType.IRRELEVANT:
            suggestions.append("改进查询理解和改写")
            suggestions.append("调整检索相似度阈值")

        # 去重
        return list(set(suggestions))

    async def batch_analyze_negative_feedbacks(
        self,
        tenant_id: str,
        limit: int = 50
    ) -> List[FailureCase]:
        """
        批量分析负面反馈

        Args:
            tenant_id: 租户 ID
            limit: 最大处理数量

        Returns:
            创建的失败案例列表
        """
        if not self.db:
            raise ValueError("需要提供数据库会话")

        logger.info(
            f"[FailureAnalyzer] 开始批量分析负面反馈 - "
            f"租户: {tenant_id}, 限制: {limit}"
        )

        # 查询未分析的负面反馈
        stmt = (
            select(UserFeedback)
            .outerjoin(FailureCase, UserFeedback.id == FailureCase.feedback_id)
            .where(
                and_(
                    UserFeedback.tenant_id == tenant_id,
                    UserFeedback.feedback_type == FeedbackType.NEGATIVE,
                    FailureCase.id.is_(None)  # 未创建失败案例
                )
            )
            .limit(limit)
        )

        result = self.db.execute(stmt)
        feedbacks = result.scalars().all()

        logger.info(f"[FailureAnalyzer] 找到 {len(feedbacks)} 条待分析反馈")

        # 批量分析
        failure_cases = []
        for feedback in feedbacks:
            try:
                failure_case = await self.analyze_feedback(
                    feedback,
                    use_llm=bool(self.llm_service)
                )
                failure_cases.append(failure_case)

            except Exception as e:
                logger.error(
                    f"[FailureAnalyzer] 分析反馈 {feedback.id} 失败: {e}"
                )
                continue

        logger.info(
            f"[FailureAnalyzer] 批量分析完成 - "
            f"成功: {len(failure_cases)}/{len(feedbacks)}"
        )

        return failure_cases

    async def suggest_improvements(
        self,
        failure_case: FailureCase
    ) -> ImprovementRecord:
        """
        基于失败案例生成改进记录

        Args:
            failure_case: 失败案例

        Returns:
            ImprovementRecord: 改进记录
        """
        logger.info(f"[FailureAnalyzer] 生成改进建议 - 案例 ID: {failure_case.id}")

        # 根据失败类型确定改进类型
        improvement_type_map = {
            FailureType.RETRIEVAL: ImprovementType.RETRIEVAL,
            FailureType.INCOMPLETE: ImprovementType.RETRIEVAL,
            FailureType.IRRELEVANT: ImprovementType.RETRIEVAL,
            FailureType.HALLUCINATION: ImprovementType.PROMPT,
            FailureType.GENERATION: ImprovementType.PROMPT,
            FailureType.OTHER: ImprovementType.OTHER
        }

        improvement_type = improvement_type_map.get(
            failure_case.failure_type,
            ImprovementType.OTHER
        )

        # 生成配置建议
        before_config, after_config = self._generate_config_changes(
            failure_case
        )

        # 创建改进记录
        improvement = ImprovementRecord(
            failure_case_id=failure_case.id,
            improvement_type=improvement_type,
            before_config=before_config,
            after_config=after_config,
            description=self._generate_improvement_description(failure_case)
        )

        if self.db:
            self.db.add(improvement)
            self.db.commit()
            self.db.refresh(improvement)

        logger.info(
            f"[FailureAnalyzer] 改进记录创建完成 - "
            f"类型: {improvement_type.value}"
        )

        return improvement

    def _generate_config_changes(
        self,
        failure_case: FailureCase
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        生成配置变更建议

        Args:
            failure_case: 失败案例

        Returns:
            (before_config, after_config) 元组
        """
        before_config = {
            "retrieval_method": "simple",
            "max_iterations": 1,
            "top_k": 5,
            "similarity_threshold": 0.7
        }

        after_config = before_config.copy()

        # 根据失败类型调整配置
        if failure_case.failure_type == FailureType.RETRIEVAL:
            after_config["retrieval_method"] = "graphrag"
            after_config["top_k"] = 10

        elif failure_case.failure_type == FailureType.INCOMPLETE:
            after_config["retrieval_method"] = "agentic"
            after_config["max_iterations"] = 3

        elif failure_case.failure_type == FailureType.IRRELEVANT:
            after_config["similarity_threshold"] = 0.8
            after_config["retrieval_method"] = "hybrid"

        elif failure_case.failure_type == FailureType.HALLUCINATION:
            after_config["strict_context_mode"] = True
            after_config["enable_citation"] = True

        return before_config, after_config

    def _generate_improvement_description(
        self,
        failure_case: FailureCase
    ) -> str:
        """
        生成改进描述

        Args:
            failure_case: 失败案例

        Returns:
            改进描述文本
        """
        failure_type = failure_case.failure_type.value
        analysis = failure_case.analysis or {}
        root_causes = analysis.get("root_causes", [])

        description = f"针对 {failure_type} 类型失败的改进方案。\n\n"

        if root_causes:
            description += "根本原因:\n"
            for cause in root_causes:
                description += f"- {cause}\n"
            description += "\n"

        if failure_case.fix_suggestions:
            description += "改进措施:\n"
            for suggestion in failure_case.fix_suggestions:
                description += f"- {suggestion}\n"

        return description

    def get_failure_statistics(
        self,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        获取失败统计信息

        Args:
            tenant_id: 租户 ID

        Returns:
            统计信息字典
        """
        if not self.db:
            raise ValueError("需要提供数据库会话")

        stats = {
            "total_failures": 0,
            "by_type": {},
            "by_status": {},
            "avg_confidence": 0.0
        }

        # 按类型统计
        for failure_type in FailureType:
            stmt = (
                select(func.count(FailureCase.id))
                .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
                .where(
                    and_(
                        UserFeedback.tenant_id == tenant_id,
                        FailureCase.failure_type == failure_type
                    )
                )
            )
            count = self.db.execute(stmt).scalar()
            stats["by_type"][failure_type.value] = count
            stats["total_failures"] += count

        # 按状态统计
        for status in FailureStatus:
            stmt = (
                select(func.count(FailureCase.id))
                .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
                .where(
                    and_(
                        UserFeedback.tenant_id == tenant_id,
                        FailureCase.status == status
                    )
                )
            )
            count = self.db.execute(stmt).scalar()
            stats["by_status"][status.value] = count

        # 平均置信度
        stmt = (
            select(func.avg(FailureCase.confidence_score))
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(
                and_(
                    UserFeedback.tenant_id == tenant_id,
                    FailureCase.confidence_score.isnot(None)
                )
            )
        )
        avg_confidence = self.db.execute(stmt).scalar()
        stats["avg_confidence"] = round(float(avg_confidence), 2) if avg_confidence else 0.0

        return stats


# 辅助函数

def create_failure_analyzer(
    llm_service=None,
    db_session: Session = None
) -> FailureAnalyzer:
    """
    创建失败分析器实例

    Args:
        llm_service: LLM 服务
        db_session: 数据库会话

    Returns:
        FailureAnalyzer: 分析器实例
    """
    return FailureAnalyzer(
        llm_service=llm_service,
        db_session=db_session
    )
