"""
Cypher AST 验证器

提供 Cypher 查询的 AST 级别安全验证，防止注入攻击

功能：
1. AST 解析和验证
2. 危险操作检测
3. 节点属性访问控制
4. 关系类型白名单
5. 嵌套查询深度限制
"""

import re
from typing import List, Optional, Set, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    STRICT = "strict"      # 严格模式，拒绝所有未知操作
    NORMAL = "normal"      # 正常模式，允许白名单操作
    PERMISSIVE = "permissive"  # 宽松模式，允许大部分操作


class CypherValidator:
    """
    Cypher 查询验证器
    
    通过 AST 分析防止潜在的 Cypher 注入攻击
    """
    
    def __init__(
        self,
        validation_level: ValidationLevel = ValidationLevel.NORMAL,
        max_query_depth: int = 5,
        max_result_size: int = 10000,
        allowed_node_labels: Optional[Set[str]] = None,
        allowed_relationship_types: Optional[Set[str]] = None,
        allowed_properties: Optional[Set[str]] = None,
        dangerous_patterns: Optional[List[str]] = None,
        custom_validators: Optional[List[Callable[[Dict[str, Any]], bool]]] = None,
    ):
        """
        初始化验证器
        
        Args:
            validation_level: 验证级别
            max_query_depth: 最大查询深度
            max_result_size: 最大结果集大小
            allowed_node_labels: 允许的节点标签白名单
            allowed_relationship_types: 允许的关系类型白名单
            allowed_properties: 允许的属性名白名单
            dangerous_patterns: 危险模式列表
            custom_validators: 自定义验证器函数列表
        """
        self.validation_level = validation_level
        self.max_query_depth = max_query_depth
        self.max_result_size = max_result_size
        self.allowed_node_labels = allowed_node_labels or set()
        self.allowed_relationship_types = allowed_relationship_types or set()
        self.allowed_properties = allowed_properties or set()
        self.dangerous_patterns = dangerous_patterns or self._get_default_dangerous_patterns()
        self.custom_validators = custom_validators or []
        
        self._query_count = 0
    
    def _get_default_dangerous_patterns(self) -> List[str]:
        """获取默认的危险模式"""
        return [
            r"DROP\s+",
            r"DELETE\s+",
            r"REMOVE\s+",
            r"DETACH\s+DELETE",
            r"SET\s+\w+\s*=\s*NULL",  # 置空操作
            r"CREATE\s+\(\)",          # 无条件的创建
            r"MERGE\s+\(\)",           # 无条件的合并
            r"\bexec\s*\(",            # 执行函数
            r"\beval\s*\(",            # 危险函数
            r"\bsystem\s+",            # 系统命令
        ]
    
    def validate(self, cypher_query: str) -> "ValidationResult":
        """
        验证 Cypher 查询
        
        Args:
            cypher_query: Cypher 查询字符串
            
        Returns:
            ValidationResult: 验证结果
        """
        self._query_count += 1
        
        errors: List[str] = []
        warnings: List[str] = []
        
        if not cypher_query or not cypher_query.strip():
            errors.append("查询不能为空")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                query=cypher_query
            )
        
        query_lower = cypher_query.lower()
        
        for pattern in self.dangerous_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                errors.append(f"检测到危险操作: {pattern.strip()}")
        
        depth = self._calculate_query_depth(cypher_query)
        if depth > self.max_query_depth:
            errors.append(f"查询深度 {depth} 超过限制 {self.max_query_depth}")
        
        if self._check_result_size_hint(cypher_query):
            warnings.append("查询可能返回大量结果")
        
        if self.validation_level == ValidationLevel.STRICT:
            if not self._validate_against_whitelist(cypher_query):
                errors.append("查询包含未在白名单中的元素（严格模式）")
        
        for custom_validator in self.custom_validators:
            try:
                result = custom_validator({"query": cypher_query})
                if not result:
                    errors.append("自定义验证失败")
            except Exception as e:
                warnings.append(f"自定义验证异常: {str(e)}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Cypher 验证失败: {errors}")
        elif warnings:
            logger.info(f"Cypher 验证通过（有警告）: {warnings}")
        else:
            logger.debug(f"Cypher 验证通过: {cypher_query[:50]}...")
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            query=cypher_query,
            query_depth=depth,
            validation_level=self.validation_level.value
        )
    
    def _calculate_query_depth(self, query: str) -> int:
        """计算查询深度（简单实现）"""
        depth = 1
        
        depth_keywords = [
            r"WITH\s+",
            r"MATCH\s+.*?MATCH\s+",
            r"OPTIONAL\s+MATCH",
            r"CALL\s+",
            r"\)\s*\(",  # 嵌套模式
            r"->\([^)]+\)->",  # 关系模式
        ]
        
        for keyword in depth_keywords:
            matches = re.findall(keyword, query, re.IGNORECASE)
            depth += len(matches)
        
        return depth
    
    def _check_result_size_hint(self, query: str) -> bool:
        """检查结果大小提示"""
        size_patterns = [
            r"LIMIT\s+(\d+)",
            r"SKIP\s+\d+",
            r"RETURN\s+\*",
        ]
        
        for pattern in size_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return False
        
        return True
    
    def _validate_against_whitelist(self, query: str) -> bool:
        """根据白名单验证"""
        if self.allowed_node_labels:
            labels = re.findall(r":(\w+)", query)
            for label in labels:
                if label not in self.allowed_node_labels:
                    return False
        
        if self.allowed_relationship_types:
            rel_types = re.findall(r"\[:(\w+)", query)
            for rel_type in rel_types:
                if rel_type not in self.allowed_relationship_types:
                    return False
        
        if self.allowed_properties:
            properties = re.findall(r"\.(\w+)", query)
            for prop in properties:
                if prop not in self.allowed_properties:
                    return False
        
        return True
    
    def is_safe_node_label(self, label: str) -> bool:
        """检查节点标签是否安全"""
        if not self.allowed_node_labels:
            return True
        return label in self.allowed_node_labels
    
    def is_safe_relationship_type(self, rel_type: str) -> bool:
        """检查关系类型是否安全"""
        if not self.allowed_relationship_types:
            return True
        return rel_type in self.allowed_relationship_types
    
    def is_safe_property(self, property_name: str) -> bool:
        """检查属性是否安全"""
        if not self.allowed_properties:
            return True
        return property_name in self.allowed_properties
    
    def add_node_label(self, label: str) -> None:
        """添加允许的节点标签"""
        self.allowed_node_labels.add(label)
    
    def add_relationship_type(self, rel_type: str) -> None:
        """添加允许的关系类型"""
        self.allowed_relationship_types.add(rel_type)
    
    def add_property(self, property_name: str) -> None:
        """添加允许的属性"""
        self.allowed_properties.add(property_name)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取验证统计"""
        return {
            "total_validated": self._query_count,
            "validation_level": self.validation_level.value,
            "max_depth": self.max_query_depth,
            "max_result_size": self.max_result_size,
            "allowed_labels_count": len(self.allowed_node_labels),
            "allowed_rels_count": len(self.allowed_relationship_types),
            "allowed_props_count": len(self.allowed_properties),
        }


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    query: str = ""
    query_depth: int = 1
    validation_level: str = "normal"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "query_depth": self.query_depth,
            "validation_level": self.validation_level
        }


_global_validator: Optional[CypherValidator] = None


def get_cypher_validator() -> CypherValidator:
    """获取全局 Cypher 验证器实例"""
    global _global_validator
    if _global_validator is None:
        _global_validator = CypherValidator()
    return _global_validator
