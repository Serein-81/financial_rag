"""
税务结构化输出验证器
负责验证和格式化税务Agent的JSON输出
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field


@dataclass
class ValidationError:
    field: str
    message: str
    value: Any
    expected: str

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    corrected_data: Optional[Dict[str, Any]] = None


class TaxOutputValidator:
    """
    税务结构化输出验证器
    
    验证规则：
    1. 金额字段精度（保留2位小数）
    2. 日期字段格式（ISO 8601）
    3. 枚举字段合法性
    4. 必填字段存在性
    5. 数值字段范围
    6. 逻辑一致性（金额勾稽关系）
    """
    
    # 有效的税种枚举
    VALID_TAX_TYPES = {
        "增值税", "企业所得税", "个人所得税", "消费税", 
        "关税", "土地增值税", "房产税", "印花税",
        "VAT", "CIT", "IIT", "消费税", "资源税"
    }
    
    # 有效的发票类型
    VALID_INVOICE_TYPES = {
        "增值税专用发票", "增值税普通发票", "电子发票",
        "专用发票", "普通发票", "电子普票", "电子专票",
        "invoice_special", "invoice_normal", "electronic_invoice"
    }
    
    # 有效的税率值
    VALID_TAX_RATES = {
        0.0, 0.03, 0.05, 0.06, 0.07, 0.09, 0.10, 
        0.11, 0.12, 0.13, 0.15, 0.20, 0.25, 0.30, 0.45,
        0.0, 3.0, 5.0, 6.0, 7.0, 9.0, 10.0,
        11.0, 12.0, 13.0, 15.0, 20.0, 25.0, 30.0, 45.0
    }
    
    # 必填字段配置
    REQUIRED_FIELDS_BY_TYPE = {
        "invoice": ["invoice_number", "invoice_date", "tax_amount", "total_amount"],
        "tax_return": ["tax_type", "tax_period", "tax_amount", "tax_payer"],
        "general": ["tax_amount", "total_amount"]
    }
    
    # 金额字段列表
    AMOUNT_FIELDS = {
        "tax_amount", "total_amount", "net_amount", "gross_amount",
        "taxable_amount", "deductible_amount", "input_tax", "output_tax",
        "sales_amount", "purchase_amount", "income", "expense",
        "input_vat", "output_vat"
    }
    
    # 日期字段列表
    DATE_FIELDS = {
        "invoice_date", "tax_date", "payment_date", "due_date",
        "declaration_date", "filing_date", "period_start", "period_end"
    }
    
    def __init__(self, strict_mode: bool = True):
        """
        初始化验证器
        
        Args:
            strict_mode: 严格模式，会自动修正部分错误；宽松模式只报告错误
        """
        self.strict_mode = strict_mode
    
    def validate(self, data: Dict[str, Any], doc_type: str = "general") -> ValidationResult:
        """
        验证税务数据结构
        
        Args:
            data: 待验证的数据
            doc_type: 文档类型 (invoice, tax_return, general)
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        corrected_data = data.copy()
        
        # 1. 必填字段验证
        required_errors = self._validate_required_fields(data, doc_type)
        errors.extend(required_errors)
        
        # 2. 金额字段验证
        amount_errors, corrected_data = self._validate_amount_fields(corrected_data)
        errors.extend(amount_errors)
        
        # 3. 日期字段验证
        date_errors, corrected_data = self._validate_date_fields(corrected_data)
        errors.extend(date_errors)
        
        # 4. 枚举字段验证
        enum_errors, corrected_data = self._validate_enum_fields(corrected_data)
        errors.extend(enum_errors)
        
        # 5. 数值范围验证
        range_errors, corrected_data = self._validate_numeric_ranges(corrected_data)
        errors.extend(range_errors)
        
        # 6. 逻辑一致性验证
        logic_errors, warnings = self._validate_logic_consistency(corrected_data)
        errors.extend(logic_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrected_data=corrected_data if self.strict_mode else None
        )
    
    def _validate_required_fields(
        self, 
        data: Dict[str, Any], 
        doc_type: str
    ) -> List[ValidationError]:
        """验证必填字段"""
        errors = []
        required_fields = self.REQUIRED_FIELDS_BY_TYPE.get(doc_type, [])
        
        for field_name in required_fields:
            if field_name not in data or data[field_name] is None or data[field_name] == "":
                errors.append(ValidationError(
                    field=field_name,
                    message=f"必填字段缺失或为空: {field_name}",
                    value=None,
                    expected="非空值"
                ))
        
        return errors
    
    def _validate_amount_fields(
        self, 
        data: Dict[str, Any]
    ) -> Tuple[List[ValidationError], Dict[str, Any]]:
        """验证金额字段"""
        errors = []
        corrected = data.copy()
        
        for field_name, value in data.items():
            if field_name in self.AMOUNT_FIELDS:
                # 检查是否为有效数值
                if value is None or value == "":
                    continue
                
                try:
                    # 转换为浮点数并保留2位小数
                    amount = float(value)
                    corrected[field_name] = round(amount, 2)
                    
                    # 检查是否为负数（某些金额字段允许负数）
                    if amount < 0 and field_name not in ["net_amount", "deductible_amount"]:
                        errors.append(ValidationError(
                            field=field_name,
                            message=f"金额字段不应为负数",
                            value=amount,
                            expected=">= 0"
                        ))
                    
                    # 检查精度损失
                    if abs(amount - round(amount, 2)) > 0.001:
                        errors.append(ValidationError(
                            field=field_name,
                            message=f"金额精度超过2位小数，已自动修正",
                            value=amount,
                            expected="最多2位小数"
                        ))
                
                except (ValueError, TypeError) as e:
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"金额字段格式无效",
                        value=value,
                        expected="数字类型"
                    ))
                    if self.strict_mode:
                        corrected[field_name] = 0.0
        
        return errors, corrected
    
    def _validate_date_fields(
        self, 
        data: Dict[str, Any]
    ) -> Tuple[List[ValidationError], Dict[str, Any]]:
        """验证日期字段"""
        errors = []
        corrected = data.copy()
        
        for field_name, value in data.items():
            if field_name in self.DATE_FIELDS:
                if value is None or value == "":
                    continue
                
                normalized_date = self._normalize_date(value)
                if normalized_date:
                    corrected[field_name] = normalized_date
                else:
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"日期格式无效: {value}",
                        value=value,
                        expected="YYYY-MM-DD 或 YYYY/MM/DD"
                    ))
                    if self.strict_mode:
                        corrected[field_name] = datetime.now().strftime("%Y-%m-%d")
        
        return errors, corrected
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """标准化日期格式"""
        if not date_str:
            return None
        
        # 如果已经是 ISO 格式
        if re.match(r"^\d{4}-\d{2}-\d{2}", str(date_str)):
            return str(date_str)[:10]
        
        # 尝试解析 YYYY/MM/DD
        match = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})", str(date_str))
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        
        # 尝试解析中文格式 YYYY年MM月DD日
        match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日", str(date_str))
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        
        # 尝试解析其他常见格式
        for fmt in ["%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"]:
            try:
                dt = datetime.strptime(str(date_str), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return None
    
    def _validate_enum_fields(
        self, 
        data: Dict[str, Any]
    ) -> Tuple[List[ValidationError], Dict[str, Any]]:
        """验证枚举字段"""
        errors = []
        corrected = data.copy()
        
        # 验证税种
        if "tax_type" in data:
            tax_type = data["tax_type"]
            if tax_type not in self.VALID_TAX_TYPES:
                errors.append(ValidationError(
                    field="tax_type",
                    message=f"无效的税种类型: {tax_type}",
                    value=tax_type,
                    expected=f"可选值: {', '.join(list(self.VALID_TAX_TYPES)[:5])}..."
                ))
                if self.strict_mode:
                    corrected["tax_type"] = "未知"
        
        # 验证发票类型
        if "invoice_type" in data:
            invoice_type = data["invoice_type"]
            if invoice_type not in self.VALID_INVOICE_TYPES:
                errors.append(ValidationError(
                    field="invoice_type",
                    message=f"无效的发票类型: {invoice_type}",
                    value=invoice_type,
                    expected="增值税专用发票/增值税普通发票/电子发票"
                ))
                if self.strict_mode:
                    corrected["invoice_type"] = "普通发票"
        
        return errors, corrected
    
    def _validate_numeric_ranges(
        self, 
        data: Dict[str, Any]
    ) -> Tuple[List[ValidationError], Dict[str, Any]]:
        """验证数值范围"""
        errors = []
        corrected = data.copy()
        
        # 验证税率范围
        if "tax_rate" in data:
            rate = data["tax_rate"]
            try:
                rate_float = float(rate)
                if rate_float < 0 or rate_float > 100:
                    errors.append(ValidationError(
                        field="tax_rate",
                        message=f"税率超出有效范围: {rate_float}",
                        value=rate_float,
                        expected="0-100%"
                    ))
                    if self.strict_mode:
                        corrected["tax_rate"] = round(rate_float / 100, 4) if rate_float > 1 else rate_float
            except (ValueError, TypeError):
                pass
        
        # 验证金额为0的情况（针对某些必填字段）
        zero_amount_fields = ["tax_amount", "total_amount"]
        for field_name in zero_amount_fields:
            if field_name in data:
                try:
                    if float(data[field_name]) == 0:
                        corrected.setdefault("_warnings", []).append(f"字段 {field_name} 金额为0")
                except (ValueError, TypeError):
                    pass
        
        return errors, corrected
    
    def _validate_logic_consistency(
        self, 
        data: Dict[str, Any]
    ) -> Tuple[List[ValidationError], List[str]]:
        """验证逻辑一致性（金额勾稽关系）"""
        errors = []
        warnings = []
        
        # 验证价税合计 = 金额 + 税额
        if all(k in data for k in ["total_amount", "tax_amount", "taxable_amount"]):
            try:
                total = float(data["total_amount"])
                tax = float(data["tax_amount"])
                taxable = float(data["taxable_amount"])
                
                calculated_total = round(taxable + tax, 2)
                if abs(total - calculated_total) > 0.01:
                    errors.append(ValidationError(
                        field="amount_consistency",
                        message=f"金额勾稽关系不一致: 价税合计({total}) ≠ 金额({taxable}) + 税额({tax})",
                        value={"total": total, "taxable": taxable, "tax": tax},
                        expected=f"金额 + 税额 = {calculated_total}"
                    ))
            except (ValueError, TypeError):
                pass
        
        # 验证税额 = 金额 × 税率
        if all(k in data for k in ["tax_amount", "taxable_amount", "tax_rate"]):
            try:
                tax = float(data["tax_amount"])
                taxable = float(data["taxable_amount"])
                rate = float(data["tax_rate"])
                
                # 统一税率为小数形式
                if rate > 1:
                    rate = rate / 100
                
                calculated_tax = round(taxable * rate, 2)
                if abs(tax - calculated_tax) > 0.02:
                    errors.append(ValidationError(
                        field="tax_calculation",
                        message=f"税额计算不一致: 税额({tax}) ≠ 金额({taxable}) × 税率({rate*100}%)",
                        value={"tax": tax, "taxable": taxable, "rate": rate},
                        expected=f"金额 × 税率 = {calculated_tax}"
                    ))
            except (ValueError, TypeError):
                pass
        
        # 验证进项销项逻辑
        if all(k in data for k in ["input_tax", "output_tax"]):
            try:
                input_tax = float(data["input_tax"])
                output_tax = float(data["output_tax"])
                
                if input_tax < 0:
                    errors.append(ValidationError(
                        field="input_tax_sign",
                        message="进项税额不应为负数",
                        value=input_tax,
                        expected=">= 0"
                    ))
                
                if output_tax < 0:
                    errors.append(ValidationError(
                        field="output_tax_sign",
                        message="销项税额不应为负数",
                        value=output_tax,
                        expected=">= 0"
                    ))
            except (ValueError, TypeError):
                pass
        
        # 检查金额为0的警告
        if "tax_amount" in data:
            try:
                if float(data["tax_amount"]) == 0:
                    warnings.append("税额为0，请确认是否为免税业务")
            except (ValueError, TypeError):
                pass
        
        return errors, warnings
    
    def validate_json_string(self, json_str: str, doc_type: str = "general") -> ValidationResult:
        """
        验证JSON字符串
        
        Args:
            json_str: JSON字符串
            doc_type: 文档类型
            
        Returns:
            验证结果
        """
        try:
            data = json.loads(json_str)
            return self.validate(data, doc_type)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field="json_format",
                    message=f"JSON格式错误: {str(e)}",
                    value=json_str,
                    expected="有效的JSON格式"
                )]
            )


def format_tax_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    格式化税务输出数据
    
    确保所有金额字段保留2位小数，日期字段为ISO格式
    
    Args:
        data: 原始数据
        
    Returns:
        格式化后的数据
    """
    validator = TaxOutputValidator(strict_mode=True)
    result = validator.validate(data)
    return result.corrected_data if result.corrected_data else data


def extract_json_from_llm_response(response: str) -> Optional[Dict[str, Any]]:
    """
    从LLM响应中提取JSON
    
    处理LLM可能返回的markdown代码块格式
    
    Args:
        response: LLM响应文本
        
    Returns:
        解析后的JSON数据，失败返回None
    """
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # 尝试从markdown代码块中提取
    json_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(json_pattern, response)
    
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    
    # 尝试提取 {...} 格式
    brace_pattern = r"\{[\s\S]*\}"
    match = re.search(brace_pattern, response)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    return None
