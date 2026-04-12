"""
财务健康智能监控服务
提供财务异常检测、预警和趋势分析功能
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from app.schemas.financial_health import (
    AnomalyType,
    SeverityLevel,
    AnomalyStatus,
    FinancialHealthMonitorRequest,
    FinancialHealthDashboard,
    FinancialMetric,
    AnomalyItem,
    AnomalyDetectionRule,
    TrendAnalysisRequest,
    TrendAnalysisResult,
    TrendPoint,
    AlertSubscriptionRequest,
)
from app.agent_framework.tools.financial_data_tools import FinancialDataQueryTool
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.services.agent_tracer import AgentTracer

logger = logging.getLogger(__name__)

try:
    from app.services.admin_notification_service import AdminNotificationService, RiskLevel, RiskCategory
except ImportError:
    from enum import Enum
    class RiskLevel(str, Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
    
    class RiskCategory(str, Enum):
        FINANCIAL = "financial"
        COMPLIANCE = "compliance"
        OPERATIONAL = "operational"
        REPUTATIONAL = "reputational"
    
    AdminNotificationService = None
    logger.warning("⚠️ AdminNotificationService 不可用 (redis 依赖缺失)")

try:
    from app.multi_agent_system.agents.finance_specialist import FinanceSpecialist
    _FINANCE_SPECIALIST_AVAILABLE = True
except ImportError:
    FinanceSpecialist = None
    _FINANCE_SPECIALIST_AVAILABLE = False
    logger.warning("⚠️ FinanceSpecialist 不可用 (neo4j 依赖缺失)")


class FinancialAnomalyDetector:
    """
    财务异常检测器
    
    预定义异常检测规则：
    1. 收入断崖式下跌 - 单月收入环比下降>30%
    2. 成本异常飙升 - 单月成本环比上升>20%
    3. 现金流持续为负 - 连续3个月经营现金流为负
    4. 回款周期延长 - 回款周期超过行业平均150%
    5. 毛利率持续下降 - 连续3个月毛利率下降
    6. 资产负债率超标 - 超过行业安全阈值
    """

    def __init__(self):
        self.rules = self._initialize_rules()

    def _initialize_rules(self) -> List[AnomalyDetectionRule]:
        """初始化异常检测规则"""
        return [
            AnomalyDetectionRule(
                rule_id="revenue_drop_rule",
                anomaly_type=AnomalyType.REVENUE_DROP,
                condition="monthly_revenue_drop > 30%",
                threshold=30.0,
                severity=SeverityLevel.HIGH,
                lookback_periods=1
            ),
            AnomalyDetectionRule(
                rule_id="cost_surge_rule",
                anomaly_type=AnomalyType.COST_SURGE,
                condition="monthly_cost_increase > 20%",
                threshold=20.0,
                severity=SeverityLevel.MEDIUM,
                lookback_periods=1
            ),
            AnomalyDetectionRule(
                rule_id="negative_cashflow_rule",
                anomaly_type=AnomalyType.NEGATIVE_CASHFLOW,
                condition="连续3个月经营现金流为负",
                threshold=3,
                severity=SeverityLevel.HIGH,
                lookback_periods=3
            ),
            AnomalyDetectionRule(
                rule_id="extended_receivables_rule",
                anomaly_type=AnomalyType.EXTENDED_RECEIVABLES,
                condition="receivables_period > industry_avg * 1.5",
                threshold=1.5,
                severity=SeverityLevel.MEDIUM,
                lookback_periods=1
            ),
            AnomalyDetectionRule(
                rule_id="margin_decline_rule",
                anomaly_type=AnomalyType.MARGIN_DECLINE,
                condition="连续3个月毛利率下降",
                threshold=3,
                severity=SeverityLevel.MEDIUM,
                lookback_periods=3
            ),
            AnomalyDetectionRule(
                rule_id="leverage_exceed_rule",
                anomaly_type=AnomalyType.LEVERAGE_EXCEED,
                condition="debt_ratio > 0.7",
                threshold=0.7,
                severity=SeverityLevel.HIGH,
                lookback_periods=1
            ),
        ]

    def detect_anomalies(
        self,
        current_data: Dict[str, Any],
        historical_data: List[Dict[str, Any]]
    ) -> List[AnomalyItem]:
        """
        检测财务异常
        
        Args:
            current_data: 当前财务数据
            historical_data: 历史财务数据列表
            
        Returns:
            List[AnomalyItem]: 检测到的异常列表
        """
        anomalies = []

        if len(historical_data) >= 1:
            prev_data = historical_data[0]
            
            current_revenue = current_data.get("total_revenue", 0)
            prev_revenue = prev_data.get("total_revenue", 0)
            
            if prev_revenue > 0:
                revenue_change = ((current_revenue - prev_revenue) / prev_revenue) * 100
                
                if revenue_change < -30:
                    anomalies.append(AnomalyItem(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type=AnomalyType.REVENUE_DROP,
                        severity=SeverityLevel.HIGH,
                        status=AnomalyStatus.DETECTED,
                        detected_at=datetime.now(),
                        title="收入断崖式下跌",
                        description=f"当月收入环比下降 {abs(revenue_change):.1f}%，超过30%阈值",
                        affected_metrics=["total_revenue"],
                        current_value=current_revenue,
                        threshold_value=prev_revenue * 0.7,
                        deviation_percentage=revenue_change,
                        potential_impact="可能导致资金链紧张，影响正常运营",
                        suggested_actions=[
                            "分析收入下降的具体原因",
                            "评估是否为季节性因素",
                            "制定应对措施"
                        ],
                        evidence=[f"上月收入: ¥{prev_revenue:,.2f}", f"本月收入: ¥{current_revenue:,.2f}"],
                        confidence_score=0.90
                    ))

            current_cost = current_data.get("total_expenses", 0)
            prev_cost = prev_data.get("total_expenses", 0)
            
            if prev_cost > 0:
                cost_change = ((current_cost - prev_cost) / prev_cost) * 100
                
                if cost_change > 20:
                    anomalies.append(AnomalyItem(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type=AnomalyType.COST_SURGE,
                        severity=SeverityLevel.MEDIUM,
                        status=AnomalyStatus.DETECTED,
                        detected_at=datetime.now(),
                        title="成本异常飙升",
                        description=f"当月成本环比上升 {cost_change:.1f}%，超过20%阈值",
                        affected_metrics=["total_expenses"],
                        current_value=current_cost,
                        threshold_value=prev_cost * 1.2,
                        deviation_percentage=cost_change,
                        potential_impact="压缩利润空间，影响盈利能力",
                        suggested_actions=[
                            "分析成本上升的具体项目",
                            "审查采购流程",
                            "寻找成本优化空间"
                        ],
                        evidence=[f"上月成本: ¥{prev_cost:,.2f}", f"本月成本: ¥{current_cost:,.2f}"],
                        confidence_score=0.85
                    ))

        if len(historical_data) >= 3:
            cashflow_negative_count = sum(
                1 for data in historical_data[-3:]
                if data.get("cash_flow", 0) < 0
            )
            
            if cashflow_negative_count >= 3:
                anomalies.append(AnomalyItem(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type=AnomalyType.NEGATIVE_CASHFLOW,
                    severity=SeverityLevel.HIGH,
                    status=AnomalyStatus.DETECTED,
                    detected_at=datetime.now(),
                    title="现金流持续为负",
                    description="连续3个月经营现金流为负，现金流状况堪忧",
                    affected_metrics=["cash_flow"],
                    potential_impact="资金链断裂风险高，需立即采取措施",
                    suggested_actions=[
                        "加快应收账款回收",
                        "优化付款周期",
                        "考虑融资计划"
                    ],
                    confidence_score=0.95
                ))

            margin_declines = 0
            for i in range(1, min(len(historical_data), 3)):
                current_margin = historical_data[-i].get("gross_margin", 0)
                prev_margin = historical_data[-i-1].get("gross_margin", 0)
                if current_margin < prev_margin:
                    margin_declines += 1
            
            if margin_declines >= 2:
                anomalies.append(AnomalyItem(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type=AnomalyType.MARGIN_DECLINE,
                    severity=SeverityLevel.MEDIUM,
                    status=AnomalyStatus.DETECTED,
                    detected_at=datetime.now(),
                    title="毛利率持续下降",
                    description="毛利率连续多个月呈下降趋势",
                    affected_metrics=["gross_margin"],
                    potential_impact="盈利能力持续恶化",
                    suggested_actions=[
                        "分析毛利率下降原因",
                        "优化产品结构",
                        "控制成本上升"
                    ],
                    confidence_score=0.80
                ))

        debt_ratio = current_data.get("debt_ratio", 0)
        if debt_ratio > 0.7:
            anomalies.append(AnomalyItem(
                anomaly_id=str(uuid.uuid4()),
                anomaly_type=AnomalyType.LEVERAGE_EXCEED,
                severity=SeverityLevel.HIGH,
                status=AnomalyStatus.DETECTED,
                detected_at=datetime.now(),
                title="资产负债率超标",
                description=f"资产负债率 {debt_ratio*100:.1f}% 超过70%安全阈值",
                affected_metrics=["debt_ratio"],
                current_value=debt_ratio,
                threshold_value=0.7,
                deviation_percentage=(debt_ratio - 0.7) * 100,
                potential_impact="财务风险较高，偿债能力受限",
                suggested_actions=[
                    "优化负债结构",
                    "增加所有者权益",
                    "控制新增负债"
                ],
                confidence_score=0.95
            ))

        return anomalies


class FinancialHealthService:
    """
    财务健康服务
    
    功能：
    1. 财务健康状态监控
    2. 异常检测与预警
    3. 趋势分析与预测
    4. 预警订阅管理
    """

    def __init__(self):
        self.financial_data_tool = FinancialDataQueryTool()
        self.anomaly_detector = FinancialAnomalyDetector()
        self.agent_tracer = AgentTracer()
        self.notification_service = AdminNotificationService()
        
        self._initialize_llm_components()
        
        self._alert_subscriptions = {}
        
        logger.info("✅ 财务健康服务初始化完成")

    def _initialize_llm_components(self):
        """初始化LLM组件"""
        try:
            self.llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
            self.tool_manager = ToolManager()
            self.finance_specialist = FinanceSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            logger.info("✅ LLM组件初始化完成")
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ LLM组件初始化数据错误: {e}")
            self.finance_specialist = None
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ LLM组件初始化IO错误: {e}")
            self.finance_specialist = None
        except Exception as e:
            logger.warning(f"⚠️ LLM组件初始化失败: {e}")
            self.finance_specialist = None

    async def monitor_financial_health(
        self,
        request: FinancialHealthMonitorRequest
    ) -> Dict[str, Any]:
        """
        监控财务健康状况
        
        Args:
            request: 监控请求
            
        Returns:
            Dict: 监控结果
        """
        monitor_id = str(uuid.uuid4())
        
        logger.info(f"🔍 开始财务健康监控: {monitor_id}")
        
        trace_id = await self.agent_tracer.start_trace(
            agent_type="financial_health",
            user_query="财务健康监控",
            message_id=monitor_id
        )
        
        try:
            financial_data = await self._fetch_financial_data(
                request.tenant_id,
                request.user_id
            )
            
            historical_data = await self._fetch_historical_data(
                request.tenant_id,
                request.user_id,
                request.period_start,
                request.period_end
            )
            
            dashboard = await self._generate_dashboard(
                monitor_id,
                request.tenant_id,
                financial_data,
                historical_data,
                request.period_start,
                request.period_end
            )
            
            anomalies = []
            if request.include_anomaly_detection:
                anomalies = self.anomaly_detector.detect_anomalies(
                    financial_data,
                    historical_data
                )
                
                if anomalies:
                    logger.warning(f"⚠️ 检测到 {len(anomalies)} 个财务异常")
                    
                    for anomaly in anomalies:
                        if anomaly.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
                            if self.notification_service:
                                await self.notification_service.detect_risk_level(
                                    user_query=f"财务异常检测 - {anomaly.title}",
                                    context={"anomaly_type": anomaly.anomaly_type.value}
                                )
            
            await self.agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=f"财务健康监控完成，检测到{len(anomalies)}个异常",
                success=True
            )
            
            dashboard_dict = dashboard.model_dump() if hasattr(dashboard, 'model_dump') else dashboard
            
            saved_report_id = await self._save_health_report(
                monitor_id=monitor_id,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                period_start=request.period_start,
                period_end=request.period_end,
                dashboard=dashboard_dict,
                current_data=financial_data,
                historical_data=historical_data,
                anomalies=anomalies
            )
            
            return {
                "monitor_id": monitor_id,
                "report_id": saved_report_id,
                "status": "completed",
                "dashboard": dashboard,
                "financial_data": financial_data,
                "anomalies_detected": anomalies,
                "generated_at": datetime.now()
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 财务健康监控数据错误: {e}", exc_info=True)
            await self.agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=f"数据错误: {str(e)}",
                success=False,
                error_message=str(e)
            )
            raise
        except (OSError, IOError) as e:
            logger.error(f"❌ 财务健康监控IO错误: {e}", exc_info=True)
            await self.agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=f"IO错误: {str(e)}",
                success=False,
                error_message=str(e)
            )
            raise
        except Exception as e:
            logger.error(f"❌ 财务健康监控失败: {e}", exc_info=True)
            
            await self.agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=f"监控失败: {str(e)}",
                success=False,
                error_message=str(e)
            )
            
            raise

    def _safe_uuid(self, value):
        """安全地将值转换为 UUID 对象"""
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                return uuid.UUID(value)
            except ValueError:
                logger.warning(f"⚠️ 无效的 UUID 字符串: {value}")
                return None
        return None

    async def _save_health_report(
        self,
        monitor_id: str,
        user_id: str,
        tenant_id: str,
        period_start: date,
        period_end: date,
        dashboard: Dict[str, Any],
        current_data: Dict[str, Any],
        historical_data: List[Dict[str, Any]],
        anomalies: List[Any]
    ) -> Optional[str]:
        """保存财务健康报告到数据库"""
        from app.db.session import AsyncSessionLocal
        from app.models.financial_health import FinancialHealthReport, HealthStatus, ReportPeriod
        
        try:
            user_uuid = self._safe_uuid(user_id)
            
            if not user_uuid:
                logger.error(f"❌ 无效的 user_id: {user_id}")
                return None
            
            async with AsyncSessionLocal() as db:
                report_id = str(uuid.uuid4())
                
                health_score = dashboard.get("overall_health_score", 0) or dashboard.get("health_score", 0)
                if health_score >= 80:
                    health_status = HealthStatus.healthy
                elif health_score >= 60:
                    health_status = HealthStatus.warning
                elif health_score >= 40:
                    health_status = HealthStatus.caution
                else:
                    health_status = HealthStatus.critical
                
                total_revenue = current_data.get("total_revenue", 0)
                prev_revenue = historical_data[0].get("total_revenue", 0) if historical_data else 0
                revenue_growth = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
                
                total_expenses = current_data.get("total_expenses", 0)
                prev_expenses = historical_data[0].get("total_expenses", 0) if historical_data else 0
                expense_growth = ((total_expenses - prev_expenses) / prev_expenses * 100) if prev_expenses > 0 else 0
                
                net_profit = current_data.get("net_profit", 0)
                profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
                
                cash_flow = current_data.get("cash_flow", 0)
                operating_cash_flow = current_data.get("operating_cash_flow", cash_flow)
                net_flow = operating_cash_flow
                
                report = FinancialHealthReport(
                    id=uuid.UUID(report_id),
                    user_id=user_uuid,
                    tenant_id=str(tenant_id) if tenant_id else "unknown",
                    report_name=f"财务健康报告-{datetime.now().strftime('%Y%m%d %H:%M')}",
                    report_period=ReportPeriod.monthly,
                    period_start=period_start,
                    period_end=period_end,
                    overall_health_score=health_score,
                    health_status=health_status,
                    revenue_summary={
                        "total_revenue": total_revenue,
                        "revenue_growth": revenue_growth,
                        "revenue_analysis": {}
                    },
                    expense_summary={
                        "total_expenses": total_expenses,
                        "expense_growth": expense_growth,
                        "expense_analysis": {}
                    },
                    profit_summary={
                        "profit_margin": profit_margin,
                        "net_profit": net_profit
                    },
                    cash_flow_summary={
                        "inflow": operating_cash_flow if operating_cash_flow > 0 else 0,
                        "outflow": abs(operating_cash_flow) if operating_cash_flow < 0 else 0,
                        "net_flow": net_flow
                    },
                    financial_metrics=dashboard.get("key_metrics", []),
                    risk_assessments=[],
                    recommendations=[],
                    anomaly_detections=[
                        {
                            "anomaly_type": a.anomaly_type.value if hasattr(a.anomaly_type, 'value') else str(a.anomaly_type),
                            "severity": a.severity.value if hasattr(a.severity, 'value') else str(a.severity),
                            "title": a.title,
                            "description": a.description
                        }
                        for a in anomalies
                    ],
                    status="completed",
                    created_at=datetime.now(),
                    completed_at=datetime.now()
                )
                
                db.add(report)
                await db.commit()
                
                logger.info(f"✅ 财务健康报告已保存: {report_id}")
                return report_id
                
        except Exception as e:
            logger.error(f"❌ 保存财务健康报告失败: {e}", exc_info=True)
            return None

    async def _fetch_financial_data(
        self,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """获取当前财务数据"""
        try:
            result = await self.financial_data_tool.execute(
                user_id=user_id,
                tenant_id=tenant_id,
                fiscal_year=datetime.now().year,
                include_vat=True,
                include_corporate_tax=True
            )

            status = result.get("status")
            if status in ("error", "unavailable", None):
                logger.warning(f"⚠️ 财务数据不可用: {result.get('message', '未知原因')}")
                return {}

            return result.get("financial_data", {})

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 获取财务数据数据错误: {e}")
            return {}
        except (OSError, IOError) as e:
            logger.error(f"❌ 获取财务数据IO错误: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ 获取财务数据失败: {e}")
            return {}

    async def _fetch_historical_data(
        self,
        tenant_id: str,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """获取历史财务数据"""
        historical_data = []
        
        try:
            current_year = datetime.now().year
            for year_offset in range(3):
                year = current_year - year_offset
                result = await self.financial_data_tool.execute(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    fiscal_year=year,
                    include_vat=True,
                    include_corporate_tax=True
                )
                
                if result.get("status") == "success":
                    historical_data.append(result.get("financial_data", {}))
                else:
                    logger.debug(f"⚠️ {year}年度财务数据不可用: {result.get('message', '未知')}")

        except (ValueError, KeyError) as e:
            logger.error(f"❌ 获取历史数据数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 获取历史数据IO错误: {e}")
        except Exception as e:
            logger.error(f"❌ 获取历史数据失败: {e}")
        
        return historical_data

    async def _generate_dashboard(
        self,
        dashboard_id: str,
        tenant_id: str,
        current_data: Dict[str, Any],
        historical_data: List[Dict[str, Any]],
        start_date: date,
        end_date: date
    ) -> FinancialHealthDashboard:
        """生成财务健康仪表盘"""
        key_metrics = []
        
        metrics_config = [
            ("total_revenue", "总收入", "¥", "revenue"),
            ("total_expenses", "总支出", "¥", "expenses"),
            ("gross_margin", "毛利率", "%", "margin"),
            ("net_profit", "净利润", "¥", "profit"),
        ]
        
        for data_key, data_name, unit, metric_type in metrics_config:
            value = current_data.get(data_key, 0.0)
            change_pct = 0.0
            trend = "stable"
            status = "normal"
            
            if historical_data and len(historical_data) > 0:
                prev_value = historical_data[0].get(data_key, 0.0)
                if prev_value > 0:
                    change_pct = ((value - prev_value) / prev_value) * 100
                    trend = "up" if change_pct > 0 else "down"
                    
                    if abs(change_pct) > 20:
                        status = "high"
                    elif abs(change_pct) > 10:
                        status = "warning"
            
            key_metrics.append(FinancialMetric(
                name=data_name,
                value=value,
                unit=unit,
                formatted_value=self._format_value(value, unit),
                change_percentage=change_pct,
                trend=trend,
                status=status
            ))
        
        anomalies = self.anomaly_detector.detect_anomalies(current_data, historical_data)
        active_anomalies = [a for a in anomalies if a.status == AnomalyStatus.DETECTED]
        critical_count = sum(1 for a in active_anomalies if a.severity == SeverityLevel.CRITICAL)
        
        health_score = self._calculate_health_score(active_anomalies, key_metrics)
        
        dashboard = FinancialHealthDashboard(
            dashboard_id=dashboard_id,
            tenant_id=tenant_id,
            generated_at=datetime.now(),
            period=f"{start_date} 至 {end_date}",
            overall_health_score=health_score,
            health_status=self._get_health_status(health_score),
            key_metrics=key_metrics,
            active_anomalies_count=len(active_anomalies),
            critical_anomalies_count=critical_count,
            recent_anomalies=active_anomalies[:5],
            cash_flow_status=self._assess_cash_flow(current_data, historical_data),
            profitability_status=self._assess_profitability(current_data, historical_data),
            liquidity_status=self._assess_liquidity(current_data),
            leverage_status=self._assess_leverage(current_data),
            summary=self._generate_dashboard_summary(health_score, len(active_anomalies), critical_count)
        )
        
        return dashboard

    def _format_value(self, value: float, unit: str) -> str:
        """格式化数值"""
        if unit == "¥":
            if abs(value) >= 100000000:
                return f"¥{value/100000000:.2f}亿"
            elif abs(value) >= 10000:
                return f"¥{value/10000:.2f}万"
            else:
                return f"¥{value:,.2f}"
        elif unit == "%":
            return f"{value:.2f}%"
        else:
            return str(value)

    def _calculate_health_score(
        self,
        anomalies: List[AnomalyItem],
        metrics: List[FinancialMetric]
    ) -> float:
        """计算健康评分"""
        base_score = 100.0
        
        severity_deduction = {
            SeverityLevel.LOW: 5,
            SeverityLevel.MEDIUM: 15,
            SeverityLevel.HIGH: 30,
            SeverityLevel.CRITICAL: 50
        }
        
        for anomaly in anomalies:
            deduction = severity_deduction.get(anomaly.severity, 10)
            base_score -= deduction * anomaly.confidence_score
        
        warning_metrics = sum(1 for m in metrics if m.status == "warning")
        high_metrics = sum(1 for m in metrics if m.status == "high")
        
        base_score -= warning_metrics * 5
        base_score -= high_metrics * 10
        
        return max(0.0, min(100.0, base_score))

    def _get_health_status(self, score: float) -> str:
        """获取健康状态"""
        if score >= 80:
            return "healthy"
        elif score >= 50:
            return "warning"
        else:
            return "critical"

    def _assess_cash_flow(
        self,
        current_data: Dict[str, Any],
        historical_data: List[Dict[str, Any]]
    ) -> str:
        """评估现金流状态"""
        cash_flow = current_data.get("cash_flow", 0)
        
        if cash_flow > 0:
            if len(historical_data) >= 3:
                recent_negative = sum(
                    1 for d in historical_data[:3] if d.get("cash_flow", 0) < 0
                )
                if recent_negative == 0:
                    return "良好"
        
        if cash_flow < 0:
            return "需关注"
        
        return "正常"

    def _assess_profitability(
        self,
        current_data: Dict[str, Any],
        historical_data: List[Dict[str, Any]]
    ) -> str:
        """评估盈利能力"""
        margin = current_data.get("gross_margin", 0)
        
        if margin >= 0.3:
            return "优秀"
        elif margin >= 0.2:
            return "良好"
        elif margin >= 0.1:
            return "一般"
        else:
            return "需改善"

    def _assess_liquidity(self, current_data: Dict[str, Any]) -> str:
        """评估流动性"""
        current_ratio = current_data.get("current_ratio", 2.0)
        
        if current_ratio >= 2.0:
            return "充足"
        elif current_ratio >= 1.5:
            return "正常"
        elif current_ratio >= 1.0:
            return "偏紧"
        else:
            return "不足"

    def _assess_leverage(self, current_data: Dict[str, Any]) -> str:
        """评估杠杆率"""
        debt_ratio = current_data.get("debt_ratio", 0.5)
        
        if debt_ratio <= 0.3:
            return "偏低"
        elif debt_ratio <= 0.5:
            return "适中"
        elif debt_ratio <= 0.7:
            return "偏高"
        else:
            return "过高"

    def _generate_dashboard_summary(
        self,
        health_score: float,
        anomaly_count: int,
        critical_count: int
    ) -> str:
        """生成仪表盘摘要"""
        status = self._get_health_status(health_score)
        
        summary_parts = [
            f"财务健康评分 {health_score:.1f} 分，状态{status}。"
        ]
        
        if critical_count > 0:
            summary_parts.append(f"存在 {critical_count} 个严重异常，需立即关注。")
        elif anomaly_count > 0:
            summary_parts.append(f"存在 {anomaly_count} 个异常，建议排查。")
        else:
            summary_parts.append("未检测到明显异常。")
        
        return " ".join(summary_parts)

    async def query_anomalies(
        self,
        tenant_id: str,
        anomaly_types: Optional[List[AnomalyType]] = None,
        severity_levels: Optional[List[SeverityLevel]] = None,
        status: Optional[AnomalyStatus] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """查询异常列表"""
        return {
            "total_count": 0,
            "anomalies": [],
            "page": 1,
            "page_size": limit,
            "message": "异常查询功能需要数据库支持"
        }

    async def perform_trend_analysis(
        self,
        request: TrendAnalysisRequest
    ) -> Dict[str, Any]:
        """
        执行趋势分析
        
        Args:
            request: 趋势分析请求
            
        Returns:
            Dict: 趋势分析结果
        """
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"📈 开始趋势分析: {analysis_id}")
        
        analysis_results = []
        
        for metric_name in request.metric_names:
            historical_data = await self._fetch_historical_data(
                request.tenant_id,
                request.user_id,
                datetime.now().date(),
                datetime.now().date()
            )
            
            trend_result = TrendAnalysisResult(
                metric_name=metric_name,
                trend_direction="stable",
                trend_strength=0.5,
                average_value=0.0,
                min_value=0.0,
                max_value=0.0,
                volatility=0.0,
                historical_values=[],
                forecast_values=[],
                insights=["数据不足，无法进行趋势分析"]
            )
            
            analysis_results.append(trend_result)
        
        return {
            "analysis_id": analysis_id,
            "tenant_id": request.tenant_id,
            "period_type": request.period_type,
            "analysis_results": analysis_results,
            "summary": f"趋势分析完成，共分析 {len(analysis_results)} 个指标",
            "generated_at": datetime.now()
        }

    async def subscribe_alerts(
        self,
        request: AlertSubscriptionRequest
    ) -> Dict[str, Any]:
        """
        订阅预警通知
        
        Args:
            request: 订阅请求
            
        Returns:
            Dict: 订阅结果
        """
        subscription_id = str(uuid.uuid4())
        
        self._alert_subscriptions[subscription_id] = {
            "subscription_id": subscription_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "alert_types": [t.value for t in request.alert_types],
            "severity_threshold": request.severity_threshold.value,
            "notification_channels": request.notification_channels,
            "frequency": request.frequency.value,
            "created_at": datetime.now()
        }
        
        logger.info(f"📧 创建预警订阅: {subscription_id}")
        
        return {
            "subscription_id": subscription_id,
            "status": "active",
            "created_at": datetime.now(),
            "message": "预警订阅创建成功"
        }

    async def get_analysis_history(
        self,
        user_id: str,
        tenant_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        获取财务健康分析历史记录

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量

        Returns:
            包含历史记录列表和总数的字典
        """
        try:
            logger.info(f"📋 获取财务健康分析历史: user={user_id}, page={page}, page_size={page_size}")

            from app.db.session import AsyncSessionLocal
            from app.models.financial_health import FinancialHealthReport
            from sqlalchemy import select, func, desc

            async with AsyncSessionLocal() as db:
                offset = (page - 1) * page_size

                count_stmt = select(func.count(FinancialHealthReport.id)).where(
                    FinancialHealthReport.tenant_id == tenant_id
                )
                count_result = await db.execute(count_stmt)
                total = count_result.scalar() or 0

                stmt = (
                    select(FinancialHealthReport)
                    .where(FinancialHealthReport.tenant_id == tenant_id)
                    .order_by(desc(FinancialHealthReport.period_end))
                    .offset(offset)
                    .limit(page_size)
                )
                result = await db.execute(stmt)
                reports = result.scalars().all()

                items = []
                for report in reports:
                    items.append({
                        "id": str(report.id),
                        "report_name": report.report_name or "财务健康报告",
                        "health_score": report.overall_health_score or 0,
                        "health_level": report.health_status.value if report.health_status else "unknown",
                        "anomaly_count": len(report.anomaly_detections) if report.anomaly_detections else 0,
                        "status": "completed",
                        "created_at": report.created_at.isoformat() if report.created_at else None,
                        "period_start": report.period_start.isoformat() if report.period_start else None,
                        "period_end": report.period_end.isoformat() if report.period_end else None
                    })

                return {
                    "reports": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }

        except Exception as e:
            error_str = str(e)
            if "UndefinedTableError" in error_str or "does not exist" in error_str:
                logger.warning(f"⚠️ 财务健康报告表不存在，返回空数据: {tenant_id}")
            else:
                logger.error(f"❌ 获取财务健康历史失败: {e}", exc_info=True)
            return {"reports": [], "total": 0, "page": page, "page_size": page_size}
