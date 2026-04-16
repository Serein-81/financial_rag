"""
财务计算工具
提供财务指标计算和分析功能
"""

from typing import Dict, Any, Optional, List
import re
from decimal import InvalidOperation


class FinancialCalculator:
    """财务计算工具"""
    
    def __init__(self):
        self.name = "financial_calculator"
        self.description = "计算财务指标和进行财务分析"
    
    def calculate_asset_liability_ratio(
        self,
        total_liabilities: float,
        total_assets: float
    ) -> Dict[str, Any]:
        """
        计算资产负债率
        
        Args:
            total_liabilities: 负债总额
            total_assets: 资产总额
            
        Returns:
            计算结果和分析
        """
        try:
            if total_assets == 0:
                return {
                    "ratio": None,
                    "percentage": None,
                    "analysis": "资产总额为零，无法计算资产负债率",
                    "risk_level": "critical"
                }
            
            ratio = total_liabilities / total_assets
            percentage = ratio * 100
            
            # 风险评估
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
                "ratio": round(ratio, 4),
                "percentage": round(percentage, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "一般不超过70%"
            }
            
        except Exception as e:
            return {
                "ratio": None,
                "percentage": None,
                "analysis": f"计算失败: {str(e)}",
                "risk_level": "unknown"
            }
    
    def calculate_current_ratio(
        self,
        current_assets: float,
        current_liabilities: float
    ) -> Dict[str, Any]:
        """
        计算流动比率
        
        Args:
            current_assets: 流动资产
            current_liabilities: 流动负债
            
        Returns:
            计算结果和分析
        """
        try:
            if current_liabilities == 0:
                return {
                    "ratio": None,
                    "analysis": "流动负债为零，无法计算流动比率",
                    "risk_level": "unknown"
                }
            
            ratio = current_assets / current_liabilities
            
            # 风险评估
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
                "ratio": round(ratio, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "一般应大于1，理想范围1.5-2.5"
            }
            
        except Exception as e:
            return {
                "ratio": None,
                "analysis": f"计算失败: {str(e)}",
                "risk_level": "unknown"
            }
    
    def calculate_quick_ratio(
        self,
        current_assets: float,
        inventory: float,
        current_liabilities: float
    ) -> Dict[str, Any]:
        """
        计算速动比率
        
        Args:
            current_assets: 流动资产
            inventory: 存货
            current_liabilities: 流动负债
            
        Returns:
            计算结果和分析
        """
        try:
            if current_liabilities == 0:
                return {
                    "ratio": None,
                    "analysis": "流动负债为零，无法计算速动比率",
                    "risk_level": "unknown"
                }
            
            quick_assets = current_assets - inventory
            ratio = quick_assets / current_liabilities
            
            # 风险评估
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
                "ratio": round(ratio, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "一般应大于1"
            }
            
        except Exception as e:
            return {
                "ratio": None,
                "analysis": f"计算失败: {str(e)}",
                "risk_level": "unknown"
            }
    
    def calculate_net_profit_margin(
        self,
        net_profit: float,
        revenue: float
    ) -> Dict[str, Any]:
        """
        计算净利润率
        
        Args:
            net_profit: 净利润
            revenue: 营业收入
            
        Returns:
            计算结果和分析
        """
        try:
            if revenue == 0:
                return {
                    "ratio": None,
                    "percentage": None,
                    "analysis": "营业收入为零，无法计算净利润率",
                    "risk_level": "critical"
                }
            
            ratio = net_profit / revenue
            percentage = ratio * 100
            
            # 风险评估
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
                "ratio": round(ratio, 4),
                "percentage": round(percentage, 2),
                "analysis": analysis,
                "risk_level": risk_level,
                "benchmark": "因行业而异，一般5%-15%"
            }
            
        except Exception as e:
            return {
                "ratio": None,
                "percentage": None,
                "analysis": f"计算失败: {str(e)}",
                "risk_level": "unknown"
            }
    
    def extract_financial_data(
        self,
        text: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        从文本中提取财务数据
        
        Args:
            text: 财务报表文本
            tenant_id: 租户ID（用于隔离）
            
        Returns:
            提取的财务数据
        """
        try:
            # 简化的数据提取逻辑
            # TODO: 实现更智能的财务数据提取
            
            extracted_data = {
                "total_assets": self._extract_amount(text, ["资产总额", "资产总计"]),
                "total_liabilities": self._extract_amount(text, ["负债总额", "负债总计"]),
                "current_assets": self._extract_amount(text, ["流动资产"]),
                "current_liabilities": self._extract_amount(text, ["流动负债"]),
                "inventory": self._extract_amount(text, ["存货"]),
                "net_profit": self._extract_amount(text, ["净利润"]),
                "revenue": self._extract_amount(text, ["营业收入", "主营业务收入"]),
                "tenant_id": tenant_id  # 🔒 租户隔离
            }
            
            return {
                "success": True,
                "data": extracted_data,
                "message": "财务数据提取完成"
            }
            
        except Exception as e:
            return {
                "success": False,
                "data": {},
                "message": f"财务数据提取失败: {str(e)}"
            }
    
    def _extract_amount(self, text: str, keywords: List[str]) -> Optional[float]:
        """
        从文本中提取金额
        
        Args:
            text: 文本内容
            keywords: 关键词列表
            
        Returns:
            提取的金额
        """
        for keyword in keywords:
            # 查找关键词后的数字
            pattern = rf"{keyword}[：:\s]*([0-9,]+\.?[0-9]*)"
            match = re.search(pattern, text)
            if match:
                try:
                    # 移除逗号并转换为浮点数
                    amount_str = match.group(1).replace(",", "")
                    return float(amount_str)
                except (ValueError, InvalidOperation):
                    continue
        
        return None
    
    def analyze_financial_health(
        self,
        financial_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        综合财务健康分析
        
        Args:
            financial_data: 财务数据
            tenant_id: 租户ID
            
        Returns:
            财务健康分析结果
        """
        try:
            analysis_results = []
            overall_score = 0
            total_indicators = 0
            
            # 资产负债率分析
            if financial_data.get("total_assets") and financial_data.get("total_liabilities"):
                result = self.calculate_asset_liability_ratio(
                    financial_data["total_liabilities"],
                    financial_data["total_assets"]
                )
                analysis_results.append({
                    "indicator": "资产负债率",
                    "value": result.get("percentage"),
                    "analysis": result.get("analysis"),
                    "risk_level": result.get("risk_level")
                })
                
                # 评分
                if result.get("risk_level") == "low":
                    overall_score += 4
                elif result.get("risk_level") == "medium":
                    overall_score += 3
                elif result.get("risk_level") == "high":
                    overall_score += 2
                else:
                    overall_score += 1
                total_indicators += 1
            
            # 流动比率分析
            if financial_data.get("current_assets") and financial_data.get("current_liabilities"):
                result = self.calculate_current_ratio(
                    financial_data["current_assets"],
                    financial_data["current_liabilities"]
                )
                analysis_results.append({
                    "indicator": "流动比率",
                    "value": result.get("ratio"),
                    "analysis": result.get("analysis"),
                    "risk_level": result.get("risk_level")
                })
                
                if result.get("risk_level") == "low":
                    overall_score += 4
                elif result.get("risk_level") == "medium":
                    overall_score += 3
                elif result.get("risk_level") == "high":
                    overall_score += 2
                else:
                    overall_score += 1
                total_indicators += 1
            
            # 净利润率分析
            if financial_data.get("net_profit") and financial_data.get("revenue"):
                result = self.calculate_net_profit_margin(
                    financial_data["net_profit"],
                    financial_data["revenue"]
                )
                analysis_results.append({
                    "indicator": "净利润率",
                    "value": result.get("percentage"),
                    "analysis": result.get("analysis"),
                    "risk_level": result.get("risk_level")
                })
                
                if result.get("risk_level") == "low":
                    overall_score += 4
                elif result.get("risk_level") == "medium":
                    overall_score += 3
                elif result.get("risk_level") == "high":
                    overall_score += 2
                else:
                    overall_score += 1
                total_indicators += 1
            
            # 计算综合评分
            if total_indicators > 0:
                final_score = (overall_score / total_indicators) * 25  # 转换为百分制
                
                if final_score >= 80:
                    health_level = "优秀"
                    health_description = "财务状况良好，各项指标表现优秀"
                elif final_score >= 60:
                    health_level = "良好"
                    health_description = "财务状况基本良好，部分指标需要关注"
                elif final_score >= 40:
                    health_level = "一般"
                    health_description = "财务状况一般，存在一定风险"
                else:
                    health_level = "较差"
                    health_description = "财务状况较差，存在较大风险"
            else:
                final_score = 0
                health_level = "无法评估"
                health_description = "缺少必要的财务数据，无法进行评估"
            
            return {
                "tenant_id": tenant_id,  # 🔒 租户隔离
                "overall_score": round(final_score, 1),
                "health_level": health_level,
                "health_description": health_description,
                "detailed_analysis": analysis_results,
                "total_indicators": total_indicators
            }
            
        except Exception as e:
            return {
                "tenant_id": tenant_id,
                "overall_score": 0,
                "health_level": "评估失败",
                "health_description": f"财务健康分析失败: {str(e)}",
                "detailed_analysis": [],
                "total_indicators": 0
            }