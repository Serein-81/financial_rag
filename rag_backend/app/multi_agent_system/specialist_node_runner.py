"""
Specialist Node Runner — 统一的 LangGraph specialist 节点执行器。

消除 finance/tax/legal 三个 specialist 节点中的重复代码，
提供一致的错误分类、格式化、规范化、结果合并逻辑。
"""

import logging
from typing import Any, Callable, Dict, Optional

from app.langgraph.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 错误报告模板（按专家类型 + 错误类型）
# ---------------------------------------------------------------------------

_ERROR_TEMPLATES: Dict[str, Dict[str, str]] = {
    "finance": {
        "timeout": (
            "## 💰 财务专家分析报告\n\n"
            "### ⚠️ 分析处理超时\n\n"
            "**原因**：财务分析请求处理时间超过系统上限，未能按时完成。\n\n"
            "**建议**：\n"
            "1. 稍后重新提交查询\n"
            "2. 尝试缩短或简化您的问题描述\n"
            "3. 如持续出现此问题，请联系系统管理员\n\n"
            "---\n*⏱️ 超时时间: 60秒*"
        ),
        "data_error": (
            "## 💰 财务专家分析报告\n\n"
            "### ⚠️ 数据获取异常\n\n"
            "**原因**：{error_msg}\n\n"
            "**建议**：\n"
            "1. 确认企业财务数据已正确导入系统\n"
            "2. 检查数据格式是否符合要求\n"
            "3. 如需帮助，请联系系统管理员\n\n"
            "---\n*📊 数据来源: 企业财务数据库*"
        ),
        "unknown": (
            "## 💰 财务专家分析报告\n\n"
            "### ⚠️ 分析处理失败\n\n"
            "**原因**：{error_msg}\n\n"
            "**建议**：{fallback}\n\n"
            "---\n*🔍 请稍后重试*"
        ),
    },
    "tax": {
        "unknown": (
            "## 📋 税务专家分析报告\n\n"
            "### ⚠️ 分析处理失败\n\n"
            "**原因**：{error_msg}\n\n"
            "**建议**：请稍后重试，或联系系统管理员获取帮助。\n\n"
            "---\n*🔍 税务分析未能完成*"
        ),
    },
    "legal": {
        "unknown": (
            "## ⚖️ 法律专家分析报告\n\n"
            "### ⚠️ 分析处理失败\n\n"
            "**原因**：{error_msg}\n\n"
            "**建议**：请稍后重试，或联系系统管理员获取帮助。\n\n"
            "---\n*🔍 法律分析未能完成*"
        ),
    },
}

# ---------------------------------------------------------------------------
# 输出 Schema 校验
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field, ValidationError
from .circuit_breaker import circuit_breaker


class SpecialistOutputSchema(BaseModel):
    """specialist.run() 返回值的强制 Schema"""
    success: bool = True
    domain: str = Field(default="general", max_length=50)
    text_answer: str | None = Field(default=None, max_length=50000)
    analysis: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    error: str | None = None


def validate_specialist_output(result: dict, source: str) -> dict:
    """校验 specialist 输出，非法字段被静默修正（不抛异常）"""
    try:
        validated = SpecialistOutputSchema.model_validate(result)
        return result  # 校验通过，原样返回
    except ValidationError as e:
        logger.warning("[%s] 输出 Schema 校验发现异常: %s", source, e)
        # 静默修正：confidence 超范围
        if "confidence" in str(e):
            result["confidence"] = max(0.0, min(1.0, result.get("confidence", 0.85)))
        # 静默修正：domain 过长
        if "domain" in str(e):
            result["domain"] = str(result.get("domain", "general"))[:50]
        return result


# ---------------------------------------------------------------------------
# 公共执行器
# ---------------------------------------------------------------------------


