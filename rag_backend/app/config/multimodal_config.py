"""
多模态理解配置

用户可以通过环境变量或配置文件控制多模态功能的行为。
"""

import os
from typing import Optional
from enum import Enum


class ParserMode(str, Enum):
    """解析器模式"""
    BASIC = "basic"              # 仅基础提取（免费）
    RULE_BASED = "rule_based"    # 基础 + 规则分析（免费）
    AI_ENHANCED = "ai_enhanced"  # 基础 + 规则 + AI增强（需要模型）


class MultiModalConfig:
    """
    多模态理解配置

    三种模式：
    1. basic - 仅提取结构化数据和OCR文字（免费，速度快）
    2. rule_based - 基础 + 规则分析（免费，推荐，默认）
    3. ai_enhanced - 基础 + 规则 + AI分析（需要GPT-4V/Claude等，成本高）

    环境变量配置：
    - MULTIMODAL_ENABLED: 是否启用多模态功能（true/false）
    - MULTIMODAL_TABLE_MODE: 表格解析模式（basic/rule_based/ai_enhanced）
    - MULTIMODAL_CHART_MODE: 图表解析模式（basic/rule_based/ai_enhanced）
    - MULTIMODAL_IMAGE_MODE: 图片解析模式（basic/rule_based/ai_enhanced）
    - MULTIMODAL_VISION_MODEL: Vision模型（gpt-4v/claude-3.5-sonnet/gemini-1.5-pro）
    - MULTIMODAL_LLM_MODEL: LLM模型（用于表格摘要生成）
    """

    def __init__(self):
        # ========== 总开关 ==========
        self.enabled = os.getenv("MULTIMODAL_ENABLED", "true").lower() == "true"

        # ========== 解析模式 ==========
        # 表格解析模式
        self.table_mode = ParserMode(
            os.getenv("MULTIMODAL_TABLE_MODE", "rule_based")
        )

        # 图表解析模式
        self.chart_mode = ParserMode(
            os.getenv("MULTIMODAL_CHART_MODE", "rule_based")
        )

        # 图片解析模式
        self.image_mode = ParserMode(
            os.getenv("MULTIMODAL_IMAGE_MODE", "basic")
        )

        # ========== AI模型配置 ==========
        # Vision模型（用于图表和图片理解）
        self.vision_model = os.getenv(
            "MULTIMODAL_VISION_MODEL",
            "gpt-4o"  # 默认使用GPT-4o（比4V便宜）
        )

        # LLM模型（用于表格摘要生成）
        self.llm_model = os.getenv(
            "MULTIMODAL_LLM_MODEL",
            "gpt-4o-mini"  # 默认使用mini版本（便宜）
        )

        # ========== OCR配置 ==========
        # OCR引擎：tesseract（本地，免费）/ paddleocr（本地，免费）/ api（第三方）
        self.ocr_engine = os.getenv("MULTIMODAL_OCR_ENGINE", "tesseract")

        # ========== 性能配置 ==========
        # 是否缓存AI分析结果
        self.enable_cache = os.getenv("MULTIMODAL_ENABLE_CACHE", "true").lower() == "true"

        # AI分析超时时间（秒）
        self.ai_timeout = int(os.getenv("MULTIMODAL_AI_TIMEOUT", "30"))

        # 并发处理数量
        self.max_concurrent = int(os.getenv("MULTIMODAL_MAX_CONCURRENT", "3"))

        # ========== 成本控制 ==========
        # AI增强模式的最大token数
        self.max_tokens = int(os.getenv("MULTIMODAL_MAX_TOKENS", "500"))

        # 每天AI调用次数限制（0表示不限制）
        self.daily_ai_limit = int(os.getenv("MULTIMODAL_DAILY_AI_LIMIT", "0"))

    def is_table_ai_enabled(self) -> bool:
        """表格是否启用AI增强"""
        return self.enabled and self.table_mode == ParserMode.AI_ENHANCED

    def is_chart_ai_enabled(self) -> bool:
        """图表是否启用AI增强"""
        return self.enabled and self.chart_mode == ParserMode.AI_ENHANCED

    def is_image_ai_enabled(self) -> bool:
        """图片是否启用AI增强"""
        return self.enabled and self.image_mode == ParserMode.AI_ENHANCED

    def is_any_ai_enabled(self) -> bool:
        """是否有任何AI增强功能启用"""
        return (
            self.is_table_ai_enabled() or
            self.is_chart_ai_enabled() or
            self.is_image_ai_enabled()
        )

    def get_cost_estimate(self) -> dict:
        """
        估算使用成本（参考）

        返回每1000个文档的大致成本（美元）
        """
        costs = {
            "basic": {
                "table": 0,
                "chart": 0,
                "image": 0,
                "total": 0
            },
            "rule_based": {
                "table": 0,
                "chart": 0,
                "image": 0,
                "total": 0
            },
            "ai_enhanced": {
                "table": 0.50,    # GPT-4o-mini: ~$0.15/1M tokens
                "chart": 2.00,    # GPT-4o: vision ~$2.5/1M tokens
                "image": 2.00,    # 同上
                "total": 4.50
            }
        }

        current_cost = 0
        if self.table_mode == ParserMode.AI_ENHANCED:
            current_cost += costs["ai_enhanced"]["table"]
        if self.chart_mode == ParserMode.AI_ENHANCED:
            current_cost += costs["ai_enhanced"]["chart"]
        if self.image_mode == ParserMode.AI_ENHANCED:
            current_cost += costs["ai_enhanced"]["image"]

        return {
            "mode": {
                "table": self.table_mode.value,
                "chart": self.chart_mode.value,
                "image": self.image_mode.value
            },
            "estimated_cost_per_1k_docs": f"${current_cost:.2f}",
            "reference": "基于平均每个文档5个表格/2个图表/3张图片"
        }

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "modes": {
                "table": self.table_mode.value,
                "chart": self.chart_mode.value,
                "image": self.image_mode.value
            },
            "models": {
                "vision": self.vision_model,
                "llm": self.llm_model
            },
            "ocr_engine": self.ocr_engine,
            "performance": {
                "enable_cache": self.enable_cache,
                "ai_timeout": self.ai_timeout,
                "max_concurrent": self.max_concurrent
            },
            "cost_control": {
                "max_tokens": self.max_tokens,
                "daily_ai_limit": self.daily_ai_limit
            },
            "cost_estimate": self.get_cost_estimate()
        }


