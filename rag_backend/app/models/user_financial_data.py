"""
用户财务数据模型
用于存储用户的企业财务信息，支持税务查询和分析
"""

import uuid
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text, Boolean, func, Date, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserFinancialData(Base):
    """
    用户财务数据模型
    
    存储用户的企业财务信息，包括收入、支出、税务数据等
    支持年度、季度、月度等多种周期类型
    """
    __tablename__ = "user_financial_data"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 用户和租户信息（租户隔离）
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    
    # 财务年度（保留用于兼容和快速查询）
    fiscal_year = Column(Integer, nullable=False, index=True)
    
    # 周期类型: yearly/quarterly/monthly
    period_type = Column(String(20), default="yearly", nullable=False, index=True, comment="周期类型")
    
    # 周期开始和结束日期
    period_start = Column(Date, nullable=False, index=True, comment="周期开始日期")
    period_end = Column(Date, nullable=False, index=True, comment="周期结束日期")

    __table_args__ = (
        Index('ix_user_financial_data_lookup', 'user_id', 'tenant_id', 'fiscal_year', 'period_type'),
        Index('ix_user_financial_data_tenant_year', 'tenant_id', 'fiscal_year'),
        Index('ix_user_financial_data_user_year', 'user_id', 'fiscal_year'),
    )

    # 收入数据
    total_revenue = Column(Float, default=0.0, comment="总收入")
    taxable_sales = Column(Float, default=0.0, comment="应税销售额")
    tax_free_sales = Column(Float, default=0.0, comment="免税销售额")
    
    # 支出和成本
    total_expenses = Column(Float, default=0.0, comment="总支出")
    deductible_expenses = Column(Float, default=0.0, comment="可抵扣支出")
    non_deductible_expenses = Column(Float, default=0.0, comment="不可抵扣支出")
    
    # 税务数据
    input_tax = Column(Float, default=0.0, comment="进项税额")
    output_tax = Column(Float, default=0.0, comment="销项税额")
    vat_rate = Column(Float, default=0.13, comment="增值税率")
    
    # 企业所得税相关
    taxable_income = Column(Float, default=0.0, comment="应纳税所得额")
    corporate_tax_rate = Column(Float, default=0.25, comment="企业所得税率")
    is_small_enterprise = Column(Boolean, default=False, comment="是否小微企业")
    
    # 个人所得税相关（工资薪金等）
    total_payroll = Column(Float, default=0.0, comment="工资薪金总额")
    special_deductions = Column(Float, default=0.0, comment="专项附加扣除")
    
    # 成本结构明细（JSONB格式）
    cost_breakdown = Column(JSONB, nullable=True, comment="成本结构明细")
    
    # 发票统计
    total_invoices = Column(Integer, default=0, comment="发票总数")
    input_invoice_count = Column(Integer, default=0, comment="进项发票数")
    output_invoice_count = Column(Integer, default=0, comment="销项发票数")
    
    # 数据状态
    data_status = Column(String(20), default="draft", comment="数据状态: draft/confirmed/final")
    is_current = Column(Boolean, default=True, comment="是否为最新数据")
    
    # 数据来源
    data_source = Column(String(50), default="manual", comment="数据来源: manual/upload/auto")
    source_file_id = Column(UUID(as_uuid=True), nullable=True, comment="来源文件ID")
    
    # 备注和说明
    notes = Column(Text, nullable=True, comment="备注说明")
    
    # 审核信息
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", foreign_keys=[user_id], backref="financial_data")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<UserFinancialData(id={self.id}, fiscal_year={self.fiscal_year}, user_id={self.user_id})>"
    
    @property
    def calculated_vat(self):
        """计算应缴增值税"""
        return round(self.output_tax - self.input_tax, 2)
    
    @property
    def calculated_corporate_tax(self):
        """计算应缴企业所得税"""
        if self.is_small_enterprise and self.taxable_income <= 1000000:
            effective_rate = 0.05
        elif self.is_small_enterprise and self.taxable_income <= 3000000:
            effective_rate = 0.05
        else:
            effective_rate = self.corporate_tax_rate
        return round(self.taxable_income * effective_rate, 2)
    
    @property
    def tax_burden_rate(self):
        """计算整体税负率"""
        if self.total_revenue > 0:
            total_tax = self.calculated_vat + self.calculated_corporate_tax
            return round(total_tax / self.total_revenue * 100, 2)
        return 0.0


class FinancialDataHistory(Base):
    """
    财务数据修改历史
    记录用户财务数据的修改历史
    """
    __tablename__ = "financial_data_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联的财务数据
    financial_data_id = Column(UUID(as_uuid=True), ForeignKey("user_financial_data.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 修改信息
    modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    modified_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    
    # 修改内容快照
    previous_data = Column(JSONB, nullable=False, comment="修改前的数据")
    new_data = Column(JSONB, nullable=False, comment="修改后的数据")
    
    # 修改说明
    change_reason = Column(Text, nullable=True, comment="修改原因")
    
    # 关系
    financial_data = relationship("UserFinancialData", backref="history")
    modifier = relationship("User", backref="financial_modifications")
    
    def __repr__(self):
        return f"<FinancialDataHistory(id={self.id}, financial_data_id={self.financial_data_id})>"
