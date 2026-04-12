"""
税务文件内容验证器
用于验证上传的文件是否包含有效的税务数据
"""

import re
import logging
from typing import Tuple, Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TaxValidationResult:
    """税务文件验证结果"""
    is_valid: bool
    confidence: float  # 0.0 - 1.0
    found_keywords: List[str]
    missing_indicators: List[str]
    suggestions: List[str]
    extracted_info: Dict[str, Any]
    error_message: Optional[str] = None


class TaxFileValidator:
    """
    税务文件内容验证器
    
    验证功能：
    1. 检查文件是否包含税务相关的关键词
    2. 验证是否存在税务数据特征（金额、日期、税种等）
    3. 评估文件是否为有效税务文件
    4. 提供详细的验证报告和修改建议
    """

    # 税务相关关键词（中文）
    TAX_KEYWORDS_CN = {
        # 税种名称
        "增值税", "企业所得税", "个人所得税", "消费税", "关税", "土地增值税",
        "房产税", "印花税", "资源税", "城市维护建设税", "教育费附加", "地方教育附加",
        "VAT", "CIT", "IIT", "消费税", "增值税专用发票", "增值税普通发票",
        
        # 税务专业术语
        "进项税额", "销项税额", "应纳税额", "应补（退）税额", "期初余额", "期末余额",
        "进项转出", "进项税额转出", "不得抵扣", "免抵退", "留抵税额",
        "销售额", "销项税额", "进项税额", "进项税", "销项税", "应交税金",
        "税务", "申报", "纳税", "税率", "税额", "发票", "抵扣",
        
        # 财务报表相关
        "利润表", "资产负债表", "现金流量表", "主营业务收入", "主营业务成本",
        "期间费用", "管理费用", "销售费用", "财务费用", "营业利润", "利润总额",
        
        # 发票相关
        "发票号码", "发票代码", "开票日期", "购货单位", "销货单位", "价税合计",
        "货物或应税劳务", "规格型号", "单位", "数量", "单价", "金额", "税率",
        
        # 申报相关
        "申报日期", "申报期", "所属期", "税款所属期", "填表日期", "申报方式",
        "一般纳税人", "小规模纳税人", "一般计税", "简易计税"
    }

    # 税务关键词（英文）
    TAX_KEYWORDS_EN = {
        "tax", "vat", "invoice", "receipt", "taxable", "deductible",
        "input_tax", "output_tax", "tax_amount", "tax_rate",
        "sales", "purchase", "revenue", "income", "expense",
        "profit", "loss", "balance_sheet", "income_statement",
        "tax_return", "declaration", "filing", "payment",
        "credit", "debit", "accounting", "financial"
    }

    # 税务指标模式（用于提取信息）
    TAX_PATTERNS = {
        # 金额模式（支持中文和英文）
        "currency_cn": r"(?:¥|人民币|元)(?:\s*)(\d+(?:,\d{3})*(?:\.\d{2})?)",
        "currency_en": r"(?:USD|US\$|\$)(?:\s*)(\d+(?:,\d{3})*(?:\.\d{2})?)",
        "tax_amount": r"(?:税额|税额合计|应纳税额)(?:\s*:?\s*)(?:¥\s*)?(\d+(?:,\d{3})*(?:\.\d{2})?)",
        "sales_amount": r"(?:销售额|销售金额)(?:\s*:?\s*)(?:¥\s*)?(\d+(?:,\d{3})*(?:\.\d{2})?)",
        "purchase_amount": r"(?:采购额|购买金额|进项)(?:\s*:?\s*)(?:¥\s*)?(\d+(?:,\d{3})*(?:\.\d{2})?)",
        
        # 发票号模式
        "invoice_number": r"(?:发票号(?:码)?|invoice\s*no\.?)(?:\s*:?\s*)([A-Z0-9]{8,20})",
        "tax_id": r"(?:纳税人识别号|税号|tax\s*id)(?:\s*:?\s*)([0-9A-Z]{15,20})",
        
        # 日期模式
        "invoice_date": r"(?:开票日期|发票日期|date)(?:\s*:?\s*)(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
        "tax_period": r"(?:所属期|申报期|period)(?:\s*:?\s*)(\d{4}年?\d{1,2}月?)",
        
        # 税率模式
        "tax_rate": r"(?:税率|rate)(?:\s*:?\s*)(\d+(?:\.\d+)?%)",
    }

    # 低置信度关键词（可能误判）
    LOW_CONFIDENCE_KEYWORDS = {
        "发票", "税务", "申报", "财务", "会计",
        "收入", "支出", "金额", "成本", "利润"
    }

    # 高置信度关键词（强烈表明是税务文件）
    HIGH_CONFIDENCE_KEYWORDS = {
        "增值税", "进项税额", "销项税额", "发票号码",
        "纳税人识别号", "应纳税额", "税务申报", "VAT",
        "input_tax", "output_tax", "tax_return"
    }

    def __init__(self):
        """初始化验证器"""
        logger.info("🔍 [税务文件验证器] 初始化完成")

    async def validate_with_ocr_fallback(
        self,
        content: str,
        file_bytes: Optional[bytes] = None,
        file_type: str = "unknown"
    ) -> TaxValidationResult:
        """
        验证文件内容，如果文本过少则尝试 OCR
        
        Args:
            content: 文件的文本内容
            file_bytes: 原始文件字节（用于 OCR）
            file_type: 文件类型
            
        Returns:
            TaxValidationResult: 验证结果
        """
        if not content or len(content.strip()) < 50:
            if file_bytes and file_type == "pdf":
                logger.info("🔍 [税务文件验证器] 文本内容过少，尝试 OCR...")
                try:
                    ocr_content = await self._extract_text_from_pdf_ocr(file_bytes)
                    if ocr_content:
                        logger.info(f"🔍 [税务文件验证器] OCR 提取成功: {len(ocr_content)} 字符")
                        return await self.validate(ocr_content, file_type)
                except Exception as e:
                    logger.error(f"❌ [税务文件验证器] OCR 提取失败: {str(e)}")
            
            return TaxValidationResult(
                is_valid=False,
                confidence=0.0,
                found_keywords=[],
                missing_indicators=["文件内容为空或无法提取文本"],
                suggestions=["请确保文件包含可识别的文本内容", "如果是扫描件，建议上传清晰的图片"],
                extracted_info={},
                error_message="无法从文件中提取文本内容"
            )
        
        return await self.validate(content, file_type)
    
    async def _extract_text_from_pdf_ocr(self, file_bytes: bytes) -> str:
        """使用 OCR 从 PDF 中提取文本"""
        try:
            import fitz
            from PIL import Image
            import pytesseract
            import io
            
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
            all_text = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # 如果页面文本过少，使用 OCR
                if len(page_text.strip()) < 50:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_bytes))
                    ocr_text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                    if ocr_text.strip():
                        all_text.append(ocr_text)
                else:
                    all_text.append(page_text)
            
            doc.close()
            return "\n\n".join(all_text)
            
        except ImportError as e:
            logger.error(f"OCR 依赖缺失: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"PDF OCR 提取失败: {str(e)}")
            return ""

    async def validate(
        self,
        content: str,
        file_type: str = "unknown"
    ) -> TaxValidationResult:
        """
        验证文件内容是否为有效的税务文件
        
        Args:
            content: 文件的文本内容
            file_type: 文件类型 (pdf, excel, csv等)
            
        Returns:
            TaxValidationResult: 验证结果
        """
        try:
            if not content or len(content.strip()) < 50:
                return TaxValidationResult(
                    is_valid=False,
                    confidence=0.0,
                    found_keywords=[],
                    missing_indicators=["文件内容过短或为空"],
                    suggestions=["请上传完整的税务文件"],
                    extracted_info={},
                    error_message="文件内容为空或过短，无法进行税务验证"
                )

            # 统计找到的关键词
            found_cn = self._find_keywords(content, self.TAX_KEYWORDS_CN)
            found_en = self._find_keywords(content, self.TAX_KEYWORDS_EN)
            found_keywords = found_cn + found_en

            # 检查税务指标模式
            extracted_info = self._extract_tax_info(content)

            # 计算置信度
            confidence = self._calculate_confidence(
                found_keywords=found_keywords,
                extracted_info=extracted_info,
                content_length=len(content)
            )

            # 检查关键指标
            missing_indicators = self._check_missing_indicators(
                found_keywords=found_keywords,
                extracted_info=extracted_info
            )

            # 生成建议
            suggestions = self._generate_suggestions(
                confidence=confidence,
                missing_indicators=missing_indicators,
                found_keywords=found_keywords
            )

            # 判断是否有效
            is_valid = self._is_valid_tax_file(
                confidence=confidence,
                missing_indicators=missing_indicators
            )

            logger.info(
                f"🔍 [税务文件验证器] 验证完成: "
                f"is_valid={is_valid}, confidence={confidence:.2%}, "
                f"found_keywords={len(found_keywords)}, "
                f"extracted_fields={len(extracted_info)}"
            )

            return TaxValidationResult(
                is_valid=is_valid,
                confidence=confidence,
                found_keywords=found_keywords[:10],  # 最多返回10个关键词
                missing_indicators=missing_indicators,
                suggestions=suggestions,
                extracted_info=extracted_info,
                error_message=None if is_valid else self._generate_error_message(missing_indicators)
            )

        except Exception as e:
            logger.error(f"❌ [税务文件验证器] 验证失败: {str(e)}")
            return TaxValidationResult(
                is_valid=False,
                confidence=0.0,
                found_keywords=[],
                missing_indicators=["验证过程出错"],
                suggestions=["请重新上传文件或联系管理员"],
                extracted_info={},
                error_message=f"文件验证失败: {str(e)}"
            )

    def _find_keywords(self, content: str, keywords: set) -> List[str]:
        """查找文本中包含的关键词"""
        found = []
        content_lower = content.lower()
        
        for keyword in keywords:
            if keyword.lower() in content_lower:
                found.append(keyword)
        
        return list(set(found))

    def _extract_tax_info(self, content: str) -> Dict[str, Any]:
        """提取税务相关信息"""
        extracted = {}
        
        # 提取金额信息
        currency_cn = re.findall(self.TAX_PATTERNS["currency_cn"], content)
        if currency_cn:
            amounts = [float(c.replace(',', '')) for c in currency_cn]
            extracted["amounts"] = amounts
            extracted["total_amount"] = sum(amounts)
            extracted["max_amount"] = max(amounts) if amounts else 0

        # 提取发票号
        invoice_numbers = re.findall(self.TAX_PATTERNS["invoice_number"], content, re.IGNORECASE)
        if invoice_numbers:
            extracted["invoice_numbers"] = invoice_numbers[:5]  # 最多5个

        # 提取纳税人识别号
        tax_ids = re.findall(self.TAX_PATTERNS["tax_id"], content, re.IGNORECASE)
        if tax_ids:
            extracted["taxpayer_ids"] = tax_ids

        # 提取日期信息
        invoice_dates = re.findall(self.TAX_PATTERNS["invoice_date"], content)
        if invoice_dates:
            extracted["invoice_dates"] = invoice_dates[:5]

        # 提取税务期间
        tax_periods = re.findall(self.TAX_PATTERNS["tax_period"], content)
        if tax_periods:
            extracted["tax_periods"] = tax_periods

        # 提取税率
        tax_rates = re.findall(self.TAX_PATTERNS["tax_rate"], content)
        if tax_rates:
            rates = [float(r.rstrip('%')) / 100 for r in tax_rates]
            extracted["tax_rates"] = rates
            extracted["unique_rates"] = list(set(rates))

        # 检查是否包含金额字段
        has_tax_amount = bool(re.search(self.TAX_PATTERNS["tax_amount"], content))
        has_sales_amount = bool(re.search(self.TAX_PATTERNS["sales_amount"], content))
        has_purchase_amount = bool(re.search(self.TAX_PATTERNS["purchase_amount"], content))
        
        extracted["has_tax_amount_field"] = has_tax_amount
        extracted["has_sales_amount_field"] = has_sales_amount
        extracted["has_purchase_amount_field"] = has_purchase_amount

        return extracted

    def _calculate_confidence(
        self,
        found_keywords: List[str],
        extracted_info: Dict[str, Any],
        content_length: int
    ) -> float:
        """计算文件为税务文件的置信度"""
        confidence = 0.0
        
        # 1. 基于关键词数量 (最高40分)
        keyword_score = min(len(found_keywords) / 20, 1.0) * 40
        confidence += keyword_score
        
        # 2. 高置信度关键词 (最高30分)
        high_conf_count = sum(1 for kw in found_keywords if kw in self.HIGH_CONFIDENCE_KEYWORDS)
        high_conf_score = min(high_conf_count / 3, 1.0) * 30
        confidence += high_conf_score
        
        # 3. 提取的信息完整性 (最高20分)
        info_score = 0
        if extracted_info.get("amounts"):
            info_score += 5
        if extracted_info.get("invoice_numbers"):
            info_score += 5
        if extracted_info.get("taxpayer_ids"):
            info_score += 5
        if extracted_info.get("tax_rates"):
            info_score += 5
        confidence += min(info_score, 20)
        
        # 4. 内容长度合理性 (最高10分)
        if 100 < content_length < 1000000:  # 100字符到1MB文本
            confidence += 10
        elif content_length >= 1000000:
            confidence += 5
        else:
            confidence += 2
        
        return min(confidence / 100, 1.0)

    def _check_missing_indicators(
        self,
        found_keywords: List[str],
        extracted_info: Dict[str, Any]
    ) -> List[str]:
        """检查缺失的关键指标"""
        missing = []
        
        # 检查关键税务术语
        essential_keywords = ["增值税", "税额", "发票", "销售", "进项", "销项"]
        found_essential = [kw for kw in essential_keywords if kw in found_keywords]
        if len(found_essential) < 2:
            missing.append(f"缺少关键税务术语（找到{len(found_essential)}/6）")
        
        # 检查是否有金额
        if not extracted_info.get("amounts"):
            missing.append("未检测到金额信息")
        
        # 检查是否只有低置信度关键词
        low_conf_count = sum(1 for kw in found_keywords if kw in self.LOW_CONFIDENCE_KEYWORDS)
        if low_conf_count > 0 and len(found_keywords) - low_conf_count < 3:
            missing.append("关键词过于笼统，未检测到明确的税务特征")
        
        return missing

    def _generate_suggestions(
        self,
        confidence: float,
        missing_indicators: List[str],
        found_keywords: List[str]
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if confidence < 0.3:
            suggestions.append("该文件可能不是税务文件，请确认文件类型")
            suggestions.append("建议上传增值税发票、企业所得税申报表等税务文件")
        elif confidence < 0.6:
            if "缺少关键税务术语" in str(missing_indicators):
                suggestions.append("文件中税务术语较少，建议使用标准的税务报表模板")
            if "未检测到金额信息" in str(missing_indicators):
                suggestions.append("请确保文件包含完整的金额信息")
        
        if not found_keywords:
            suggestions.append("无法识别文件内容，请检查文件是否清晰可读")
        
        if not suggestions:
            suggestions.append("文件验证通过，可以继续处理")
        
        return suggestions

    def _is_valid_tax_file(
        self,
        confidence: float,
        missing_indicators: List[str]
    ) -> bool:
        """判断是否为有效的税务文件"""
        # 高置信度
        if confidence >= 0.6:
            return True
        
        # 中等置信度但没有严重缺失
        if confidence >= 0.4:
            severe_missing = [
                "缺少关键税务术语",
                "未检测到金额信息",
                "关键词过于笼统"
            ]
            has_severe_missing = any(m in str(missing_indicators) for m in severe_missing)
            return not has_severe_missing
        
        return False

    def _generate_error_message(self, missing_indicators: List[str]) -> str:
        """生成错误消息"""
        if not missing_indicators:
            return "文件验证未通过，请检查文件格式"
        
        return "; ".join(missing_indicators[:3])  # 最多3条错误信息


# 单例实例
tax_file_validator = TaxFileValidator()
