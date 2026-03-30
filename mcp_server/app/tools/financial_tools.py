"""
财务分析工具
"""

import logging
from typing import Any, Dict, Optional

from app.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)


class AssetLiabilityRatioTool(ToolBase):
    """资产负债率计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_asset_liability_ratio",
            description="计算资产负债率（Asset-Liability Ratio）。衡量企业总资产中负债的比例。",
            timeout=30
        )

    async def execute(
        self,
        total_liabilities: float,
        total_assets: float,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算资产负债率

        Args:
            total_liabilities: 负债总额
            total_assets: 资产总额
            tenant_id: 租户ID

        Returns:
            包含计算结果的字典
        """
        if total_assets <= 0:
            return {
                "success": False,
                "error": "资产总额必须大于0",
                "total_assets": total_assets,
                "total_liabilities": total_liabilities,
                "tenant_id": tenant_id
            }

        ratio = (total_liabilities / total_assets) * 100
        equity = total_assets - total_liabilities
        equity_ratio = 100 - ratio

        risk_level = self._assess_risk(ratio)

        return {
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "equity": round(equity, 2),
            "asset_liability_ratio": round(ratio, 2),
            "equity_ratio": round(equity_ratio, 2),
            "risk_level": risk_level,
            "benchmark": {
                "excellent": "< 40%",
                "good": "40% - 60%",
                "warning": "60% - 70%",
                "danger": "> 70%"
            },
            "tenant_id": tenant_id
        }

    def _assess_risk(self, ratio: float) -> str:
        """评估风险等级"""
        if ratio < 40:
            return "low"
        elif ratio < 60:
            return "medium"
        elif ratio < 70:
            return "high"
        return "critical"


class CurrentRatioTool(ToolBase):
    """流动比率计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_current_ratio",
            description="计算流动比率（Current Ratio）。衡量企业短期偿债能力。",
            timeout=30
        )

    async def execute(
        self,
        current_assets: float,
        current_liabilities: float,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算流动比率

        Args:
            current_assets: 流动资产
            current_liabilities: 流动负债
            tenant_id: 租户ID

        Returns:
            包含计算结果的字典
        """
        if current_liabilities <= 0:
            return {
                "success": False,
                "error": "流动负债必须大于0",
                "current_assets": current_assets,
                "current_liabilities": current_liabilities,
                "tenant_id": tenant_id
            }

        ratio = current_assets / current_liabilities

        risk_level = self._assess_risk(ratio)

        return {
            "current_assets": round(current_assets, 2),
            "current_liabilities": round(current_liabilities, 2),
            "current_ratio": round(ratio, 2),
            "risk_level": risk_level,
            "benchmark": {
                "excellent": "> 2.0",
                "good": "1.5 - 2.0",
                "warning": "1.0 - 1.5",
                "danger": "< 1.0"
            },
            "tenant_id": tenant_id
        }

    def _assess_risk(self, ratio: float) -> str:
        """评估风险等级"""
        if ratio >= 2.0:
            return "low"
        elif ratio >= 1.5:
            return "medium"
        elif ratio >= 1.0:
            return "high"
        return "critical"


class QuickRatioTool(ToolBase):
    """速动比率计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_quick_ratio",
            description="计算速动比率（Quick Ratio）。衡量企业立即偿债能力。",
            timeout=30
        )

    async def execute(
        self,
        current_assets: float,
        inventory: float,
        current_liabilities: float,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算速动比率

        Args:
            current_assets: 流动资产
            inventory: 存货
            current_liabilities: 流动负债
            tenant_id: 租户ID

        Returns:
            包含计算结果的字典
        """
        if current_liabilities <= 0:
            return {
                "success": False,
                "error": "流动负债必须大于0",
                "current_assets": current_assets,
                "inventory": inventory,
                "current_liabilities": current_liabilities,
                "tenant_id": tenant_id
            }

        quick_assets = current_assets - inventory
        ratio = quick_assets / current_liabilities

        risk_level = self._assess_risk(ratio)

        return {
            "current_assets": round(current_assets, 2),
            "inventory": round(inventory, 2),
            "quick_assets": round(quick_assets, 2),
            "current_liabilities": round(current_liabilities, 2),
            "quick_ratio": round(ratio, 2),
            "risk_level": risk_level,
            "benchmark": {
                "excellent": "> 1.0",
                "good": "0.8 - 1.0",
                "warning": "0.5 - 0.8",
                "danger": "< 0.5"
            },
            "tenant_id": tenant_id
        }

    def _assess_risk(self, ratio: float) -> str:
        """评估风险等级"""
        if ratio >= 1.0:
            return "low"
        elif ratio >= 0.8:
            return "medium"
        elif ratio >= 0.5:
            return "high"
        return "critical"


class NetProfitMarginTool(ToolBase):
    """净利润率计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_profit_margin",
            description="计算净利润率（Net Profit Margin）。衡量企业盈利能力。",
            timeout=30
        )

    async def execute(
        self,
        net_profit: float,
        revenue: float,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算净利润率

        Args:
            net_profit: 净利润
            revenue: 营业收入
            tenant_id: 租户ID

        Returns:
            包含计算结果的字典
        """
        if revenue <= 0:
            return {
                "success": False,
                "error": "营业收入必须大于0",
                "net_profit": net_profit,
                "revenue": revenue,
                "tenant_id": tenant_id
            }

        margin = (net_profit / revenue) * 100

        risk_level = self._assess_risk(margin)

        return {
            "net_profit": round(net_profit, 2),
            "revenue": round(revenue, 2),
            "net_profit_margin": round(margin, 2),
            "profit_per_yuan": round(net_profit / revenue, 4),
            "risk_level": risk_level,
            "benchmark": {
                "excellent": "> 20%",
                "good": "10% - 20%",
                "average": "5% - 10%",
                "warning": "0% - 5%",
                "loss": "< 0%"
            },
            "tenant_id": tenant_id
        }

    def _assess_risk(self, margin: float) -> str:
        """评估风险等级"""
        if margin >= 20:
            return "low"
        elif margin >= 10:
            return "medium"
        elif margin >= 5:
            return "high"
        return "critical"


def register_financial_tools():
    """注册所有财务工具"""
    registry.register(AssetLiabilityRatioTool())
    registry.register(CurrentRatioTool())
    registry.register(QuickRatioTool())
    registry.register(NetProfitMarginTool())


financial_tools = [
    AssetLiabilityRatioTool(),
    CurrentRatioTool(),
    QuickRatioTool(),
    NetProfitMarginTool()
]