async def run_specialist_node(
    state: AgentState,
    *,
    source: str,
    specialist,
    format_success: Callable[[Dict[str, Any]], str],
    format_fallback: Callable[[Dict[str, Any]], str],
    payload_formatter,
    tenant_id: str,
    user_id: str,
) -> AgentState:
    """统一的 specialist 节点执行器。

    处理流程：
    1. 调用 specialist.run()
    2. 检查 result.success — 失败时生成错误报告
    3. 格式化结果（优先 format_success，失败时降级到 format_fallback）
    4. 通过 payload_formatter 规范化
    5. 合并到 state.specialist_results（同源替换）

    Args:
        state: LangGraph AgentState
        source: 专家标识 ("finance" / "tax" / "legal")
        specialist: 专家实例（有 .run() 方法）
        format_success: 成功结果格式化函数
        format_fallback: 降级格式化函数
        payload_formatter: BlackboardPayloadFormatter 实例
        tenant_id: 租户ID
        user_id: 用户ID

    Returns:
        更新后的 AgentState
    """
    logger.info("[节点] %s 开始", source)
    specialist_context = {"tenant_id": tenant_id, "user_id": user_id}

    try:
        # 🆕 熔断器检查
        if circuit_breaker.is_tripped(source):
            logger.warning("[%s] 熔断中，跳过执行", source)
            markdown_report = _build_error_report(
                source=source,
                error_type="circuit_breaker",
                error_msg=f"{source} 专家连续异常，已暂时跳过（冷却中）",
                fallback=f"请稍后重试，{source} 专家当前不可用",
            )
            result = {"success": False, "error": "circuit_breaker"}
            circuit_breaker.record_success(source)
        else:
            result = await specialist.run(
                user_input=state["user_query"],
                context=specialist_context,
            )
            result = validate_specialist_output(result, source)
            circuit_breaker.record_success(source)
            logger.info("[%s] 分析完成, success=%s", source, result.get("success"))

        # ── 失败时生成错误报告 ──
        if not result.get("success", True):
            error_type = result.get("error_type", "unknown")
            error_msg = result.get("error", "未知错误")
            fallback_msg = result.get("fallback", "建议您稍后重试")
            logger.warning("[%s] 分析失败 (type=%s): %s", source, error_type, error_msg)

            markdown_report = _build_error_report(
                source=source,
                error_type=error_type,
                error_msg=error_msg,
                fallback=fallback_msg,
            )
        else:
            # 🆕 text_answer 直接透传，不走专用格式化器
            text_answer = result.get("text_answer") if isinstance(result, dict) else None
            if text_answer:
                markdown_report = str(text_answer)
                logger.debug("[%s] 使用 text_answer，长度: %d", source, len(markdown_report))
            else:
                try:
                    markdown_report = format_success(result)
                    logger.debug("[%s] 使用专用格式化器，长度: %d", source, len(markdown_report))
                except Exception as format_err:
                    logger.warning("[%s] 专用格式化器失败，降级: %s", source, format_err)
                    markdown_report = format_fallback(result)

        # ── 规范化 ──
        specialist_data = payload_formatter.normalize_specialist_result(
            source=source,
            content=markdown_report,
            data=result,
            confidence=result.get("confidence", 0.85),
            success=result.get("success", True),
        )

        # ── 合并到 state（同 source 替换） ──
        existing = state.get("specialist_results", [])
        retry_count = state.get("retry_count", 0)
        if retry_count > 0:
            logger.info("[%s] 重试 #%d 替换结果", source, retry_count)
            existing = [r for r in existing if r.get("source") != source]
        else:
            existing = [r for r in existing if r.get("source") != source]
            logger.debug("[%s] 替换旧结果 | 旧: %d → 新: %d", source, len(existing), len(existing) + 1)

        return {**state, "specialist_results": existing + [specialist_data]}

    except Exception as e:
        circuit_breaker.record_failure(source)
        logger.error("[%s] 执行失败: %s", source, e, exc_info=True)
        return {
            **state,
            "specialist_results": [
                {
                    "source": source,
                    "data": {"error": str(e)},
                    "confidence": 0.0,
                    "success": False,
                }
            ],
        }


def _build_error_report(
    source: str,
    error_type: str,
    error_msg: str,
    fallback: str,
) -> str:
    """根据 source + error_type 查找模板并生成错误报告。"""
    templates = _ERROR_TEMPLATES.get(source, {})
    # 优先用 error_type 精确匹配，否则回退到 "unknown"
    template = templates.get(error_type) or templates.get("unknown", "分析失败: {error_msg}")
    return template.format(error_msg=error_msg, fallback=fallback)
