"""
用户多模态配置模型

每个租户可以自定义多模态功能的配置，包括是否启用AI增强、选择哪个模型等。
"""

import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class UserMultiModalConfig(Base):
    """
    用户多模态配置表

    每个租户可以自定义：
    - 是否启用多模态功能
    - 每个内容类型（表格/图表/图片）的解析模式
    - 使用哪个AI模型
    - 成本控制（每日限额等）
    """
    __tablename__ = "user_multimodal_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 租户ID（多租户隔离）
    tenant_id = Column(String(50), nullable=False, index=True)

    # ========== 功能开关 ==========
    enabled = Column(Boolean, default=True, nullable=False)  # 是否启用多模态

    # ========== 解析模式配置 ==========
    # basic: 仅基础提取（免费）
    # rule_based: 基础 + 规则分析（免费，推荐）
    # ai_enhanced: 基础 + 规则 + AI增强（付费）

    table_mode = Column(String(20), default="rule_based", nullable=False)  # 表格解析模式
    chart_mode = Column(String(20), default="rule_based", nullable=False)  # 图表解析模式
    image_mode = Column(String(20), default="basic", nullable=False)       # 图片解析模式

    # ========== AI模型配置 ==========
    # 用户可选择自己有额度的模型
    vision_model = Column(String(50), default="gpt-4o", nullable=True)     # Vision模型
    llm_model = Column(String(50), default="gpt-4o-mini", nullable=True)   # LLM模型

    # 用户API密钥（加密存储，可选）
    # 如果用户提供自己的API Key，则使用用户的额度
    # 否则使用系统配置的API Key
    user_api_key_encrypted = Column(String(500), nullable=True)
    use_own_api_key = Column(Boolean, default=False, nullable=False)

    # ========== 成本控制 ==========
    # 每日AI调用次数限制（0表示不限制）
    daily_ai_limit = Column(Integer, default=100, nullable=False)

    # 当前已使用次数（每日重置）
    daily_ai_used = Column(Integer, default=0, nullable=False)

    # 上次重置时间
    last_reset_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # 总AI调用次数（统计）
    total_ai_calls = Column(Integer, default=0, nullable=False)

    # ========== 性能配置 ==========
    enable_cache = Column(Boolean, default=True, nullable=False)           # 是否缓存AI结果
    ai_timeout = Column(Integer, default=30, nullable=False)               # AI超时时间（秒）
    max_concurrent = Column(Integer, default=3, nullable=False)            # 最大并发数

    # ========== 高级配置 ==========
    # 自定义配置（JSON格式）
    # 例如：{"table_summary_length": "short", "chart_detail_level": "high"}
    custom_config = Column(JSONB, default={}, nullable=False)

    # ========== 审计字段 ==========
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # 唯一约束：每个租户只能有一个配置
    __table_args__ = (
        UniqueConstraint('tenant_id', name='uq_tenant_multimodal_config'),
    )

    def to_dict(self):
        """转换为字典"""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "enabled": self.enabled,
            "modes": {
                "table": self.table_mode,
                "chart": self.chart_mode,
                "image": self.image_mode
            },
            "models": {
                "vision": self.vision_model,
                "llm": self.llm_model
            },
            "use_own_api_key": self.use_own_api_key,
            "cost_control": {
                "daily_limit": self.daily_ai_limit,
                "daily_used": self.daily_ai_used,
                "total_calls": self.total_ai_calls
            },
            "performance": {
                "enable_cache": self.enable_cache,
                "ai_timeout": self.ai_timeout,
                "max_concurrent": self.max_concurrent
            },
            "custom_config": self.custom_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def is_table_ai_enabled(self) -> bool:
        """表格是否启用AI增强"""
        return self.enabled and self.table_mode == "ai_enhanced"

    def is_chart_ai_enabled(self) -> bool:
        """图表是否启用AI增强"""
        return self.enabled and self.chart_mode == "ai_enhanced"

    def is_image_ai_enabled(self) -> bool:
        """图片是否启用AI增强"""
        return self.enabled and self.image_mode == "ai_enhanced"

    def can_use_ai(self) -> bool:
        """
        是否可以使用AI（检查限额）

        Returns:
            bool: True表示可以使用，False表示已达限额
        """
        if self.daily_ai_limit == 0:
            return True  # 无限制

        return self.daily_ai_used < self.daily_ai_limit

    def increment_ai_usage(self):
        """增加AI使用次数"""
        self.daily_ai_used += 1
        self.total_ai_calls += 1

    def reset_daily_usage(self):
        """重置每日使用次数"""
        from datetime import datetime
        self.daily_ai_used = 0
        self.last_reset_at = datetime.now()

    def get_cost_estimate(self) -> dict:
        """
        估算使用成本

        Returns:
            dict: 成本估算信息
        """
        # 每种模式每1000个对象的成本（美元）
        cost_per_1k = {
            "basic": 0,
            "rule_based": 0,
            "ai_enhanced": {
                "table": 0.50,   # GPT-4o-mini
                "chart": 2.00,   # GPT-4o vision
                "image": 2.00    # GPT-4o vision
            }
        }

        total_cost = 0
        details = {}

        if self.table_mode == "ai_enhanced":
            total_cost += cost_per_1k["ai_enhanced"]["table"]
            details["table"] = f"${cost_per_1k['ai_enhanced']['table']:.2f}/1K"
        else:
            details["table"] = "基础"

        if self.chart_mode == "ai_enhanced":
            total_cost += cost_per_1k["ai_enhanced"]["chart"]
            details["chart"] = f"${cost_per_1k['ai_enhanced']['chart']:.2f}/1K"
        else:
            details["chart"] = "基础"

        if self.image_mode == "ai_enhanced":
            total_cost += cost_per_1k["ai_enhanced"]["image"]
            details["image"] = f"${cost_per_1k['ai_enhanced']['image']:.2f}/1K"
        else:
            details["image"] = "基础"

        return {
            "modes": {
                "table": self.table_mode,
                "chart": self.chart_mode,
                "image": self.image_mode
            },
            "cost_per_1k_objects": details,
            "total_cost_per_1k_docs": f"${total_cost:.2f}",
            "note": "基于平均每个文档5个表格、2个图表、3张图片估算"
        }


class UserMultiModalUsageLog(Base):
    """
    用户多模态使用日志

    记录每次AI调用的详细信息，用于统计和审计。
    """
    __tablename__ = "user_multimodal_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 租户ID
    tenant_id = Column(String(50), nullable=False, index=True)

    # 用户ID（可选）
    user_id = Column(UUID(as_uuid=True), nullable=True)

    # 文档ID
    document_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # 内容类型
    content_type = Column(String(20), nullable=False)  # table / chart / image

    # 解析模式
    parse_mode = Column(String(20), nullable=False)  # basic / rule_based / ai_enhanced

    # 使用的模型
    model_used = Column(String(50), nullable=True)

    # Token使用量
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # 成本（美元）
    estimated_cost = Column(String(20), nullable=True)

    # 响应时间（毫秒）
    response_time_ms = Column(Integer, nullable=True)

    # 是否成功
    success = Column(Boolean, default=True)

    # 错误信息
    error_message = Column(String(500), nullable=True)

    # 创建时间
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)

    def to_dict(self):
        """转换为字典"""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "user_id": str(self.user_id) if self.user_id else None,
            "document_id": str(self.document_id) if self.document_id else None,
            "content_type": self.content_type,
            "parse_mode": self.parse_mode,
            "model_used": self.model_used,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
