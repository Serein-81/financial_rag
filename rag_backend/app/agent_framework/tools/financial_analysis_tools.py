"""
财务分析工具集

整合财务指标计算、财务健康分析和风险评估功能
提供全面的企业财务分析能力
"""

import logging
from typing import Dict, Any, Optional, List
from .base import ToolBase

logger = logging.getLogger(__name__)


class FinancialIndicatorTool(ToolBase):
    """
    财务指标计算工具
    
    提供多种财务比率和指标的计算，包括：
    - 资产负债率
    - 流动比率
    - 速动比率
    - 净利润率
    """
    
    def __init__(self):
        super().__init__(
            name="financial_indicator_calculator",
            description="计算企业财务指标，包括资产负债率、流动比率、速动比率、净利润率等",
            timeout=30,
            tags=["财务", "分析", "指标"]
        )
    
    async def execute(
        self,
        indicator_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行财务指标计算
        
        Args:
            indicator_type: 指标类型 (asset_liability_ratio/current_ratio/quick_ratio/profit_margin)
            **kwargs: 根据指标类型传入相应参数
            
        Returns:
            计算结果和风险评估
        """
        try:
            if indicator_type == "asset_liability_ratio":
                return self._calculate_asset_liability_ratio(
                    kwargs.get("total_liabilities", 0),
                    kwargs.get("total_assets", 0),
                    kwargs.get("tenant_id")
                )
            elif indicator_type == "current_ratio":
                return self._calculate_current_ratio(
                    kwargs.get("current_assets", 0),
                    kwargs.get("current_liabilities", 0),
                    kwargs.get("tenant_id")
                )
            elif indicator_type == "quick_ratio":
                return self._calculate_quick_ratio(
                    kwargs.get("current_assets", 0),
                    kwargs.get("inventory", 0),
                    kwargs.get("current_liabilities", 0),
                    kwargs.get("tenant_id")
                )
            elif indicator_type == "profit_margin":
                return self._calculate_net_profit_margin(
                    kwargs.get("net_profit", 0),
                    kwargs.get("revenue", 0),
                    kwargs.get("tenant_id")
                )
            else:
                return {
                    "error": f"不支持的指标类型: {indicator_type}",
                    "supported_types": [
                        "asset_liability_ratio",
                        "current_ratio",
                        "quick_ratio",
                        "profit_margin"
                    ]
                }
        except Exception as e:
            logger.error(f"财务指标计算失败: {str(e)}", exc_info=True)
            return {
                "error": f"财务指标计算失败: {str(e)}",
                "indicator_type": indicator_type
            }
    
    def _calculate_asset_liability_ratio(
        self,
        total_liabilities: float,
        total_assets: float,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算资产负债率"""
        try:
            if total_assets == 0:
                return {
                    "indicator_type": "asset_liability_ratio",
                    "ratio": None,
                    "percentage": None,
                    "analysis": "资产总额为零，无法计算资产负债率",
                    "risk_level": "critical",
                    "tenant_id": tenant_id
                }
            
            ratio = total_liabilities / total_assets
            percentage = ratio * 100
            
            if percentage > 80:
                risk_level = "critical"
                analysis = "资产负债率过高，财务风险极大"
            elif percentage > 70:
                risk_level = "high"
                analysis = "资产负债率较高，需要关注偿债能力"
            elif percentage > 50:
                risk_level = "medium"
                analysis = "资产负债率适中，财务结构基本合理"
            else:
                risk_level = "low"
                analysis = "资产负债率较低，财务结构稳健"
            
            return {
                "indicator_type": "asset_liability_ratio",
                "ratio": round(ratio, 4),
                "percentage": round(percentage, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "一般不超过70%",
                "recommendation": self._get_asset_liability_recommendation(risk_level),
                "tenant_id": tenant_id
            }
        except Exception as e:
            return {
                "indicator_type": "asset_liability_ratio",
                "error": str(e),
                "tenant_id": tenant_id
            }
    
    def _calculate_current_ratio(
        self,
        current_assets: float,
        current_liabilities: float,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算流动比率"""
        try:
            if current_liabilities == 0:
                return {
                    "indicator_type": "current_ratio",
                    "ratio": None,
                    "analysis": "流动负债为零，无法计算流动比率",
                    "risk_level": "unknown",
                    "tenant_id": tenant_id
                }
            
            ratio = current_assets / current_liabilities
            
            if ratio < 1.0:
                risk_level = "high"
                analysis = "流动比率小于1，短期偿债能力不足"
            elif ratio < 1.5:
                risk_level = "medium"
                analysis = "流动比率偏低，需要关注流动性"
            elif ratio > 3.0:
                risk_level = "medium"
                analysis = "流动比率过高，可能存在资金利用效率问题"
            else:
                risk_level = "low"
                analysis = "流动比率合理，短期偿债能力良好"
            
            return {
                "indicator_type": "current_ratio",
                "ratio": round(ratio, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "一般应大于1，理想范围1.5-2.5",
                "recommendation": self._get_current_ratio_recommendation(ratio),
                "tenant_id": tenant_id
            }
        except Exception as e:
            return {
                "indicator_type": "current_ratio",
                "error": str(e),
                "tenant_id": tenant_id
            }
    
    def _calculate_quick_ratio(
        self,
        current_assets: float,
        inventory: float,
        current_liabilities: float,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算速动比率"""
        try:
            if current_liabilities == 0:
                return {
                    "indicator_type": "quick_ratio",
                    "ratio": None,
                    "analysis": "流动负债为零，无法计算速动比率",
                    "risk_level": "unknown",
                    "tenant_id": tenant_id
                }
            
            quick_assets = current_assets - inventory
            ratio = quick_assets / current_liabilities
            
            if ratio < 0.5:
                risk_level = "high"
                analysis = "速动比率过低，即时偿债能力不足"
            elif ratio < 1.0:
                risk_level = "medium"
                analysis = "速动比率偏低，需要关注资金流动性"
            else:
                risk_level = "low"
                analysis = "速动比率良好，即时偿债能力充足"
            
            return {
                "indicator_type": "quick_ratio",
                "ratio": round(ratio, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "一般应大于1",
                "recommendation": self._get_quick_ratio_recommendation(ratio),
                "tenant_id": tenant_id
            }
        except Exception as e:
            return {
                "indicator_type": "quick_ratio",
                "error": str(e),
                "tenant_id": tenant_id
            }
    
    def _calculate_net_profit_margin(
        self,
        net_profit: float,
        revenue: float,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算净利润率"""
        try:
            if revenue == 0:
                return {
                    "indicator_type": "profit_margin",
                    "ratio": None,
                    "percentage": None,
                    "analysis": "营业收入为零，无法计算净利润率",
                    "risk_level": "critical",
                    "tenant_id": tenant_id
                }
            
            ratio = net_profit / revenue
            percentage = ratio * 100
            
            if percentage < 0:
                risk_level = "critical"
                analysis = "净利润率为负，企业亏损"
            elif percentage < 3:
                risk_level = "high"
                analysis = "净利润率较低，盈利能力不足"
            elif percentage < 10:
                risk_level = "medium"
                analysis = "净利润率一般，盈利能力有待提升"
            else:
                risk_level = "low"
                analysis = "净利润率良好，盈利能力较强"
            
            return {
                "indicator_type": "profit_margin",
                "ratio": round(ratio, 4),
                "percentage": round(percentage, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "因行业而异，一般5%-15%",
                "recommendation": self._get_profit_margin_recommendation(percentage),
                "tenant_id": tenant_id
            }
        except Exception as e:
            return {
                "indicator_type": "profit_margin",
                "error": str(e),
                "tenant_id": tenant_id
            }
    
    def _get_asset_liability_recommendation(self, risk_level: str) -> str:
        """获取资产负债率建议"""
        recommendations = {
            "critical": "立即进行债务重组，优化资本结构，降低财务风险",
            "high": "控制债务规模，寻找股权融资机会，改善财务结构",
            "medium": "关注债务期限结构，合理安排偿债计划",
            "low": "财务结构稳健，可适度利用财务杠杆提升收益"
        }
        return recommendations.get(risk_level, "建议定期监控指标变化")
    
    def _get_current_ratio_recommendation(self, ratio: float) -> str:
        """获取流动比率建议"""
        if ratio < 1.0:
            return "增加流动资产储备，加速应收账款回收，优化存货管理"
        elif ratio < 1.5:
            return "适度增加流动资金，合理安排短期债务到期"
        elif ratio > 3.0:
            return "提高资金使用效率，考虑适度投资或偿还债务"
        else:
            return "保持当前资金管理策略，定期监控流动性变化"
    
    def _get_quick_ratio_recommendation(self, ratio: float) -> str:
        """获取速动比率建议"""
        if ratio < 0.5:
            return "加快存货周转，提高速动资产比例，增强即时偿债能力"
        elif ratio < 1.0:
            return "优化存货结构，加速资金周转，提升流动性"
        else:
            return "保持良好的速动资产结构，确保即时偿债能力"
    
    def _get_profit_margin_recommendation(self, percentage: float) -> str:
        """获取净利润率建议"""
        if percentage < 0:
            return "分析亏损原因，制定扭亏为盈计划，控制成本费用"
        elif percentage < 3:
            return "提升产品竞争力，扩大市场份额，降低运营成本"
        elif percentage < 10:
            return "优化产品结构，提高附加值，加强成本控制"
        else:
            return "保持竞争优势，持续提升盈利能力，关注长期发展"


class FinancialHealthAnalyzer(ToolBase):
    """
    财务健康综合分析工具
    
    提供企业财务健康状况的综合评估
    """
    
    def __init__(self):
        super().__init__(
            name="financial_health_analyzer",
            description="综合分析企业财务健康状况，评估财务风险和盈利能力",
            timeout=30,
            tags=["财务", "分析", "健康", "风险"]
        )
    
    async def execute(
        self,
        financial_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        执行财务健康分析
        
        Args:
            financial_data: 财务数据字典
            tenant_id: 租户ID
            
        Returns:
            财务健康分析结果
        """
        try:
            indicator_tool = FinancialIndicatorTool()
            analysis_results = []
            overall_score = 0
            total_indicators = 0
            
            if financial_data.get("total_assets") and financial_data.get("total_liabilities"):
                result = indicator_tool._calculate_asset_liability_ratio(
                    financial_data["total_liabilities"],
                    financial_data["total_assets"],
                    tenant_id
                )
                analysis_results.append({
                    "indicator": "资产负债率",
                    "value": result.get("percentage"),
                    "analysis": result.get("analysis"),
                    "risk_level": result.get("risk_level")
                })
                overall_score += self._risk_level_to_score(result.get("risk_level", "unknown"))
                total_indicators += 1
            
            if financial_data.get("current_assets") and financial_data.get("current_liabilities"):
                result = indicator_tool._calculate_current_ratio(
                    financial_data["current_assets"],
                    financial_data["current_liabilities"],
                    tenant_id
                )
                analysis_results.append({
                    "indicator": "流动比率",
                    "value": result.get("ratio"),
                    "analysis": result.get("analysis"),
                    "risk_level": result.get("risk_level")
                })
                overall_score += self._risk_level_to_score(result.get("risk_level", "unknown"))
                total_indicators += 1
            
            if financial_data.get("net_profit") and financial_data.get("revenue"):
                result = indicator_tool._calculate_net_profit_margin(
                    financial_data["net_profit"],
                    financial_data["revenue"],
                    tenant_id
                )
                analysis_results.append({
                    "indicator": "净利润率",
                    "value": result.get("percentage"),
                    "analysis": result.get("analysis"),
                    "risk_level": result.get("risk_level")
                })
                overall_score += self._risk_level_to_score(result.get("risk_level", "unknown"))
                total_indicators += 1
            
            if total_indicators > 0:
                final_score = (overall_score / total_indicators) * 25
                health_level, health_description = self._get_health_level(final_score)
            else:
                final_score = 0
                health_level = "无法评估"
                health_description = "缺少必要的财务数据，无法进行评估"
            
            return {
                "tenant_id": tenant_id,
                "overall_score": round(final_score, 1),
                "health_level": health_level,
                "health_description": health_description,
                "detailed_analysis": analysis_results,
                "total_indicators": total_indicators,
                "recommendations": self._generate_recommendations(analysis_results)
            }
        except Exception as e:
            logger.error(f"财务健康分析失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "overall_score": 0,
                "health_level": "评估失败",
                "health_description": f"财务健康分析失败: {str(e)}",
                "detailed_analysis": [],
                "total_indicators": 0
            }
    
    def _risk_level_to_score(self, risk_level: str) -> int:
        """将风险等级转换为分数"""
        scores = {
            "low": 4,
            "medium": 3,
            "high": 2,
            "critical": 1,
            "unknown": 2
        }
        return scores.get(risk_level, 2)
    
    def _get_health_level(self, score: float) -> tuple:
        """根据分数确定健康等级"""
        if score >= 80:
            return "优秀", "财务状况良好，各项指标表现优秀"
        elif score >= 60:
            return "良好", "财务状况基本良好，部分指标需要关注"
        elif score >= 40:
            return "一般", "财务状况一般，存在一定风险"
        else:
            return "较差", "财务状况较差，存在较大风险"
    
    def _generate_recommendations(self, analysis_results: List[Dict[str, Any]]) -> List[str]:
        """生成建议列表"""
        recommendations = []
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        
        for result in analysis_results:
            risk_level = result.get("risk_level", "unknown")
            if risk_level in risk_counts:
                risk_counts[risk_level] += 1
        
        if risk_counts["critical"] > 0:
            recommendations.append("存在严重财务风险，建议立即采取改善措施")
        if risk_counts["high"] > 0:
            recommendations.append("存在较高财务风险，需要重点关注和改善")
        if risk_counts["medium"] > 0:
            recommendations.append("部分财务指标需要优化，建议持续监控")
        if all(v == 0 for v in risk_counts.values()):
            recommendations.append("财务状况良好，建议继续保持")
        
        return recommendations
