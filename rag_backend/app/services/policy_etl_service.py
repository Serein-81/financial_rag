"""
政策ETL服务 (Policy ETL Service)
负责政策采集、解析、理解、影响分析
"""

import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.policy import Policy, PolicyStatus, PolicyPriority
from app.db.session import SessionLocal
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PolicyType(str, Enum):
    """政策类型"""
    NATIONAL = "national"
    PROVINCIAL = "provincial"
    MUNICIPAL = "municipal"
    DEPARTMENTAL = "departmental"
    CIRCULAR = "circular"
    INTERPRETATION = "interpretation"


class ImpactLevel(str, Enum):
    """影响级别"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PolicyScope(BaseModel):
    """政策适用范围"""
    industries: List[str] = Field(default_factory=list, description="适用行业")
    regions: List[str] = Field(default_factory=list, description="适用地区")
    scales: List[str] = Field(default_factory=list, description="适用企业规模")
    tax_types: List[str] = Field(default_factory=list, description="相关税种")
    enterprise_types: List[str] = Field(default_factory=list, description="企业类型")


class PolicyAnalysis(BaseModel):
    """政策分析结果"""
    policy_id: str = Field(description="政策编号")
    title: str = Field(description="政策标题")
    summary: str = Field(description="政策摘要")
    scope: PolicyScope = Field(description="适用范围")
    key_points: List[str] = Field(default_factory=list, description="要点提炼")
    impact_analysis: str = Field(description="影响分析")
    compliance_requirements: List[str] = Field(default_factory=list, description="合规要求")
    deadline: Optional[str] = Field(default=None, description="重要时间节点")
    related_policies: List[str] = Field(default_factory=list, description="相关政策")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="置信度")


class PolicyTask(BaseModel):
    """政策处理任务"""
    source_url: Optional[str] = Field(default=None, description="来源URL")
    source_name: str = Field(description="来源名称")
    content: Optional[str] = Field(default=None, description="政策内容")
    task_type: str = Field(default="collect", description="任务类型: collect/parse/analyze")
    priority: PolicyPriority = Field(default=PolicyPriority.MEDIUM, description="优先级")


class ImpactReport(BaseModel):
    """影响分析报告"""
    policy_id: str
    impact_level: ImpactLevel
    affected_industries: List[str]
    affected_regions: List[str]
    affected_tax_types: List[str]
    compliance_changes: List[str]
    opportunities: List[str]
    risks: List[str]
    recommendations: List[str]
    generated_at: datetime = Field(default_factory=datetime.now)


class PolicyETLService:
    """
    政策ETL服务
    
    职责：
    1. 采集: 从官方来源抓取政策
    2. 解析: 结构化政策内容
    3. 理解: 提取适用行业/地区/规模
    4. 影响: 评估对企业的影响
    """
    
    def __init__(
        self,
        session: Optional[Session] = None
    ):
        """
        初始化政策ETL服务
        
        Args:
            session: 数据库会话（可选，不提供时自动创建）
        """
        if session is not None:
            self.session = session
        else:
            try:
                self.session = SessionLocal()
            except Exception as e:
                logger.warning(f"⚠️ 无法创建数据库会话: {e}")
                self.session = None
        
        self.entity_patterns = self._compile_entity_patterns()
        
        self.scope_keywords = self._load_scope_keywords()
        
        self.impact_keywords = self._load_impact_keywords()
        
        if not getattr(PolicyETLService, '_initialized', False):
            PolicyETLService._initialized = True
            print("📋 [Policy ETL Service] 初始化完成")
            print("   - 职责: 政策采集、解析、影响分析")
            print(f"   - 实体模式: {len(self.entity_patterns)} 种")
            print(f"   - 范围关键词: {len(self.scope_keywords)} 个")
            print(f"   - 影响关键词: {len(self.impact_keywords)} 个")
    
    def _compile_entity_patterns(self) -> Dict[str, re.Pattern]:
        """编译政策实体提取正则表达式"""
        return {
            "policy_number": re.compile(
                r'(?:公告|通知|办法|规定|决定|批复|函)\s*[〔\[【]?\s*(\d{4})\s*[\]〕】]?\s*第?\s*(\d+)\s*号',
                re.IGNORECASE
            ),
            "date": re.compile(
                r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})日?',
                re.IGNORECASE
            ),
            "money": re.compile(
                r'(?:人民币|RMB|CNY|￥|¥)?\s*[\d,]+(?:\.\d{2})?\s*(?:万|亿)?\s*(?:元|美元|USD)?',
                re.IGNORECASE
            ),
            "percentage": re.compile(
                r'(\d+(?:\.\d+)?)\s*%',
                re.IGNORECASE
            ),
            "tax_rate": re.compile(
                r'(?:税率|征收率|减按)\s*[\d一二三四五六七八九十百千万]+(?:\.\d+)?\s*%',
                re.IGNORECASE
            )
        }
    
    def _load_scope_keywords(self) -> Dict[str, List[str]]:
        """加载范围识别关键词"""
        return {
            "industries": [
                "制造业", "服务业", "建筑业", "批发零售业", "交通运输业",
                "房地产业", "金融业", "信息技术业", "科学研究和技术服务业",
                "租赁和商务服务业", "文化体育和娱乐业", "教育业", "卫生和社会工作",
                "农、林、牧、渔业", "小型微利企业", "高新技术企业", "科技型中小企业"
            ],
            "scales": [
                "大型企业", "中型企业", "小型企业", "微型企业",
                "小规模纳税人", "一般纳税人", "个体工商户"
            ],
            "tax_types": [
                "增值税", "企业所得税", "个人所得税", "消费税",
                "关税", "房产税", "城镇土地使用税", "土地增值税",
                "车船税", "船舶吨税", "印花税", "资源税",
                "环境保护税", "耕地占用税"
            ],
            "regions": [
                "全国", "全国范围内", "各省、自治区、直辖市",
                "北京市", "上海市", "广东省", "浙江省", "江苏省",
                "深圳", "深圳经济特区", "海南", "海南自由贸易港",
                "雄安新区", "粤港澳大湾区", "长三角", "京津冀"
            ]
        }
    
    def _load_impact_keywords(self) -> Dict[str, List[str]]:
        """加载影响分析关键词"""
        return {
            "deadline": [
                "自", "之日起", "施行", "生效", "执行",
                "截止", "截止日期", "最后期限", "过渡期"
            ],
            "obligation": [
                "应当", "必须", "需要", "申报", "缴纳", "报送",
                "备案", "报告", "核算", "保存", "备查"
            ],
            "incentive": [
                "减免", "优惠", "退还", "抵免", "加计扣除",
                "加速折旧", "税额抵免", "税收抵免", "免税", "低税率"
            ],
            "risk": [
                "违法", "违规", "处罚", "罚款", "补缴", "滞纳金",
                "不予抵扣", "不得扣除", "追究责任", "失信"
            ]
        }
    
    async def collect_policy(
        self,
        task: PolicyTask
    ) -> Optional[Dict[str, Any]]:
        """
        采集政策
        
        Args:
            task: 政策采集任务
            
        Returns:
            采集的政策数据
        """
        logger.info(f"采集政策: {task.source_name}")
        
        if not task.content:
            logger.warning("没有政策内容可采集")
            return None
        
        policy_data = {
            "source_url": task.source_url,
            "source_name": task.source_name,
            "content": task.content,
            "collected_at": datetime.now().isoformat()
        }
        
        return policy_data
    
    async def parse_policy(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PolicyAnalysis:
        """
        解析政策
        
        Args:
            content: 政策内容
            metadata: 元数据
            
        Returns:
            政策分析结果
        """
        logger.info("解析政策内容...")
        
        analysis = PolicyAnalysis(
            policy_id=self._generate_policy_id(),
            title=self._extract_title(content),
            summary=self._extract_summary(content),
            scope=self._extract_scope(content),
            key_points=self._extract_key_points(content),
            impact_analysis="",
            compliance_requirements=[],
            related_policies=[]
        )
        
        return analysis
    
    async def analyze_impact(
        self,
        policy_analysis: PolicyAnalysis,
        content: str
    ) -> ImpactReport:
        """
        分析政策影响
        
        Args:
            policy_analysis: 政策分析结果
            content: 原始政策内容
            
        Returns:
            影响分析报告
        """
        logger.info(f"分析政策影响: {policy_analysis.policy_id}")
        
        impact_level = self._determine_impact_level(content, policy_analysis.scope)
        
        affected_industries = policy_analysis.scope.industries
        affected_regions = policy_analysis.scope.regions
        affected_tax_types = policy_analysis.scope.tax_types
        
        compliance_changes = self._extract_compliance_changes(content)
        opportunities = self._extract_opportunities(content)
        risks = self._extract_risks(content)
        recommendations = self._generate_recommendations(impact_level, opportunities, risks)
        
        return ImpactReport(
            policy_id=policy_analysis.policy_id,
            impact_level=impact_level,
            affected_industries=affected_industries,
            affected_regions=affected_regions,
            affected_tax_types=affected_tax_types,
            compliance_changes=compliance_changes,
            opportunities=opportunities,
            risks=risks,
            recommendations=recommendations,
            generated_at=datetime.now()
        )
    
    async def process(
        self,
        task: PolicyTask
    ) -> ImpactReport:
        """
        处理政策任务
        
        Args:
            task: 政策任务
            
        Returns:
            影响分析报告
        """
        logger.info(f"处理政策任务: {task.task_type}")
        
        policy_data = await self.collect_policy(task)
        
        if not policy_data:
            raise ValueError("无法采集政策数据")
        
        analysis = await self.parse_policy(
            policy_data["content"],
            {"source_name": task.source_name}
        )
        
        impact_report = await self.analyze_impact(
            analysis,
            policy_data["content"]
        )
        
        await self.save_to_database(analysis, impact_report)
        
        return impact_report
    
    async def process_batch(
        self,
        tasks: List[PolicyTask]
    ) -> List[ImpactReport]:
        """
        批量处理政策任务
        
        Args:
            tasks: 政策任务列表
            
        Returns:
            影响分析报告列表
        """
        logger.info(f"批量处理政策任务: {len(tasks)} 个")
        
        reports = []
        for task in tasks:
            try:
                report = await self.process(task)
                reports.append(report)
            except Exception as e:
                logger.error(f"处理政策任务失败: {e}")
                continue
        
        return reports
    
    async def save_to_database(
        self,
        analysis: PolicyAnalysis,
        impact_report: ImpactReport
    ) -> UUID:
        """
        保存到数据库
        
        Args:
            analysis: 政策分析
            impact_report: 影响报告
            
        Returns:
            保存的政策ID
        """
        logger.info(f"保存政策到数据库: {analysis.policy_id}")
        
        policy = Policy(
            policy_id=analysis.policy_id,
            title=analysis.title,
            content="",
            summary=analysis.summary,
            source_name="",
            industries=analysis.scope.industries,
            regions=analysis.scope.regions,
            scales=analysis.scope.scales,
            tax_types=analysis.scope.tax_types,
            tags=analysis.key_points,
            status=PolicyStatus.ACTIVE,
            priority=PolicyPriority.MEDIUM,
            meta_info={
                "impact_level": impact_report.impact_level.value,
                "compliance_changes": impact_report.compliance_changes,
                "opportunities": impact_report.opportunities,
                "risks": impact_report.risks
            }
        )
        
        if self.session is not None:
            self.session.add(policy)
            self.session.commit()
            self.session.refresh(policy)
        else:
            logger.warning("⚠️ 数据库会话不可用，跳过保存政策")
        
        return policy.id
    
    def _generate_policy_id(self) -> str:
        """生成政策ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"POL-{timestamp}"
    
    def _extract_title(self, content: str) -> str:
        """提取政策标题"""
        lines = content.split('\n')
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 200:
                return first_line
        return content[:200] if len(content) > 200 else content
    
    def _extract_summary(self, content: str) -> str:
        """提取政策摘要"""
        if len(content) <= 500:
            return content
        
        return content[:500] + "..."
    
    def _extract_scope(self, content: str) -> PolicyScope:
        """提取适用范围"""
        scope = PolicyScope()
        
        for category, keywords in self.scope_keywords.items():
            for keyword in keywords:
                if keyword in content:
                    if category == "industries":
                        scope.industries.append(keyword)
                    elif category == "scales":
                        scope.scales.append(keyword)
                    elif category == "tax_types":
                        scope.tax_types.append(keyword)
                    elif category == "regions":
                        scope.regions.append(keyword)
        
        scope.industries = list(set(scope.industries))
        scope.scales = list(set(scope.scales))
        scope.tax_types = list(set(scope.tax_types))
        scope.regions = list(set(scope.regions))
        
        return scope
    
    def _extract_key_points(self, content: str) -> List[str]:
        """提取要点"""
        key_points = []
        
        patterns = [
            r'(?:一、|（一）|1\.|第一条)[:：]?\s*(.{10,100})',
            r'(?:二、|（二）|2\.|第二条)[:：]?\s*(.{10,100})',
            r'(?:三、|（三）|3\.|第三条)[:：]?\s*(.{10,100})',
            r'(?:重点|关键|核心)[:：]?\s*(.{10,100})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            key_points.extend([m.strip() for m in matches if len(m.strip()) > 10])
        
        return key_points[:10]
    
    def _determine_impact_level(
        self,
        content: str,
        scope: PolicyScope
    ) -> ImpactLevel:
        """确定影响级别"""
        high_impact_count = 0
        medium_impact_count = 0
        
        high_impact_keywords = ["强制", "处罚", "罚款", "违法", "刑事责任"]
        medium_impact_keywords = ["应当", "建议", "鼓励", "优惠"]
        
        for keyword in high_impact_keywords:
            if keyword in content:
                high_impact_count += 1
        
        for keyword in medium_impact_keywords:
            if keyword in content:
                medium_impact_count += 1
        
        if high_impact_count >= 2 or len(scope.industries) >= 5:
            return ImpactLevel.HIGH
        elif high_impact_count >= 1 or medium_impact_count >= 3:
            return ImpactLevel.MEDIUM
        else:
            return ImpactLevel.LOW
    
    def _extract_compliance_changes(self, content: str) -> List[str]:
        """提取合规变化"""
        changes = []
        
        obligation_keywords = ["应当", "必须", "需要", "申报", "缴纳", "报送"]
        
        for keyword in obligation_keywords:
            if keyword in content:
                changes.append(f"新增义务: 涉及{keyword}的相关要求")
        
        return changes[:5]
    
    def _extract_opportunities(self, content: str) -> List[str]:
        """提取机会"""
        opportunities = []
        
        opportunity_keywords = [
            "减免", "优惠", "退还", "抵免", "加计扣除",
            "免税", "低税率", "缓缴", "扣除", "补贴"
        ]
        
        for keyword in opportunity_keywords:
            if keyword in content:
                opportunities.append(f"税收优惠: {keyword}相关政策")
        
        return list(set(opportunities))[:5]
    
    def _extract_risks(self, content: str) -> List[str]:
        """提取风险"""
        risks = []
        
        risk_keywords = [
            "违法", "违规", "处罚", "罚款", "补缴",
            "滞纳金", "不予抵扣", "追究责任", "失信"
        ]
        
        for keyword in risk_keywords:
            if keyword in content:
                risks.append(f"合规风险: {keyword}相关条款")
        
        return list(set(risks))[:5]
    
    def _generate_recommendations(
        self,
        impact_level: ImpactLevel,
        opportunities: List[str],
        risks: List[str]
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if impact_level == ImpactLevel.HIGH:
            recommendations.append("建议立即组织政策学习，制定应对方案")
            recommendations.append("建议尽快评估对现有业务流程的影响")
        
        if opportunities:
            recommendations.append("建议研究相关税收优惠政策，评估适用性")
        
        if risks:
            recommendations.append("建议加强合规审查，防范潜在风险")
        
        recommendations.append("建议持续关注后续配套政策的发布")
        
        return recommendations[:5]
    
    async def search_similar_policies(
        self,
        policy_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索相似政策
        
        Args:
            policy_id: 政策ID
            limit: 返回数量
            
        Returns:
            相似政策列表
        """
        logger.info(f"搜索相似政策: {policy_id}")
        
        if self.session is None:
            logger.warning("⚠️ 数据库会话不可用，无法搜索相似政策")
            return []
        
        stmt = select(Policy).where(
            Policy.policy_id == policy_id,
            Policy.status == PolicyStatus.ACTIVE
        )
        policy = self.session.execute(stmt).scalar_one_or_none()
        
        if not policy:
            return []
        
        similar_stmt = select(Policy).where(
            Policy.id != policy.id,
            Policy.status == PolicyStatus.ACTIVE
        ).order_by(Policy.created_at.desc()).limit(limit)
        
        similar_policies = self.session.execute(similar_stmt).scalars().all()
        
        return [
            {
                "policy_id": p.policy_id,
                "title": p.title,
                "summary": p.summary,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in similar_policies
        ]
