"""
税务报告相关 Pydantic Schema 定义
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class TaxTypeEnum(str, Enum):
    """税务类型枚举（大小写不敏感）"""
    VAT = "vat"                      # 增值税
    INCOME = "income"                # 企业所得税
    PERSONAL = "personal"            # 个人所得税
    CONSUMPTION = "consumption"      # 消费税
    BEHAVIOR = "behavior"           # 行为税
    COMPREHENSIVE = "comprehensive"  # 综合税务
    
    def __new__(cls, value):
        # 大小写不敏感：自动转换为小写
        obj = str.__new__(cls)
        obj._value_ = value.lower() if isinstance(value, str) else value
        return obj
    
    @classmethod
    def _missing_(cls, value):
        # 当解析失败时，尝试大小写不敏感匹配
        for member in cls:
            if member.value.lower() == str(value).lower():
                return member
        return None


class TaxReportStatusEnum(str, Enum):
    """税务报告状态枚举"""
    PENDING = "pending"              # 待处理
    PROCESSING = "processing"        # 处理中
    COMPLETED = "completed"          # 已完成
    FAILED = "failed"                # 失败
    PENDING_REVIEW = "pending_review"  # 待审核


class RiskLevelEnum(str, Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KeyMetricsSchema(BaseModel):
    """税务关键指标"""
    input_tax: Optional[float] = Field(None, description="进项税额")
    output_tax: Optional[float] = Field(None, description="销项税额")
    taxable_sales: Optional[float] = Field(None, description="应税销售额")
    tax_amount: Optional[float] = Field(None, description="税额")
    tax_rate: Optional[float] = Field(None, description="税率")
    total_income: Optional[float] = Field(None, description="总收入")
    deductible_amount: Optional[float] = Field(None, description="可抵扣金额")
    tax_burden_rate: Optional[float] = Field(None, description="税负率")


class TaxIssueSchema(BaseModel):
    """税务问题"""
    id: str = Field(..., description="问题ID")
    severity: RiskLevelEnum = Field(..., description="严重程度")
    category: str = Field(..., description="问题类别")
    description: str = Field(..., description="问题描述")
    evidence: List[str] = Field(default_factory=list, description="证据列表")
    legal_basis: Optional[List[str]] = Field(None, description="法律依据")
    recommendation: Optional[str] = Field(None, description="建议")
    confidence: float = Field(..., ge=0, le=1, description="置信度")


class TaxValidationResultSchema(BaseModel):
    """税务逻辑验证结果"""
    total_errors: int = Field(0, description="错误总数")
    high_severity: int = Field(0, description="高严重程度错误数")
    medium_severity: int = Field(0, description="中等严重程度错误数")
    low_severity: int = Field(0, description="低严重程度错误数")
    pass_validation: bool = Field(True, description="是否通过验证")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误详情")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="警告详情")
    reconciliation_issues: List[Dict[str, Any]] = Field(default_factory=list, description="勾稽关系问题")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list, description="异常指标")


class RAGReferenceSchema(BaseModel):
    """RAG参考资料"""
    finding_id: Optional[str] = Field(None, description="关联的发现ID")
    content: str = Field(..., description="参考内容")
    source: str = Field(..., description="来源文档")
    relevance: float = Field(..., ge=0, le=1, description="相关性评分")


class TaxIndicatorSchema(BaseModel):
    """税务指标"""
    name: str = Field(..., description="指标名称")
    value: float = Field(..., description="指标值")
    formatted: str = Field(..., description="格式化值")
    status: str = Field(..., description="状态 (normal/warning/high)")
    benchmark: Optional[str] = Field(None, description="基准值")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")


class TaxReportCreate(BaseModel):
    """创建税务报告请求"""
    tax_type: Optional[TaxTypeEnum] = Field(None, description="税务类型（可选，自动识别）")
    tax_period_year: Optional[int] = Field(None, ge=2000, le=2100, description="税务年度")
    tax_period_month: Optional[int] = Field(None, ge=1, le=12, description="税务月份")
    description: Optional[str] = Field(None, description="报告描述")

    class Config:
        json_schema_extra = {
            "example": {
                "tax_type": "vat",
                "tax_period_year": 2024,
                "tax_period_month": 3,
                "description": "2024年3月增值税申报"
            }
        }


class TaxReportUploadResponse(BaseModel):
    """税务报告上传响应"""
    id: str = Field(..., description="税务报告ID")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    file_size_mb: float = Field(..., description="文件大小（MB）")
    file_type: str = Field(..., description="文件类型")
    status: TaxReportStatusEnum = Field(..., description="处理状态")
    created_at: datetime = Field(..., description="创建时间")
    message: Optional[str] = Field(None, description="状态消息")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "税务报告_2024_03.pdf",
                "file_size": 1048576,
                "file_size_mb": 1.0,
                "file_type": "pdf",
                "status": "pending",
                "created_at": "2024-03-25T10:00:00Z",
                "message": "文件上传成功，等待处理"
            }
        }


class TaxReportResponse(BaseModel):
    """税务报告详情响应"""
    id: str = Field(..., description="税务报告ID")
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    filename: str = Field(..., description="文件名")
    original_filename: str = Field(..., description="原始文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小（字节）")
    file_size_mb: float = Field(..., description="文件大小（MB）")
    
    tax_type: Optional[TaxTypeEnum] = Field(None, description="税务类型")
    tax_period_year: Optional[int] = Field(None, description="税务年度")
    tax_period_month: Optional[int] = Field(None, description="税务月份")
    
    status: TaxReportStatusEnum = Field(..., description="处理状态")
    processing_message: Optional[str] = Field(None, description="处理状态消息")
    
    confidence_score: Optional[float] = Field(None, description="置信度")
    risk_score: Optional[int] = Field(None, description="风险评分")
    risk_level: Optional[RiskLevelEnum] = Field(None, description="风险等级")
    
    needs_human_review: bool = Field(False, description="是否需要人工审核")
    review_request_id: Optional[str] = Field(None, description="审核请求ID")
    
    key_metrics: Optional[KeyMetricsSchema] = Field(None, description="关键指标")
    
    issues: List[TaxIssueSchema] = Field(default_factory=list, description="发现的问题")
    
    tax_validation: Optional[TaxValidationResultSchema] = Field(None, description="税务逻辑验证结果")
    
    rag_references: List[RAGReferenceSchema] = Field(default_factory=list, description="RAG参考资料")
    
    indicators: List[TaxIndicatorSchema] = Field(default_factory=list, description="税务指标")
    
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        from_attributes = True


class TaxReportListResponse(BaseModel):
    """税务报告列表响应"""
    items: List[TaxReportResponse] = Field(..., description="报告列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")


class TaxReportStatusResponse(BaseModel):
    """税务报告状态响应"""
    id: str = Field(..., description="报告ID")
    status: TaxReportStatusEnum = Field(..., description="状态")
    processing_message: Optional[str] = Field(None, description="处理消息")
    progress_percent: int = Field(0, ge=0, le=100, description="处理进度百分比")
    needs_human_review: bool = Field(False, description="是否需要人工审核")
    estimated_completion: Optional[datetime] = Field(None, description="预计完成时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "processing_message": "正在执行税务逻辑验证...",
                "progress_percent": 75,
                "needs_human_review": False,
                "estimated_completion": "2024-03-25T10:05:00Z"
            }
        }


class ManualTaxReportInput(BaseModel):
    """手动录入税务报告输入"""
    tax_type: TaxTypeEnum = Field(..., description="税务类型")
    fiscal_year: int = Field(..., ge=2000, le=2100, description="财务年度")
    fiscal_period: Optional[str] = Field(None, description="财务期间（如：2024-Q1, 2024-03）")
    
    company_name: Optional[str] = Field(None, description="公司名称")
    tax_id: Optional[str] = Field(None, description="纳税人识别号")
    
    revenue: float = Field(0, ge=0, description="营业收入")
    taxable_sales: float = Field(0, ge=0, description="应税销售额")
    tax_free_sales: float = Field(0, ge=0, description="免税销售额")
    
    input_tax: float = Field(0, ge=0, description="进项税额")
    output_tax: float = Field(0, ge=0, description="销项税额")
    vat_rate: float = Field(0.13, ge=0, le=1, description="增值税率")
    
    total_expenses: float = Field(0, ge=0, description="总支出")
    deductible_expenses: float = Field(0, ge=0, description="可抵扣支出")
    
    taxable_income: float = Field(0, ge=0, description="应纳税所得额")
    corporate_tax_rate: float = Field(0.25, ge=0, le=1, description="企业所得税率")
    
    total_payroll: float = Field(0, ge=0, description="工资薪金总额")
    
    total_invoices: int = Field(0, ge=0, description="发票总数")
    input_invoice_count: int = Field(0, ge=0, description="进项发票数")
    output_invoice_count: int = Field(0, ge=0, description="销项发票数")
    
    financial_data_id: Optional[str] = Field(None, description="关联财务数据ID")
    
    notes: Optional[str] = Field(None, description="备注")
    run_analysis: bool = Field(True, description="是否立即运行AI分析")

    class Config:
        json_schema_extra = {
            "example": {
                "tax_type": "vat",
                "fiscal_year": 2024,
                "fiscal_period": "2024-03",
                "company_name": "示例公司",
                "revenue": 1000000,
                "taxable_sales": 850000,
                "tax_free_sales": 150000,
                "input_tax": 85000,
                "output_tax": 110500,
                "vat_rate": 0.13,
                "total_invoices": 50,
                "financial_data_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class ManualTaxReportCreate(BaseModel):
    """手动创建税务报告请求"""
    input_data: ManualTaxReportInput = Field(..., description="录入数据")

    class Config:
        json_schema_extra = {
            "example": {
                "input_data": {
                    "tax_type": "vat",
                    "fiscal_year": 2024,
                    "fiscal_period": "2024-03",
                    "company_name": "示例公司",
                    "revenue": 1000000,
                    "taxable_sales": 850000,
                    "tax_free_sales": 150000,
                    "input_tax": 85000,
                    "output_tax": 110500,
                    "vat_rate": 0.13,
                    "run_analysis": True
                }
            }
        }


class TaxReportFilter(BaseModel):
    """税务报告筛选条件"""
    status: Optional[TaxReportStatusEnum] = Field(None, description="状态筛选")
    tax_type: Optional[TaxTypeEnum] = Field(None, description="税务类型筛选")
    risk_level: Optional[RiskLevelEnum] = Field(None, description="风险等级筛选")
    needs_review: Optional[bool] = Field(None, description="需要审核筛选")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    keyword: Optional[str] = Field(None, description="关键词搜索（文件名）")


class TaxReportBatchUploadRequest(BaseModel):
    """批量上传税务报告请求"""
    reports: List[TaxReportCreate] = Field(..., min_items=1, description="报告列表")

    class Config:
        json_schema_extra = {
            "example": {
                "reports": [
                    {"tax_type": "vat", "tax_period_year": 2024, "tax_period_month": 1},
                    {"tax_type": "income", "tax_period_year": 2023, "tax_period_month": 12}
                ]
            }
        }


class TaxReportProcessingCallback(BaseModel):
    """税务报告处理回调（内部使用）"""
    report_id: str = Field(..., description="报告ID")
    stage: str = Field(..., description="处理阶段")
    status: str = Field(..., description="状态")
    message: Optional[str] = Field(None, description="消息")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="时间戳")
