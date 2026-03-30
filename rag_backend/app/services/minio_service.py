# app/services/minio_service.py
import io
import json
import uuid
import time
import logging
from typing import Optional, Dict, Any, List
from minio import Minio
from minio.error import S3Error
from minio.datatypes import Bucket
from app.core.config import settings

logger = logging.getLogger(__name__)


class MinioService:
    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.secure = settings.MINIO_SECURE
        
        self.avatar_bucket = settings.MINIO_AVATAR_BUCKET
        self.doc_bucket = getattr(settings, "MINIO_DOC_BUCKET", "documents")
        
        self.prefix_path = getattr(settings, 'MINIO_PREFIX_PATH', None)
        self.verify_ssl = getattr(settings, 'MINIO_VERIFY_SSL', True)
        self.retry_max_attempts = getattr(settings, 'MINIO_RETRY_MAX_ATTEMPTS', 3)
        self.retry_delay = getattr(settings, 'MINIO_RETRY_DELAY', 1.0)
        self.retry_exponential = getattr(settings, 'MINIO_RETRY_EXPONENTIAL', True)
        
        self._client: Optional[Minio] = None
        self._init_client()
        
        self._ensure_bucket_exists(self.avatar_bucket)
        self._ensure_bucket_exists(self.doc_bucket)
        self._ensure_public_policy(self.avatar_bucket)
    
    def _init_client(self):
        """初始化 MinIO 客户端"""
        http_client = None
        if not self.verify_ssl:
            import urllib3
            import ssl
            http_client = urllib3.PoolManager(cert_reqs=ssl.CERT_NONE)
            logger.info("SSL 证书验证已禁用（支持自签名证书）")
        
        self._client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            http_client=http_client
        )
    
    def _resolve_path(self, filename: str, tenant_id: Optional[str] = None) -> str:
        """解析存储路径"""
        if self.prefix_path:
            if tenant_id:
                return f"{self.prefix_path}/{tenant_id}/{filename}"
            return f"{self.prefix_path}/{filename}"
        if tenant_id:
            return f"{tenant_id}/{filename}"
        return filename
    
    def _retry_operation(self, operation, *args, **kwargs):
        """通用重试机制"""
        last_exception = None
        
        for attempt in range(self.retry_max_attempts):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_max_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt) if self.retry_exponential else self.retry_delay
                    logger.warning(f"[重试] {operation.__name__} 第 {attempt + 1} 次失败: {e}, {wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)
                    self._init_client()
                else:
                    logger.error(f"[失败] {operation.__name__} 重试 {self.retry_max_attempts} 次后仍失败")
        
        raise last_exception
    
    def _ensure_bucket_exists(self, bucket_name: str):
        """确保桶存在"""
        try:
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logger.info(f"[MinIO] 自动创建 Bucket: {bucket_name}")
        except S3Error as e:
            logger.error(f"[MinIO] 检查 Bucket 失败: {e}")
    
    def _ensure_public_policy(self, bucket_name: str):
        """设置桶公开读取策略"""
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            }]
        }
        
        try:
            self._client.set_bucket_policy(bucket_name, json.dumps(policy))
            logger.info(f"[MinIO] 已设置 {bucket_name} 公开读取策略")
        except Exception as e:
            logger.warning(f"[MinIO] 设置策略失败: {e}")
    
    def _resolve_object_name(self, object_name: str) -> str:
        """兼容处理带 bucket 前缀的路径"""
        if object_name.startswith(f"{self.doc_bucket}/"):
            return object_name.split("/", 1)[1]
        return object_name
    
    # ==========================================
    # [头像管理]
    # ==========================================
    def upload_avatar(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """上传头像并返回直链 URL"""
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        object_name = f"{uuid.uuid4().hex}.{ext}"
        
        data_stream = io.BytesIO(file_bytes)
        self._client.put_object(
            self.avatar_bucket,
            object_name,
            data_stream,
            len(file_bytes),
            content_type
        )
        
        public_endpoint = getattr(settings, "MINIO_PUBLIC_ENDPOINT", self.endpoint)
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{public_endpoint}/{self.avatar_bucket}/{object_name}"
    
    # ==========================================
    # [文档管理 - 融合版]
    # ==========================================
    def upload_document(
        self,
        file_bytes: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        tenant_id: Optional[str] = None
    ) -> str:
        """
        上传文档（带重试机制 + 路径隔离）
        
        Args:
            file_bytes: 文件内容
            object_name: 对象名称
            content_type: 内容类型
            tenant_id: 租户ID（用于路径隔离）
        
        Returns:
            存储路径标识
        """
        def _do_upload():
            resolved_path = self._resolve_path(object_name, tenant_id)
            data_stream = io.BytesIO(file_bytes)
            self._client.put_object(
                self.doc_bucket,
                resolved_path,
                data_stream,
                len(file_bytes),
                content_type
            )
            return f"{self.doc_bucket}/{resolved_path}"
        
        return self._retry_operation(_do_upload)
    
    def download_document(
        self,
        object_name: str,
        tenant_id: Optional[str] = None
    ) -> bytes:
        """
        下载文档（带重试机制 + 路径隔离 + 资源正确释放）
        
        Args:
            object_name: 对象名称
            tenant_id: 租户ID
        
        Returns:
            文件内容
        """
        def _do_download():
            resolved_name = self._resolve_object_name(object_name)
            resolved_path = self._resolve_path(resolved_name, tenant_id)
            
            response = self._client.get_object(self.doc_bucket, resolved_path)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        
        return self._retry_operation(_do_download)
    
    def delete_document(self, object_name: str, tenant_id: Optional[str] = None):
        """删除文档"""
        def _do_delete():
            resolved_name = self._resolve_object_name(object_name)
            resolved_path = self._resolve_path(resolved_name, tenant_id)
            self._client.remove_object(self.doc_bucket, resolved_path)
        
        return self._retry_operation(_do_delete)
    
    def document_exists(self, object_name: str, tenant_id: Optional[str] = None) -> bool:
        """检查文档是否存在"""
        try:
            resolved_name = self._resolve_object_name(object_name)
            resolved_path = self._resolve_path(resolved_name, tenant_id)
            self._client.stat_object(self.doc_bucket, resolved_path)
            return True
        except S3Error as e:
            if e.code in ["NoSuchKey", "NoSuchBucket"]:
                return False
            raise
        except Exception:
            return False
    
    def list_documents(self, prefix: str = "", tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出文档"""
        def _do_list():
            resolved_prefix = self._resolve_path(prefix, tenant_id) if prefix else ""
            if self.prefix_path and tenant_id:
                resolved_prefix = f"{self.prefix_path}/{tenant_id}/" + prefix
            elif self.prefix_path:
                resolved_prefix = f"{self.prefix_path}/" + prefix
            elif tenant_id:
                resolved_prefix = f"{tenant_id}/" + prefix
            
            objects = self._client.list_objects(self.doc_bucket, prefix=resolved_prefix, recursive=True)
            return [
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                }
                for obj in objects
            ]
        
        return self._retry_operation(_do_list)
    
    # ==========================================
    # [健康检查]
    # ==========================================
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            buckets: List[Bucket] = self._client.list_buckets()
            bucket_info = []
            
            for b in buckets:
                try:
                    objects = list(self._client.list_objects(b.name, recursive=True))
                    bucket_info.append({
                        "name": b.name,
                        "object_count": len(objects)
                    })
                except Exception:
                    bucket_info.append({"name": b.name, "object_count": "unknown"})
            
            return {
                "status": "healthy",
                "endpoint": self.endpoint,
                "secure": self.secure,
                "prefix_path": self.prefix_path,
                "bucket_count": len(buckets),
                "buckets": bucket_info,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e),
                "timestamp": time.time()
            }
    
    # ==========================================
    # [预签名 URL]
    # ==========================================
    def get_presigned_url(
        self,
        object_name: str,
        expires: int = 3600,
        tenant_id: Optional[str] = None
    ) -> Optional[str]:
        """获取预签名 URL"""
        def _do_get_url():
            resolved_name = self._resolve_object_name(object_name)
            resolved_path = self._resolve_path(resolved_name, tenant_id)
            return self._client.get_presigned_url("GET", self.doc_bucket, resolved_path, expires)
        
        return self._retry_operation(_do_get_url)
    
    # ==========================================
    # [桶管理]
    # ==========================================
    def create_bucket(self, bucket_name: str) -> bool:
        """创建桶"""
        try:
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logger.info(f"[MinIO] 创建桶成功: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"[MinIO] 创建桶失败: {bucket_name}, 错误: {e}")
            return False
    
    def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """删除桶"""
        try:
            if not self._client.bucket_exists(bucket_name):
                return False
            
            if force:
                objects = self._client.list_objects(bucket_name, recursive=True)
                for obj in objects:
                    self._client.remove_object(bucket_name, obj.object_name)
                logger.info(f"[MinIO] 已删除桶内所有对象: {bucket_name}")
            
            self._client.remove_bucket(bucket_name)
            logger.info(f"[MinIO] 删除桶成功: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"[MinIO] 删除桶失败: {bucket_name}, 错误: {e}")
            return False
    
    def list_buckets(self) -> List[str]:
        """列出所有桶"""
        try:
            return [b.name for b in self._client.list_buckets()]
        except Exception as e:
            logger.error(f"[MinIO] 列出桶失败: {e}")
            return []


# 单例导出
minio_service = MinioService()
