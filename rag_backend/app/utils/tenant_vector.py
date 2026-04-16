"""
向量库租户隔离工具
"""

from typing import Dict, Optional


def get_vector_filter(tenant_id: str) -> Dict:
    """
    获取向量检索的租户过滤器
    
    Args:
        tenant_id: 租户ID
        
    Returns:
        Qdrant 过滤器字典
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    
    return {
        "must": [
            {
                "key": "tenant_id",
                "match": {
                    "value": tenant_id
                }
            }
        ]
    }


def merge_vector_filters(tenant_id: str, additional_filters: Optional[Dict] = None) -> Dict:
    """
    合并租户过滤器和其他过滤条件
    
    Args:
        tenant_id: 租户ID
        additional_filters: 额外的过滤条件
        
    Returns:
        合并后的过滤器
    """
    base_filter = get_vector_filter(tenant_id)
    
    if not additional_filters:
        return base_filter
    
    # 合并 must 条件
    if "must" in additional_filters:
        base_filter["must"].extend(additional_filters["must"])
    
    # 添加 should 条件
    if "should" in additional_filters:
        base_filter["should"] = additional_filters["should"]
    
    # 添加 must_not 条件
    if "must_not" in additional_filters:
        base_filter["must_not"] = additional_filters["must_not"]
    
    return base_filter


def add_tenant_to_payload(payload: Dict, tenant_id: str) -> Dict:
    """
    向 payload 添加 tenant_id
    
    Args:
        payload: 原始 payload
        tenant_id: 租户ID
        
    Returns:
        添加了 tenant_id 的 payload
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    
    payload["tenant_id"] = tenant_id
    return payload


def validate_vector_payload(payload: Dict) -> bool:
    """
    验证 payload 是否包含 tenant_id
    
    Args:
        payload: payload 字典
        
    Returns:
        是否有效
    """
    return "tenant_id" in payload and payload["tenant_id"]