# 全局配置实例
multimodal_config = MultiModalConfig()


# 便捷函数

def get_multimodal_config() -> MultiModalConfig:
    """获取多模态配置"""
    return multimodal_config


def is_multimodal_enabled() -> bool:
    """多模态功能是否启用"""
    return multimodal_config.enabled


def get_table_parser_mode() -> ParserMode:
    """获取表格解析模式"""
    return multimodal_config.table_mode


def get_chart_parser_mode() -> ParserMode:
    """获取图表解析模式"""
    return multimodal_config.chart_mode


def get_image_parser_mode() -> ParserMode:
    """获取图片解析模式"""
    return multimodal_config.image_mode


# 配置示例

"""
# .env 文件配置示例

# ========== 推荐配置：免费模式（默认）==========
MULTIMODAL_ENABLED=true
MULTIMODAL_TABLE_MODE=rule_based    # 规则分析，无需模型
MULTIMODAL_CHART_MODE=rule_based    # 规则分析，无需模型
MULTIMODAL_IMAGE_MODE=basic         # 仅OCR，无需模型

# ========== 高级配置：AI增强模式 ==========
# 注意：需要GPT-4V/Claude 3.5等模型，成本较高
# MULTIMODAL_ENABLED=true
# MULTIMODAL_TABLE_MODE=ai_enhanced
# MULTIMODAL_CHART_MODE=ai_enhanced
# MULTIMODAL_IMAGE_MODE=ai_enhanced
# MULTIMODAL_VISION_MODEL=gpt-4o           # 或 claude-3.5-sonnet
# MULTIMODAL_LLM_MODEL=gpt-4o-mini
# MULTIMODAL_MAX_TOKENS=500
# MULTIMODAL_DAILY_AI_LIMIT=1000           # 每天最多1000次AI调用

# ========== 禁用多模态功能 ==========
# MULTIMODAL_ENABLED=false
"""
