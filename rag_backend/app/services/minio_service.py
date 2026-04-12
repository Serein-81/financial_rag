# app/services/minio_service.py
import io
import json
import uuid
import time
import asyncio
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
        self._buckets_initialized = False
    
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
        if self._client is None:
            self._init_client()
        
        last_exception = None
        delay = self.retry_delay
        
        for attempt in range(self.retry_max_attempts):
            try:
                return operation(*args, **kwargs)
            except (ValueError, KeyError) as e:
                last_exception = e
                if attempt < self.retry_max_attempts - 1:
                    time.sleep(delay)
                    delay *= 2 if self.retry_exponential else 1
                    continue
                raise
            except (OSError, IOError) as e:
                last_exception = e
                if attempt < self.retry_max_attempts - 1:
                    time.sleep(delay)
                    delay *= 2 if self.retry_exponential else 1
                    continue
                raise
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
    
    async def _retry_operation_async(self, operation, *args, **kwargs):
        """异步重试机制 - 使用 asyncio.sleep() 避免阻塞事件循环"""
        if self._client is None:
            self._init_client()
        
        last_exception = None
        delay = self.retry_delay
        
        for attempt in range(self.retry_max_attempts):
            try:
                return await asyncio.to_thread(operation, *args, **kwargs)
            except (ValueError, KeyError) as e:
                last_exception = e
                if attempt < self.retry_max_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2 if self.retry_exponential else 1
                    continue
                raise
            except (OSError, IOError) as e:
                last_exception = e
                if attempt < self.retry_max_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 2 if self.retry_exponential else 1
                    continue
                raise
            except Exception as e:
                last_exception = e
                if attempt < self.retry_max_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt) if self.retry_exponential else self.retry_delay
                    logger.warning(f"[异步重试] {operation.__name__} 第 {attempt + 1} 次失败: {e}, {wait_time:.1f}秒后重试...")
                    await asyncio.sleep(wait_time)
                    self._init_client()
                else:
                    logger.error(f"[异步失败] {operation.__name__} 重试 {self.retry_max_attempts} 次后仍失败")
        
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
        except (ValueError, KeyError) as e:
            logger.warning(f"[MinIO] 设置策略数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"[MinIO] 设置策略IO错误: {e}")
        except Exception as e:
            logger.warning(f"[MinIO] 设置策略失败: {e}")
    
    def _ensure_initialized(self):
        """确保客户端和桶已初始化（懒加载）"""
        if self._client is None:
            self._init_client()
        
        if not self._buckets_initialized:
            try:
                self._ensure_bucket_exists(self.avatar_bucket)
                self._ensure_bucket_exists(self.doc_bucket)
                self._ensure_public_policy(self.avatar_bucket)
                self._buckets_initialized = True
            except (ValueError, KeyError) as e:
                logger.warning(f"[MinIO] 初始化 bucket 数据错误: {e}")
            except (OSError, IOError) as e:
                logger.warning(f"[MinIO] 初始化 bucket IO错误: {e}")
            except Exception as e:
                logger.warning(f"[MinIO] 初始化 bucket 失败: {e}")
    
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
        self._ensure_initialized()
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
            print(f"[MinIO] upload_document: object_name={object_name}, resolved_path={resolved_path}, bucket={self.doc_bucket}")
            data_stream = io.BytesIO(file_bytes)
            self._client.put_object(
                self.doc_bucket,
                resolved_path,
                data_stream,
                len(file_bytes),
                content_type
            )
            print(f"[MinIO] upload_document: 上传完成, 实际MinIO路径: {self.doc_bucket}/{resolved_path}")
            return f"{self.doc_bucket}/{resolved_path}"
        
        return self._retry_operation(_do_upload)
    
    async def upload_document_async(
        self,
        file_bytes: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        tenant_id: Optional[str] = None
    ) -> str:
        """
        异步上传文档（使用 asyncio 避免阻塞）
        
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
            logger.info(f"[MinIO异步] upload_document_async: object_name={object_name}, resolved_path={resolved_path}, bucket={self.doc_bucket}")
            data_stream = io.BytesIO(file_bytes)
            self._client.put_object(
                self.doc_bucket,
                resolved_path,
                data_stream,
                len(file_bytes),
                content_type
            )
            logger.info(f"[MinIO异步] upload_document_async: 上传完成, 实际MinIO路径: {self.doc_bucket}/{resolved_path}")
            return f"{self.doc_bucket}/{resolved_path}"
        
        return await self._retry_operation_async(_do_upload)
    
    def download_document(
        self,
        object_name: str,
        tenant_id: Optional[str] = None
    ) -> bytes:
        """
        下载文档（带重试机制 + 路径隔离 + 资源正确释放）
        
        Args:
            object_name: 对象名称（可能是完整路径如 "documents/tenant_id/..." 或相对路径 "tenant_id/..."）
            tenant_id: 租户ID（已废弃，不再使用）
        
        Returns:
            文件内容
        """
        def _do_download():
            resolved_name = self._resolve_object_name(object_name)
            print(f"[MinIO] download_document: object_name={object_name}, resolved_name={resolved_name}")
            
            try:
                stat = self._client.stat_object(self.doc_bucket, resolved_name)
                print(f"[MinIO] 文件存在, 大小: {stat.size} bytes, ETag: {stat.etag}")
            except S3Error as e:
                print(f"[MinIO] 文件不存在或无法访问: {e}")
                raise
            
            response = self._client.get_object(self.doc_bucket, resolved_name)
            try:
                data = response.read()
                print(f"[MinIO] download_document: read {len(data)} bytes")
                return data
            finally:
                response.close()
                response.release_conn()
        
        return self._retry_operation(_do_download)
    
    async def download_document_async(
        self,
        object_name: str,
        tenant_id: Optional[str] = None
    ) -> bytes:
        """
        异步下载文档（使用 asyncio 避免阻塞）
        
        Args:
            object_name: 对象名称
            tenant_id: 租户ID（已废弃，不再使用）
        
        Returns:
            文件内容
        """
        def _do_download():
            resolved_name = self._resolve_object_name(object_name)
            logger.info(f"[MinIO异步] download_document_async: object_name={object_name}, resolved_name={resolved_name}")
            
            try:
                stat = self._client.stat_object(self.doc_bucket, resolved_name)
                logger.info(f"[MinIO异步] 文件存在, 大小: {stat.size} bytes, ETag: {stat.etag}")
            except S3Error as e:
                logger.error(f"[MinIO异步] 文件不存在或无法访问: {e}")
                raise
            
            response = self._client.get_object(self.doc_bucket, resolved_name)
            try:
                data = response.read()
                logger.info(f"[MinIO异步] download_document_async: read {len(data)} bytes")
                return data
            finally:
                response.close()
                response.release_conn()
        
        return await self._retry_operation_async(_do_download)
    
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
        except (ValueError, KeyError) as e:
            logger.warning(f"[MinIO] 检查对象存在数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.warning(f"[MinIO] 检查对象存在IO错误: {e}")
            return False
        except RuntimeError as e:
            logger.warning(f"[MinIO] 检查对象存在运行时错误: {e}")
            return False
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
            self._ensure_initialized()
            buckets: List[Bucket] = self._client.list_buckets()
            bucket_info = []
            
            for b in buckets:
                try:
                    objects = list(self._client.list_objects(b.name, recursive=True))
                    bucket_info.append({
                        "name": b.name,
                        "object_count": len(objects)
                    })
                except (ValueError, KeyError) as e:
                    logger.warning(f"[MinIO] 获取桶信息数据错误: {e}")
                    bucket_info.append({"name": b.name, "object_count": "unknown"})
                except (OSError, IOError) as e:
                    logger.warning(f"[MinIO] 获取桶信息IO错误: {e}")
                    bucket_info.append({"name": b.name, "object_count": "unknown"})
                except RuntimeError as e:
                    logger.warning(f"[MinIO] 获取桶信息运行时错误: {e}")
                    bucket_info.append({"name": b.name, "object_count": "unknown"})
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
        except (ValueError, KeyError) as e:
            logger.error(f"[MinIO] 获取存储信息数据错误: {e}")
            return {
                "status": "unhealthy",
                "error": f"数据错误: {str(e)}",
                "buckets": [],
                "total_size_bytes": 0,
                "total_objects": 0,
                "timestamp": time.time()
            }
        except (OSError, IOError) as e:
            logger.error(f"[MinIO] 获取存储信息IO错误: {e}")
            return {
                "status": "unhealthy",
                "error": f"IO错误: {str(e)}",
                "buckets": [],
                "total_size_bytes": 0,
                "total_objects": 0,
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
            self._ensure_initialized()
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logger.info(f"[MinIO] 创建桶成功: {bucket_name}")
            return True
        except (ValueError, KeyError) as e:
            logger.error(f"[MinIO] 创建桶数据错误: {bucket_name}, 错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"[MinIO] 创建桶IO错误: {bucket_name}, 错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[MinIO] 创建桶失败: {bucket_name}, 错误: {e}")
            return False
    
    def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """删除桶"""
        try:
            self._ensure_initialized()
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
        except (ValueError, KeyError) as e:
            logger.error(f"[MinIO] 删除桶数据错误: {bucket_name}, 错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"[MinIO] 删除桶IO错误: {bucket_name}, 错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[MinIO] 删除桶失败: {bucket_name}, 错误: {e}")
            return False
    
    def list_buckets(self) -> List[str]:
        """列出所有桶"""
        try:
            self._ensure_initialized()
            return [b.name for b in self._client.list_buckets()]
        except (ValueError, KeyError) as e:
            logger.error(f"[MinIO] 列出桶数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            logger.error(f"[MinIO] 列出桶IO错误: {e}")
            return []
        except Exception as e:
            logger.error(f"[MinIO] 列出桶失败: {e}")
            return []


class MinioServiceSingleton:
    """MinIO 服务懒加载单例"""
    _instance: Optional[MinioService] = None
    
    def __getattr__(self, name):
        if MinioServiceSingleton._instance is None:
            MinioServiceSingleton._instance = MinioService()
        return getattr(MinioServiceSingleton._instance, name)
    
    def __dir__(self):
        if MinioServiceSingleton._instance is None:
            MinioServiceSingleton._instance = MinioService()
        return dir(MinioServiceSingleton._instance)


minio_service = MinioServiceSingleton()
