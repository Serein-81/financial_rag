"""
税务逻辑验证器
用于验证税务数据的逻辑一致性和勾稽关系
"""

import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaxLogicErrorType(str, Enum):
    """税务逻辑错误类型"""
    VAT_INPUT_OUTPUT_MISMATCH = "vat_input_output_mismatch"  # 进项销项不匹配
    TAX_RATE_APPLICABILITY = "tax_rate_applicability"  # 税率适用性错误
    AMOUNT_RECONCILIATION = "amount_reconciliation"  # 金额勾稽不平
    TAX_LOAD_ANOMALY = "tax_load_anomaly"  # 税负率异常
    GROSS_MARGIN_ANOMALY = "gross_margin_anomaly"  # 毛利率异常
    INPUT_RATIO_ANOMALY = "input_ratio_anomaly"  # 进项占比异常
    TAX_CALCULATION_ERROR = "tax_calculation_error"  # 税额计算错误
    DEDUCTION_EXCEED_LIMIT = "deduction_exceed_limit"  # 扣除超限
    INCOME_TAX_MISMATCH = "income_tax_mismatch"  # 所得税数据不一致


@dataclass
class TaxLogicError:
    """税务逻辑错误"""
    error_id: str
    error_type: TaxLogicErrorType
    description: str
    severity: str  # high, medium, low
    field_name: str  # 出问题的字段名
    actual_value: Any  # 实际值
    expected_value: Any  # 期望值
    legal_basis: Optional[List[str]] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "error_type": self.error_type.value,
            "description": self.description,
            "severity": self.severity,
            "field_name": self.field_name,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "legal_basis": self.legal_basis,
            "suggestion": self.suggestion
        }


@dataclass
class TaxIndicator:
    """税务指标"""
    name: str
    value: float
    expected_range: Tuple[float, float]  # 正常范围
    is_anomaly: bool
    deviation: float  # 偏离程度
    description: str


