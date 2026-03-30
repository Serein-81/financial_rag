"""
PII（个人身份信息）脱敏工具
用于在将文档发送给外部LLM API之前，移除敏感个人信息
"""

import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class PIIType(Enum):
    """PII类型枚举"""
    NAME = "name"
    PHONE = "phone"
    EMAIL = "email"
    ID_CARD = "id_card"
    BANK_ACCOUNT = "bank_account"
    ADDRESS = "address"
    TAX_ID = "tax_id"
    CREDIT_CARD = "credit_card"


@dataclass
class PIIMatch:
    """PII匹配结果"""
    pii_type: PIIType
    original_value: str
    replacement: str
    start_pos: int
    end_pos: int
    confidence: float


class PIIAnonymizer:
    """
    PII脱敏工具
    
    支持检测和脱敏的PII类型：
    1. 姓名（中文姓名）
    2. 手机号码
    3. 电子邮箱
    4. 身份证号
    5. 银行账号
    6. 地址
    7. 纳税人识别号（15-20位）
    8. 信用卡号
    """
    
    def __init__(self):
        """初始化脱敏工具"""
        self._init_patterns()
        self._init_replacements()
    
    def _init_patterns(self):
        """初始化正则表达式模式"""
        self.patterns: Dict[PIIType, re.Pattern] = {
            PIIType.PHONE: re.compile(
                r'(?<!\d)(1[3-9]\d{9})(?!\d)',
                re.IGNORECASE
            ),
            PIIType.EMAIL: re.compile(
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                re.IGNORECASE
            ),
            PIIType.ID_CARD: re.compile(
                r'(?<!\d)[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)'
            ),
            PIIType.BANK_ACCOUNT: re.compile(
                r'(?<!\d)\d{16,19}(?!\d)'
            ),
            PIIType.TAX_ID: re.compile(
                r'(?<!\d)\d{15}|\d{18}|\d{20}(?!\d)'
            ),
            PIIType.CREDIT_CARD: re.compile(
                r'(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)'
            ),
        }
        
        self.chinese_name_patterns = [
            r'姓名[：:]\s*([\u4e00-\u9fff]{2,4})',
            r'纳税人[：:]\s*([\u4e00-\u9fff]{2,10})',
            r'公司名称[：:]\s*([\u4e00-\u9fff]{2,30})',
            r'当事人[：:]\s*([\u4e00-\u9fff]{2,10})',
            r'法定代表人[：:]\s*([\u4e00-\u9fff]{2,4})',
        ]
    
    def _init_replacements(self):
        """初始化脱敏替换规则"""
        self.replacements: Dict[PIIType, Tuple[str, float]] = {
            PIIType.PHONE: ("[PHONE_{index}]", 0.95),
            PIIType.EMAIL: ("[EMAIL_{index}]", 0.95),
            PIIType.ID_CARD: ("[ID_{index}]", 0.98),
            PIIType.BANK_ACCOUNT: ("[BANK_{index}]", 0.98),
            PIIType.TAX_ID: ("[TAX_ID_{index}]", 0.95),
            PIIType.CREDIT_CARD: ("[CARD_{index}]", 0.98),
        }
        
        self.counter: Dict[PIIType, int] = {pt: 0 for pt in PIIType}
    
    def reset_counter(self):
        """重置计数器"""
        self.counter = {pt: 0 for pt in PIIType}
    
    def anonymize(self, text: str, preserve_format: bool = True) -> str:
        """
        脱敏文本中的所有PII
        
        Args:
            text: 原始文本
            preserve_format: 是否保留格式（如手机号保留前三位后四位）
            
        Returns:
            脱敏后的文本
        """
        self.reset_counter()
        
        result = text
        
        for pii_type, pattern in self.patterns.items():
            matches = list(pattern.finditer(result))
            for match in reversed(matches):
                original = match.group(0)
                replacement, _ = self.replacements[pii_type]
                index = self.counter[pii_type]
                self.counter[pii_type] += 1
                
                placeholder = replacement.format(index=index)
                
                if preserve_format and pii_type == PIIType.PHONE:
                    phone = original
                    if len(phone) == 11:
                        placeholder = f"{phone[:3]}****{phone[-4:]}"
                elif preserve_format and pii_type == PIIType.TAX_ID:
                    tax_id = original
                    if len(tax_id) == 18:
                        placeholder = f"{tax_id[:6]}****{tax_id[-4:]}"
                
                result = result[:match.start()] + placeholder + result[match.end():]
        
        for name_pattern in self.chinese_name_patterns:
            matches = list(re.finditer(name_pattern, result))
            for match in reversed(matches):
                name = match.group(1)
                if name and not self._is_generic_term(name):
                    index = self.counter[PIIType.NAME]
                    self.counter[PIIType.NAME] += 1
                    placeholder = f"[NAME_{index}]"
                    result = result[:match.start(1)] + placeholder + result[match.end(1):]
        
        return result
    
    def _is_generic_term(self, text: str) -> bool:
        """检查是否是通用术语"""
        generic_terms = [
            "有限公司", "股份有限公司", "有限责任公司",
            "公司", "企业", "集团", "个人", "纳税人"
        ]
        return any(term in text for term in generic_terms)
    
    def find_all_pii(self, text: str) -> List[PIIMatch]:
        """
        查找文本中的所有PII
        
        Args:
            text: 原始文本
            
        Returns:
            PII匹配列表
        """
        matches: List[PIIMatch] = []
        
        for pii_type, pattern in self.patterns.items():
            replacement, confidence = self.replacements[pii_type]
            for match in pattern.finditer(text):
                original = match.group(0)
                index = self.counter.get(pii_type, 0)
                self.counter[pii_type] = index + 1
                
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    original_value=original,
                    replacement=replacement.format(index=index),
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=confidence
                ))
        
        for name_pattern in self.chinese_name_patterns:
            for match in re.finditer(name_pattern, text):
                name = match.group(1)
                if name and not self._is_generic_term(name):
                    index = self.counter.get(PIIType.NAME, 0)
                    self.counter[PIIType.NAME] = index + 1
                    
                    matches.append(PIIMatch(
                        pii_type=PIIType.NAME,
                        original_value=name,
                        replacement=f"[NAME_{index}]",
                        start_pos=match.start(1),
                        end_pos=match.end(1),
                        confidence=0.8
                    ))
        
        matches.sort(key=lambda x: x.start_pos)
        return matches
    
    def restore(self, anonymized_text: str, pii_mapping: Dict[str, str]) -> str:
        """
        恢复脱敏的PII
        
        Args:
            anonymized_text: 脱敏后的文本
            pii_mapping: PII映射字典 {占位符: 原始值}
            
        Returns:
            恢复后的文本
        """
        result = anonymized_text
        for placeholder, original in pii_mapping.items():
            result = result.replace(placeholder, original)
        return result
    
    def anonymize_json(self, data: Any, preserve_keys: Optional[List[str]] = None) -> Tuple[Any, Dict[str, str]]:
        """
        脱敏JSON数据中的PII
        
        Args:
            data: JSON数据（dict/list/str/int/float/bool/None）
            preserve_keys: 需要保留不脱敏的键名列表
            
        Returns:
            (脱敏后的数据, PII映射字典)
        """
        preserve_keys = preserve_keys or []
        pii_mapping: Dict[str, str] = {}
        
        def _process(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: _process(v) if k not in preserve_keys else v
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [_process(item) for item in obj]
            elif isinstance(obj, str):
                self.reset_counter()
                anonymized = self.anonymize(obj)
                all_pii = self.find_all_pii(obj)
                
                for pii_match in all_pii:
                    if pii_match.replacement not in pii_mapping:
                        pii_mapping[pii_match.replacement] = pii_match.original_value
                
                return anonymized
            else:
                return obj
        
        return _process(data), pii_mapping
    
    def get_statistics(self, text: str) -> Dict[str, int]:
        """
        获取文本中PII统计信息
        
        Args:
            text: 原始文本
            
        Returns:
            各类型PII数量统计
        """
        all_pii = self.find_all_pii(text)
        stats: Dict[str, int] = {}
        
        for pii_match in all_pii:
            pii_name = pii_match.pii_type.value
            stats[pii_name] = stats.get(pii_name, 0) + 1
        
        return stats


pii_anonymizer = PIIAnonymizer()


def anonymize_text(text: str, preserve_format: bool = True) -> str:
    """
    便捷函数：脱敏文本
    
    Args:
        text: 原始文本
        preserve_format: 是否保留格式
        
    Returns:
        脱敏后的文本
    """
    return pii_anonymizer.anonymize(text, preserve_format)


def anonymize_json(data: Any, preserve_keys: Optional[List[str]] = None) -> Tuple[Any, Dict[str, str]]:
    """
    便捷函数：脱敏JSON数据
    
    Args:
        data: JSON数据
        preserve_keys: 需要保留的键名
        
    Returns:
        (脱敏后的数据, PII映射)
    """
    return pii_anonymizer.anonymize_json(data, preserve_keys)


def get_pii_statistics(text: str) -> Dict[str, int]:
    """
    便捷函数：获取PII统计
    
    Args:
        text: 原始文本
        
    Returns:
        PII统计信息
    """
    return pii_anonymizer.get_statistics(text)


def restore_anonymized(anonymized_text: str, pii_mapping: Dict[str, str]) -> str:
    """
    便捷函数：恢复脱敏内容
    
    Args:
        anonymized_text: 脱敏后的文本
        pii_mapping: PII映射
        
    Returns:
        恢复后的文本
    """
    return pii_anonymizer.restore(anonymized_text, pii_mapping)
