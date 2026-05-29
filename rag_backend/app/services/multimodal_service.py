"""
多模态解析服务

根据用户配置动态选择解析器和模式。
"""

import logging
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models.user_multimodal_config import (
    UserMultiModalConfig,
    UserMultiModalUsageLog
)
from app.models.multimodal_chunk import (
    TableData,
    ChartData,
    ImageData,
    MultiModalChunk,
    create_table_chunk,
    create_chart_chunk,
    create_image_chunk
)
from app.parsers.table_parser import TableParser
from app.parsers.chart_parser import ChartParser

logger = logging.getLogger(__name__)


class MultiModalService:
    """
    多模态解析服务

    根据用户配置动态选择解析模式，并记录使用情况。
    """

    def __init__(self, db: AsyncSession, tenant_id: str):
        """
        初始化服务

        注意：异步加载配置需调用 `await get_multimodal_service(...)` 工厂函数，
        或在使用前先 `await service._load_config()`。

        Args:
            db: 数据库会话（AsyncSession）
            tenant_id: 租户ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.config: Optional[UserMultiModalConfig] = None

    async def _load_config(self) -> UserMultiModalConfig:
        """
        加载用户配置

        如果用户没有配置，返回默认配置。
        """
        result = await self.db.execute(
            select(UserMultiModalConfig).where(
                UserMultiModalConfig.tenant_id == self.tenant_id
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            # 创建默认配置
            config = UserMultiModalConfig(
                tenant_id=self.tenant_id,
                enabled=True,
                table_mode="rule_based",
                chart_mode="rule_based",
                image_mode="basic",
                vision_model="gpt-4o",
                llm_model="gpt-4o-mini",
                daily_ai_limit=100
            )
            # 不保存到数据库，仅作为临时默认配置

        # 检查是否需要重置每日计数
        if config.last_reset_at:
            now = datetime.now()
            if (now - config.last_reset_at).days >= 1:
                config.reset_daily_usage()
                await self.db.commit()

        self.config = config
        return config

    async def _ensure_config(self) -> UserMultiModalConfig:
        """确保配置已加载（懒加载兜底）"""
        if self.config is None:
            await self._load_config()
        return self.config

    async def parse_table(
        self,
        table_data: List[List[str]],
        caption: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> TableData:
        """
        解析表格

        根据用户配置选择解析模式。

        Args:
            table_data: 表格数据（二维列表）
            caption: 表格标题
            document_id: 文档ID（用于日志）

        Returns:
            TableData: 表格结构化数据
        """
        await self._ensure_config()
        if not self.config.enabled:
            # 如果禁用，使用basic模式
            mode = "basic"
        else:
            mode = self.config.table_mode

        # 检查AI限额
        if mode == "ai_enhanced" and not self.config.can_use_ai():
            logger.warning(f"租户 {self.tenant_id} 已达AI使用限额，降级到rule_based模式")
            mode = "rule_based"

        # 创建解析器
        llm_service = None
        if mode == "ai_enhanced":
            llm_service = self._get_llm_service()

        parser = TableParser(mode=mode, llm_service=llm_service)

        # 记录开始时间
        import time
        start_time = time.time()

        try:
            # 解析表格
            result = await parser.parse_table(table_data, caption)

            # 记录成功
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._log_usage(
                content_type="table",
                parse_mode=mode,
                model_used=self.config.llm_model if mode == "ai_enhanced" else None,
                response_time_ms=response_time_ms,
                success=True,
                document_id=document_id
            )

            # 增加使用计数
            if mode == "ai_enhanced":
                self.config.increment_ai_usage()
                await self.db.commit()

            return result

        except Exception as e:
            # 记录失败
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._log_usage(
                content_type="table",
                parse_mode=mode,
                model_used=self.config.llm_model if mode == "ai_enhanced" else None,
                response_time_ms=response_time_ms,
                success=False,
                error_message=str(e),
                document_id=document_id
            )
            raise

    async def parse_chart(
        self,
        image_bytes: bytes,
        title: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> ChartData:
        """
        解析图表

        根据用户配置选择解析模式。

        Args:
            image_bytes: 图表图片字节流
            title: 图表标题
            document_id: 文档ID（用于日志）

        Returns:
            ChartData: 图表结构化数据
        """
        await self._ensure_config()
        if not self.config.enabled:
            mode = "basic"
        else:
            mode = self.config.chart_mode

        # 检查AI限额
        if mode == "ai_enhanced" and not self.config.can_use_ai():
            logger.warning(f"租户 {self.tenant_id} 已达AI使用限额，降级到rule_based模式")
            mode = "rule_based"

        # 创建解析器
        vision_service = None
        ocr_service = None
        if mode == "ai_enhanced":
            vision_service = self._get_vision_service()
            ocr_service = self._get_ocr_service()

        parser = ChartParser(
            mode=mode,
            vision_service=vision_service,
            ocr_service=ocr_service
        )

        # 记录开始时间
        import time
        start_time = time.time()

        try:
            # 解析图表
            result = await parser.parse_chart(image_bytes, title)

            # 记录成功
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._log_usage(
                content_type="chart",
                parse_mode=mode,
                model_used=self.config.vision_model if mode == "ai_enhanced" else None,
                response_time_ms=response_time_ms,
                success=True,
                document_id=document_id
            )

            # 增加使用计数
            if mode == "ai_enhanced":
                self.config.increment_ai_usage()
                await self.db.commit()

            return result

        except Exception as e:
            # 记录失败
            response_time_ms = int((time.time() - start_time) * 1000)
            await self._log_usage(
                content_type="chart",
                parse_mode=mode,
                model_used=self.config.vision_model if mode == "ai_enhanced" else None,
                response_time_ms=response_time_ms,
                success=False,
                error_message=str(e),
                document_id=document_id
            )
            raise

    def _get_llm_service(self):
        """获取LLM服务实例"""
        # TODO: 根据配置的模型和API Key创建LLM服务
        # 如果用户提供了自己的API Key，使用用户的
        # 否则使用系统配置的
        from app.services.llm_service import llm_service
        return llm_service

    def _get_vision_service(self):
        """获取Vision服务实例"""
        # TODO: 根据配置的模型和API Key创建Vision服务
        from app.services.vision_service import vision_service
        return vision_service

    def _get_ocr_service(self):
        """获取OCR服务实例"""
        from app.services.ocr_service import ocr_service
        return ocr_service

    async def _log_usage(
        self,
        content_type: str,
        parse_mode: str,
        model_used: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        response_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        document_id: Optional[str] = None
    ):
        """
        记录使用日志

        Args:
            content_type: 内容类型 (table/chart/image)
            parse_mode: 解析模式
            model_used: 使用的模型
            input_tokens: 输入token数
            output_tokens: 输出token数
            response_time_ms: 响应时间（毫秒）
            success: 是否成功
            error_message: 错误信息
            document_id: 文档ID
        """
        total_tokens = input_tokens + output_tokens

        # 估算成本
        estimated_cost = None
        if parse_mode == "ai_enhanced" and total_tokens > 0:
            # 简化的成本估算（实际应根据模型定价）
            cost_per_1m_tokens = 0.15 if "mini" in (model_used or "") else 2.5
            estimated_cost = f"${(total_tokens / 1_000_000 * cost_per_1m_tokens):.6f}"

        log = UserMultiModalUsageLog(
            tenant_id=self.tenant_id,
            document_id=document_id,
            content_type=content_type,
            parse_mode=parse_mode,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message
        )

        self.db.add(log)
        await self.db.commit()

    def get_config(self) -> dict:
        """获取当前配置"""
        return self.config.to_dict()

    def is_enabled(self) -> bool:
        """多模态功能是否启用"""
        return self.config.enabled

    def can_use_ai(self) -> bool:
        """是否可以使用AI"""
        return self.config.can_use_ai()


# 便捷函数

async def get_multimodal_service(db: AsyncSession, tenant_id: str) -> MultiModalService:
    """
    获取多模态服务实例（已加载配置）

    Args:
        db: 数据库会话（AsyncSession）
        tenant_id: 租户ID

    Returns:
        MultiModalService: 服务实例
    """
    service = MultiModalService(db=db, tenant_id=tenant_id)
    await service._load_config()
    return service