class TaxLogicValidator:
    """
    税务逻辑验证器
    
    验证功能：
    1. 进项销项逻辑校验
    2. 税率适用性检查
    3. 金额勾稽关系验证
    4. 税务异常指标检测
    5. 税务计算准确性验证
    """

    # 税率范围定义（2024年中国增值税）
    VAT_RATE_RANGES = {
        "general": (0.13, 0.13),  # 一般税率 13%
        "low": (0.09, 0.09),  # 低税率 9%
        "service": (0.06, 0.06),  # 现代服务 6%
        "export": (0.0, 0.0),  # 出口退税 0%
    }

    # 税务指标正常范围（行业平均值，仅供参考）
    TAX_INDICATOR_RANGES = {
        "tax_load_rate": (0.03, 0.08),  # 税负率 3%-8%
        "gross_margin": (0.15, 0.50),  # 毛利率 15%-50%
        "input_tax_ratio": (0.60, 1.20),  # 进项占比 60%-120%
        "output_tax_ratio": (0.80, 1.50),  # 销项占比 80%-150%
        "vat_net_rate": (-0.05, 0.03),  # 增值税净税负 -5% to 3%
    }

    def __init__(self):
        """初始化税务逻辑验证器"""
        logger.info("🧮 [税务逻辑验证器] 初始化完成")

    async def validate(
        self,
        tax_data: Dict[str, Any],
        finance_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[TaxLogicError], List[TaxIndicator]]:
        """
        执行税务逻辑验证
        
        Args:
            tax_data: 税务数据（从TaxSpecialist提取的结构化数据）
            finance_data: 财务数据（用于交叉验证）
            
        Returns:
            errors: 税务逻辑错误列表
            indicators: 税务指标列表
        """
        errors = []
        indicators = []

        # 1. 验证进项销项逻辑
        vat_errors, vat_indicators = await self._validate_vat_logic(tax_data)
        errors.extend(vat_errors)
        indicators.extend(vat_indicators)

        # 2. 验证税率适用性
        rate_errors = await self._validate_tax_rate_applicability(tax_data)
        errors.extend(rate_errors)

        # 3. 验证金额勾稽关系
        reconciliation_errors = await self._validate_amount_reconciliation(
            tax_data, finance_data
        )
        errors.extend(reconciliation_errors)

        # 4. 检测税务异常指标
        anomaly_indicators = await self._detect_tax_anomalies(tax_data)
        indicators.extend(anomaly_indicators)

        # 5. 验证税务计算准确性
        calc_errors = await self._validate_tax_calculation(tax_data)
        errors.extend(calc_errors)

        logger.info(
            f"🧮 [税务逻辑验证器] 完成: "
            f"{len(errors)} 个错误, {len(indicators)} 个指标"
        )

        return errors, indicators

    async def _validate_vat_logic(
        self,
        tax_data: Dict[str, Any]
    ) -> Tuple[List[TaxLogicError], List[TaxIndicator]]:
        """验证增值税逻辑（进项销项）"""
        errors = []
        indicators = []

        input_tax = tax_data.get("input_tax", 0)
        output_tax = tax_data.get("output_tax", 0)
        taxable_sales = tax_data.get("taxable_sales", 0)
        taxable_purchases = tax_data.get("taxable_purchases", 0)

        try:
            input_tax = float(input_tax) if input_tax else 0
            output_tax = float(output_tax) if output_tax else 0
            taxable_sales = float(taxable_sales) if taxable_sales else 0
            taxable_purchases = float(taxable_purchases) if taxable_purchases else 0

            # 检查进项税额符号
            if input_tax < 0:
                errors.append(TaxLogicError(
                    error_id=str(uuid.uuid4()),
                    error_type=TaxLogicErrorType.VAT_INPUT_OUTPUT_MISMATCH,
                    description="进项税额不应为负数",
                    severity="high",
                    field_name="input_tax",
                    actual_value=input_tax,
                    expected_value=">= 0",
                    legal_basis=["《增值税暂行条例》第四条"],
                    suggestion="检查进项税额填报是否正确"
                ))

            # 检查销项税额符号
            if output_tax < 0:
                errors.append(TaxLogicError(
                    error_id=str(uuid.uuid4()),
                    error_type=TaxLogicErrorType.VAT_INPUT_OUTPUT_MISMATCH,
                    description="销项税额不应为负数",
                    severity="high",
                    field_name="output_tax",
                    actual_value=output_tax,
                    expected_value=">= 0",
                    legal_basis=["《增值税暂行条例》第四条"],
                    suggestion="检查销项税额填报是否正确"
                ))

            # 计算进项占比指标
            if taxable_sales > 0 and taxable_purchases > 0:
                input_ratio = (input_tax / output_tax) if output_tax > 0 else 0
                
                expected_range = self.TAX_INDICATOR_RANGES["input_ratio"]
                is_anomaly = not (expected_range[0] <= input_ratio <= expected_range[1])
                deviation = max(0, abs(input_ratio - (expected_range[0] + expected_range[1]) / 2))
                
                indicators.append(TaxIndicator(
                    name="进项占比",
                    value=input_ratio,
                    expected_range=expected_range,
                    is_anomaly=is_anomaly,
                    deviation=deviation,
                    description=f"进项税额/销项税额 = {input_ratio:.2%}"
                ))

            # 计算增值税净税负
            if taxable_sales > 0:
                net_vat = output_tax - input_tax
                net_rate = net_vat / taxable_sales
                
                expected_range = self.TAX_INDICATOR_RANGES["vat_net_rate"]
                is_anomaly = not (expected_range[0] <= net_rate <= expected_range[1])
                deviation = max(0, abs(net_rate - (expected_range[0] + expected_range[1]) / 2))
                
                indicators.append(TaxIndicator(
                    name="增值税净税负",
                    value=net_rate,
                    expected_range=expected_range,
                    is_anomaly=is_anomaly,
                    deviation=deviation,
                    description=f"(销项-进项)/销售额 = {net_rate:.2%}"
                ))

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"🧮 [税务逻辑验证器] 进项销项验证计算错误: {e}")

        return errors, indicators

    async def _validate_tax_rate_applicability(
        self,
        tax_data: Dict[str, Any]
    ) -> List[TaxLogicError]:
        """验证税率适用性"""
        errors = []

        tax_rates = tax_data.get("applicable_tax_rates", [])
        business_type = tax_data.get("business_type", "")

        if not tax_rates:
            return errors

        try:
            for rate_info in tax_rates:
                rate = float(rate_info.get("rate", 0))
                category = rate_info.get("category", "")
                amount = float(rate_info.get("amount", 0))

                # 检查税率是否在有效范围内
                valid_rates = [0.13, 0.09, 0.06, 0.05, 0.03, 0.00]
                if rate not in valid_rates:
                    errors.append(TaxLogicError(
                        error_id=str(uuid.uuid4()),
                        error_type=TaxLogicErrorType.TAX_RATE_APPLICABILITY,
                        description=f"发现异常税率 {rate}",
                        severity="medium",
                        field_name="tax_rate",
                        actual_value=rate,
                        expected_value=f"有效税率之一: {valid_rates}",
                        legal_basis=["《增值税暂行条例》第二条"],
                        suggestion="请核实税率适用的准确性"
                    ))

                # 检查税率与金额的匹配性
                if amount > 0 and rate > 0:
                    calculated_tax = amount * rate
                    reported_tax = float(rate_info.get("tax_amount", 0))
                    tolerance = 0.01  # 1%容差
                    
                    if abs(calculated_tax - reported_tax) / (calculated_tax + 1) > tolerance:
                        errors.append(TaxLogicError(
                            error_id=str(uuid.uuid4()),
                            error_type=TaxLogicErrorType.TAX_CALCULATION_ERROR,
                            description=f"税率 {rate} 与金额 {amount} 计算不匹配",
                            severity="high",
                            field_name=f"tax_amount_{category}",
                            actual_value=reported_tax,
                            expected_value=calculated_tax,
                            legal_basis=["《增值税暂行条例》第四条"],
                            suggestion=f"应纳税额 = 销售额 × 税率 = {calculated_tax}"
                        ))

        except (ValueError, TypeError) as e:
            logger.warning(f"🧮 [税务逻辑验证器] 税率验证计算错误: {e}")

        return errors

    async def _validate_amount_reconciliation(
        self,
        tax_data: Dict[str, Any],
        finance_data: Optional[Dict[str, Any]] = None
    ) -> List[TaxLogicError]:
        """验证金额勾稽关系"""
        errors = []

        # 获取税务数据中的金额
        total_income = tax_data.get("total_income", 0)
        taxable_income = tax_data.get("taxable_income", 0)
        total_deductions = tax_data.get("total_deductions", 0)

        try:
            total_income = float(total_income) if total_income else 0
            taxable_income = float(taxable_income) if taxable_income else 0
            total_deductions = float(total_deductions) if total_deductions else 0

            # 验证收入 - 扣除 = 应税收入
            expected_taxable = total_income - total_deductions
            tolerance = 0.01  # 1%容差

            if abs(taxable_income - expected_taxable) / (abs(expected_taxable) + 1) > tolerance:
                errors.append(TaxLogicError(
                    error_id=str(uuid.uuid4()),
                    error_type=TaxLogicErrorType.AMOUNT_RECONCILIATION,
                    description="收入、扣除与应税收入勾稽不平",
                    severity="high",
                    field_name="taxable_income",
                    actual_value=taxable_income,
                    expected_value=expected_taxable,
                    legal_basis=["《企业所得税法》第五条"],
                    suggestion=f"应税收入 = 总收入 - 总扣除 = {expected_taxable}"
                ))

            # 与财务数据交叉验证（如有）
            if finance_data:
                finance_revenue = finance_data.get("total_revenue", 0)
                if finance_revenue and abs(float(finance_revenue) - total_income) > 0.01:
                    errors.append(TaxLogicError(
                        error_id=str(uuid.uuid4()),
                        error_type=TaxLogicErrorType.AMOUNT_RECONCILIATION,
                        description="税务总收入与财务报表总收入不一致",
                        severity="medium",
                        field_name="total_income",
                        actual_value=total_income,
                        expected_value=finance_revenue,
                        legal_basis=["《企业会计准则》"],
                        suggestion="请核对税务与财务数据的一致性"
                    ))

        except (ValueError, TypeError) as e:
            logger.warning(f"🧮 [税务逻辑验证器] 勾稽验证计算错误: {e}")

        return errors

    async def _detect_tax_anomalies(
        self,
        tax_data: Dict[str, Any]
    ) -> List[TaxIndicator]:
        """检测税务异常指标"""
        indicators = []

        total_revenue = tax_data.get("total_income", 0)
        gross_profit = tax_data.get("gross_profit", 0)
        tax_amount = tax_data.get("tax_amount", 0)

        try:
            total_revenue = float(total_revenue) if total_revenue else 0
            gross_profit = float(gross_profit) if gross_profit else 0
            tax_amount = float(tax_amount) if tax_amount else 0

            # 检测税负率异常
            if total_revenue > 0:
                tax_load_rate = tax_amount / total_revenue
                expected_range = self.TAX_INDICATOR_RANGES["tax_load_rate"]
                is_anomaly = not (expected_range[0] <= tax_load_rate <= expected_range[1])
                deviation = max(0, abs(tax_load_rate - (expected_range[0] + expected_range[1]) / 2))
                
                indicators.append(TaxIndicator(
                    name="税负率",
                    value=tax_load_rate,
                    expected_range=expected_range,
                    is_anomaly=is_anomaly,
                    deviation=deviation,
                    description=f"税额/总收入 = {tax_load_rate:.2%}"
                ))

            # 检测毛利率异常
            if total_revenue > 0:
                gross_margin = gross_profit / total_revenue
                expected_range = self.TAX_INDICATOR_RANGES["gross_margin"]
                is_anomaly = not (expected_range[0] <= gross_margin <= expected_range[1])
                deviation = max(0, abs(gross_margin - (expected_range[0] + expected_range[1]) / 2))
                
                indicators.append(TaxIndicator(
                    name="毛利率",
                    value=gross_margin,
                    expected_range=expected_range,
                    is_anomaly=is_anomaly,
                    deviation=deviation,
                    description=f"毛利润/总收入 = {gross_margin:.2%}"
                ))

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"🧮 [税务逻辑验证器] 异常指标检测计算错误: {e}")

        return indicators

    async def _validate_tax_calculation(
        self,
        tax_data: Dict[str, Any]
    ) -> List[TaxLogicError]:
        """验证税务计算准确性"""
        errors = []

        # 企业所得税验证
        corporate_income = tax_data.get("corporate_taxable_income", 0)
        corporate_rate = tax_data.get("corporate_tax_rate", 0.25)
        corporate_tax = tax_data.get("corporate_tax_amount", 0)

        try:
            corporate_income = float(corporate_income) if corporate_income else 0
            corporate_rate = float(corporate_rate) if corporate_rate else 0.25
            corporate_tax = float(corporate_tax) if corporate_tax else 0

            if corporate_income > 0:
                expected_tax = corporate_income * corporate_rate
                tolerance = 0.01

                if abs(corporate_tax - expected_tax) / (expected_tax + 1) > tolerance:
                    errors.append(TaxLogicError(
                        error_id=str(uuid.uuid4()),
                        error_type=TaxLogicErrorType.TAX_CALCULATION_ERROR,
                        description="企业所得税计算错误",
                        severity="high",
                        field_name="corporate_tax_amount",
                        actual_value=corporate_tax,
                        expected_value=expected_tax,
                        legal_basis=["《企业所得税法》第四条"],
                        suggestion=f"企业所得税 = 应纳税所得额 × 税率 = {expected_tax}"
                    ))

        except (ValueError, TypeError) as e:
            logger.warning(f"🧮 [税务逻辑验证器] 税务计算验证错误: {e}")

        return errors

    def generate_validation_report(
        self,
        errors: List[TaxLogicError],
        indicators: List[TaxIndicator]
    ) -> Dict[str, Any]:
        """
        生成验证报告
        
        Args:
            errors: 税务逻辑错误列表
            indicators: 税务指标列表
            
        Returns:
            验证报告字典
        """
        high_severity_errors = [e for e in errors if e.severity == "high"]
        medium_severity_errors = [e for e in errors if e.severity == "medium"]
        low_severity_errors = [e for e in errors if e.severity == "low"]
        
        anomaly_indicators = [i for i in indicators if i.is_anomaly]
        
        return {
            "validation_summary": {
                "total_errors": len(errors),
                "high_severity": len(high_severity_errors),
                "medium_severity": len(medium_severity_errors),
                "low_severity": len(low_severity_errors),
                "anomaly_indicators": len(anomaly_indicators),
                "total_indicators": len(indicators)
            },
            "errors": {
                "high": [e.to_dict() for e in high_severity_errors],
                "medium": [e.to_dict() for e in medium_severity_errors],
                "low": [e.to_dict() for e in low_severity_errors]
            },
            "indicators": {
                "normal": [i.__dict__ for i in indicators if not i.is_anomaly],
                "anomaly": [i.__dict__ for i in anomaly_indicators]
            },
            "pass_validation": len(high_severity_errors) == 0 and len(anomaly_indicators) == 0
        }

    async def detect_advanced_anomalies(
        self,
        tax_data: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        执行高级异常检测（增强版）

        增强功能：
        1. IQR四分位距异常检测（鲁棒统计）
        2. Z-score标准化异常检测
        3. 行业基准对比
        4. 趋势分析（如有历史数据）
        5. 多指标关联异常检测

        Args:
            tax_data: 当前税务数据
            historical_data: 历史税务数据列表（可选）

        Returns:
            高级异常检测报告
        """
        import statistics

        anomalies = []
        confidence_scores = []

        indicators_map = {
            "tax_load_rate": self._calculate_tax_load_rate(tax_data),
            "gross_margin": self._calculate_gross_margin(tax_data),
            "input_ratio": self._calculate_input_ratio(tax_data),
            "vat_net_rate": self._calculate_vat_net_rate(tax_data),
        }

        if historical_data and len(historical_data) >= 3:
            historical_indicators = self._calculate_historical_indicators(historical_data)
            trend_anomalies = self._detect_trend_anomalies(indicators_map, historical_indicators)
            anomalies.extend(trend_anomalies)

        iqr_anomalies = self._detect_iqr_anomalies(indicators_map)
        anomalies.extend(iqr_anomalies)

        zscore_anomalies = self._detect_zscore_anomalies(indicators_map)
        anomalies.extend(zscore_anomalies)

        industry_anomalies = self._detect_industry_benchmark_anomalies(indicators_map)
        anomalies.extend(industry_anomalies)

        correlation_anomalies = self._detect_correlation_anomalies(indicators_map)
        anomalies.extend(correlation_anomalies)

        for anomaly in anomalies:
            confidence_scores.append(anomaly.get("confidence", 0.5))

        avg_confidence = statistics.mean(confidence_scores) if confidence_scores else 1.0

        return {
            "total_anomalies": len(anomalies),
            "high_confidence_anomalies": len([a for a in anomalies if a.get("confidence", 0) >= 0.8]),
            "anomalies": anomalies,
            "overall_confidence": avg_confidence,
            "risk_level": self._calculate_anomaly_risk_level(anomalies),
            "recommendations": self._generate_anomaly_recommendations(anomalies)
        }

    def _calculate_tax_load_rate(self, tax_data: Dict[str, Any]) -> Optional[float]:
        """计算税负率"""
        total_revenue = float(tax_data.get("total_income", 0) or 0)
        tax_amount = float(tax_data.get("tax_amount", 0) or 0)
        if total_revenue > 0:
            return tax_amount / total_revenue
        return None

    def _calculate_gross_margin(self, tax_data: Dict[str, Any]) -> Optional[float]:
        """计算毛利率"""
        total_revenue = float(tax_data.get("total_income", 0) or 0)
        gross_profit = float(tax_data.get("gross_profit", 0) or 0)
        if total_revenue > 0:
            return gross_profit / total_revenue
        return None

    def _calculate_input_ratio(self, tax_data: Dict[str, Any]) -> Optional[float]:
        """计算进项占比"""
        input_tax = float(tax_data.get("input_tax", 0) or 0)
        output_tax = float(tax_data.get("output_tax", 0) or 0)
        if output_tax > 0:
            return input_tax / output_tax
        return None

    def _calculate_vat_net_rate(self, tax_data: Dict[str, Any]) -> Optional[float]:
        """计算增值税净税负"""
        taxable_sales = float(tax_data.get("taxable_sales", 0) or 0)
        input_tax = float(tax_data.get("input_tax", 0) or 0)
        output_tax = float(tax_data.get("output_tax", 0) or 0)
        if taxable_sales > 0:
            return (output_tax - input_tax) / taxable_sales
        return None

    def _calculate_historical_indicators(
        self,
        historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """计算历史指标统计"""
        import statistics

        indicators_history = {
            "tax_load_rate": [],
            "gross_margin": [],
            "input_ratio": [],
            "vat_net_rate": []
        }

        for data in historical_data:
            for key in indicators_history.keys():
                calc_method = getattr(self, f"_calculate_{key}")
                value = calc_method(data)
                if value is not None:
                    indicators_history[key].append(value)

        historical_stats = {}
        for key, values in indicators_history.items():
            if len(values) >= 2:
                historical_stats[key] = {
                    "mean": statistics.mean(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "median": statistics.median(values)
                }

        return historical_stats

    def _detect_trend_anomalies(
        self,
        current: Dict[str, Optional[float]],
        historical: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """检测趋势异常"""
        anomalies = []
        import uuid

        for key, current_value in current.items():
            if current_value is None or key not in historical:
                continue

            hist = historical[key]
            if hist["stdev"] == 0:
                continue

            z_score = (current_value - hist["mean"]) / hist["stdev"]

            if abs(z_score) > 2.0:
                direction = "上升" if z_score > 0 else "下降"
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "type": "trend",
                    "indicator": key,
                    "description": f"{key}相比历史趋势{direction}异常",
                    "current_value": current_value,
                    "historical_mean": hist["mean"],
                    "z_score": z_score,
                    "severity": "high" if abs(z_score) > 3 else "medium",
                    "confidence": min(abs(z_score) / 4, 0.99),
                    "legal_basis": ["行业基准对比"]
                })

        return anomalies

    def _detect_iqr_anomalies(
        self,
        indicators: Dict[str, Optional[float]]
    ) -> List[Dict[str, Any]]:
        """基于IQR（四分位距）的异常检测"""
        import uuid

        anomalies = []

        iqr_ranges = {
            "tax_load_rate": (-0.02, 0.15),
            "gross_margin": (0.05, 0.80),
            "input_ratio": (0.40, 1.40),
            "vat_net_rate": (-0.10, 0.08)
        }

        for key, value in indicators.items():
            if value is None or key not in iqr_ranges:
                continue

            min_val, max_val = iqr_ranges[key]
            if value < min_val or value > max_val:
                deviation = max(abs(value - min_val), abs(value - max_val))
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "type": "iqr",
                    "indicator": key,
                    "description": f"{key}超出正常范围",
                    "current_value": value,
                    "expected_range": (min_val, max_val),
                    "deviation": deviation,
                    "severity": "high" if deviation > 0.1 else "medium",
                    "confidence": min(deviation * 5, 0.95),
                    "legal_basis": ["税务统计规律"]
                })

        return anomalies

    def _detect_zscore_anomalies(
        self,
        indicators: Dict[str, Optional[float]]
    ) -> List[Dict[str, Any]]:
        """基于Z-score的异常检测"""
        import uuid

        anomalies = []

        industry_means = {
            "tax_load_rate": 0.045,
            "gross_margin": 0.30,
            "input_ratio": 0.85,
            "vat_net_rate": 0.02
        }

        industry_stdevs = {
            "tax_load_rate": 0.02,
            "gross_margin": 0.15,
            "input_ratio": 0.25,
            "vat_net_rate": 0.03
        }

        for key, value in indicators.items():
            if value is None:
                continue

            mean = industry_means.get(key, 0.5)
            stdev = industry_stdevs.get(key, 0.1)

            if stdev > 0:
                z_score = (value - mean) / stdev

                if abs(z_score) > 2.5:
                    anomalies.append({
                        "anomaly_id": str(uuid.uuid4()),
                        "type": "zscore",
                        "indicator": key,
                        "description": f"{key}偏离行业标准",
                        "current_value": value,
                        "industry_mean": mean,
                        "z_score": z_score,
                        "severity": "high" if abs(z_score) > 3 else "medium",
                        "confidence": min(abs(z_score) / 5, 0.95),
                        "legal_basis": ["行业基准"]
                    })

        return anomalies

    def _detect_industry_benchmark_anomalies(
        self,
        indicators: Dict[str, Optional[float]]
    ) -> List[Dict[str, Any]]:
        """行业基准对比异常检测"""
        import uuid

        anomalies = []

        industry_benchmarks = {
            "tax_load_rate": {
                "expected": (0.03, 0.08),
                "description": "税负率",
                "legal": "税负率监控"
            },
            "gross_margin": {
                "expected": (0.15, 0.50),
                "description": "毛利率",
                "legal": "毛利分析"
            }
        }

        for key, benchmark in industry_benchmarks.items():
            value = indicators.get(key)
            if value is None:
                continue

            min_val, max_val = benchmark["expected"]
            if value < min_val or value > max_val:
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "type": "industry_benchmark",
                    "indicator": key,
                    "description": f"{benchmark['description']}偏离行业正常水平",
                    "current_value": value,
                    "benchmark_range": benchmark["expected"],
                    "severity": "medium",
                    "confidence": 0.75,
                    "legal_basis": [benchmark["legal"]]
                })

        return anomalies

    def _detect_correlation_anomalies(
        self,
        indicators: Dict[str, Optional[float]]
    ) -> List[Dict[str, Any]]:
        """多指标关联异常检测"""
        import uuid

        anomalies = []

        input_ratio = indicators.get("input_ratio")
        vat_net_rate = indicators.get("vat_net_rate")

        if input_ratio is not None and vat_net_rate is not None:
            expected_net = (1 - input_ratio) * indicators.get("output_tax", 1)
            if abs(vat_net_rate - expected_net) > 0.05:
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "type": "correlation",
                    "indicator": "vat_relationship",
                    "description": "进项销项关系异常",
                    "current_vat_net_rate": vat_net_rate,
                    "expected_correlation": "正常",
                    "severity": "high",
                    "confidence": 0.85,
                    "legal_basis": ["增值税勾稽关系"]
                })

        return anomalies

    def _calculate_anomaly_risk_level(self, anomalies: List[Dict[str, Any]]) -> str:
        """计算异常风险等级"""
        high_count = len([a for a in anomalies if a.get("severity") == "high"])
        medium_count = len([a for a in anomalies if a.get("severity") == "medium"])

        if high_count >= 2:
            return "high"
        elif high_count >= 1 or medium_count >= 3:
            return "medium"
        elif medium_count >= 1:
            return "low"
        return "normal"

    def _generate_anomaly_recommendations(
        self,
        anomalies: List[Dict[str, Any]]
    ) -> List[str]:
        """生成异常处理建议"""
        recommendations = []

        type_based = {
            "trend": "建议对比历史数据，分析变化原因",
            "iqr": "建议检查数据填报的准确性",
            "zscore": "建议与行业标准进行对比分析",
            "industry_benchmark": "建议了解行业特性和经营模式",
            "correlation": "建议核实进项销项数据的匹配性"
        }

        for anomaly in anomalies:
            anomaly_type = anomaly.get("type", "")
            if anomaly_type in type_based:
                recommendations.append(type_based[anomaly_type])

        return list(set(recommendations))


# 全局验证器实例
tax_logic_validator = TaxLogicValidator()


async def validate_tax_logic(
    tax_data: Dict[str, Any],
    finance_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    便捷的税务逻辑验证接口
    
    Args:
        tax_data: 税务数据
        finance_data: 财务数据（可选）
        
    Returns:
        验证报告
    """
    errors, indicators = await tax_logic_validator.validate(tax_data, finance_data)
    return tax_logic_validator.generate_validation_report(errors, indicators)
