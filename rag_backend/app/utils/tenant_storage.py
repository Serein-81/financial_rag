"""
租户存储工具
处理 MinIO 的租户隔离
"""

import logging

logger = logging.getLogger(__name__)


def get_tenant_bucket(tenant_id: str) -> str:
    """
    获取租户专属 bucket 名称
    
    Args:
        tenant_id: 租户ID
        
    Returns:
        bucket 名称，格式：tenant-{tenant_id}-documents
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    
    # 清理 tenant_id，确保符合 bucket 命名规范
    # MinIO bucket 名称规则：小写字母、数字、连字符，3-63字符
    clean_tenant_id = tenant_id.lower().replace("_", "-")
    bucket_name = f"tenant-{clean_tenant_id}-documents"
    
    # 验证长度
    if len(bucket_name) > 63:
        # 如果太长，使用 hash
        import hashlib
        tenant_hash = hashlib.md5(tenant_id.encode()).hexdigest()[:16]
        bucket_name = f"tenant-{tenant_hash}-docs"
    
    return bucket_name


def get_tenant_file_path(tenant_id: str, file_name: str, category: str = "general") -> str:
    """
    获取租户文件的完整路径
    
    Args:
        tenant_id: 租户ID
        file_name: 文件名
        category: 文件分类（general/audit/report等）
        
    Returns:
        文件路径，格式：{category}/{file_name}
    """
    # 在租户 bucket 内按类别组织文件
    return f"{category}/{file_name}"


def validate_tenant_access(user_tenant_id: str, resource_tenant_id: str) -> bool:
    """
    验证租户访问权限
    
    Args:
        user_tenant_id: 用户的租户ID
        resource_tenant_id: 资源的租户ID
        
    Returns:
        是否有权限访问
    """
    if not user_tenant_id or not resource_tenant_id:
        logger.warning("Missing tenant_id in access validation")
        return False
    
    # 简单的相等性检查
    has_access = user_tenant_id == resource_tenant_id
    
    if not has_access:
        logger.warning(
            f"Tenant access denied: user_tenant={user_tenant_id}, "
            f"resource_tenant={resource_tenant_id}"
        )
    
    return has_access


class TenantStorageManager:
    """租户存储管理器"""
    
    def __init__(self, minio_client):
        """
        初始化
        
        Args:
            minio_client: MinIO 客户端实例
        """
        self.client = minio_client
    
    async def ensure_tenant_bucket(self, tenant_id: str) -> str:
        """
        确保租户 bucket 存在，不存在则创建
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            bucket 名称
        """
        bucket_name = get_tenant_bucket(tenant_id)
        
        try:
            # 检查 bucket 是否存在
            if not self.client.bucket_exists(bucket_name):
                # 创建 bucket
                self.client.make_bucket(bucket_name)
                logger.info(f"Created tenant bucket: {bucket_name}")
                
                # 设置 bucket 策略（私有）
                await self._set_bucket_policy(bucket_name, tenant_id)
            
            return bucket_name
            
        except Exception as e:
            logger.error(f"Failed to ensure tenant bucket: {e}")
            raise
    
    async def _set_bucket_policy(self, bucket_name: str, tenant_id: str):
        """
        设置 bucket 访问策略
        
        Args:
            bucket_name: bucket 名称
            tenant_id: 租户ID
        """
        # 设置为私有访问
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:*"],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*"
                    ],
                    "Condition": {
                        "StringNotEquals": {
                            "s3:x-amz-meta-tenant-id": tenant_id
                        }
                    }
                }
            ]
        }
        
        try:
            import json
            self.client.set_bucket_policy(bucket_name, json.dumps(policy))
            logger.info(f"Set bucket policy for: {bucket_name}")
        except Exception as e:
            logger.warning(f"Failed to set bucket policy: {e}")

def get_tenant_path(tenant_id: str, path: str = "") -> str:
    """
    获取租户路径
    
    Args:
        tenant_id: 租户ID
        path: 子路径（可选）
        
    Returns:
        完整的租户路径
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    
    base_path = f"{tenant_id}"
    
    if path:
        # 确保路径格式正确
        path = path.strip("/")
        return f"{base_path}/{path}"
    
    return base_path
