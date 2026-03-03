# app/services/minio_service.py
import io
import uuid
from minio import Minio
from minio.error import S3Error
from app.core.config import settings


class MinioService:
    def __init__(self):
        # 初始化 MinIO 客户端
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )

        # 1. 头像桶
        self.avatar_bucket = settings.MINIO_AVATAR_BUCKET
        # 2. 文档桶 (使用 getattr 兼容，如果你 config 里没配，默认用 "documents")
        self.doc_bucket = getattr(settings, "MINIO_DOC_BUCKET", "documents")

        # 确保两个桶在 MinIO 中都存在
        self._ensure_bucket_exists(self.avatar_bucket)
        self._ensure_bucket_exists(self.doc_bucket)

    def _ensure_bucket_exists(self, bucket_name: str):
        """确保指定的桶存在，如果不存在就自动创建一个，并设置公开读取策略"""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                print(f"📦 自动创建了 MinIO Bucket: {bucket_name}")
                
                # 如果是头像桶，设置为公开读取
                if bucket_name == self.avatar_bucket:
                    self._set_public_read_policy(bucket_name)
                    print(f"🔓 已将 {bucket_name} 设置为公开读取")
            else:
                # 桶已存在，检查是否需要设置策略
                if bucket_name == self.avatar_bucket:
                    try:
                        self._set_public_read_policy(bucket_name)
                        print(f"🔓 已更新 {bucket_name} 的公开读取策略")
                    except Exception as e:
                        print(f"⚠️ 设置策略时出错: {e}")
        except S3Error as e:
            print(f"❌ 检查 MinIO Bucket 失败: {e}")
    
    def _set_public_read_policy(self, bucket_name: str):
        """设置桶为公开读取"""
        import json
        
        # 定义公开读取策略
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                }
            ]
        }
        
        try:
            self.client.set_bucket_policy(bucket_name, json.dumps(policy))
        except Exception as e:
            print(f"❌ 设置桶策略失败: {e}")
            print(f"💡 提示: 请手动在 MinIO 控制台设置 {bucket_name} 桶为公开访问")

    # ==========================================
    # 🖼️ 头像管理
    # ==========================================
    def upload_avatar(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """上传头像并返回文件的直链 URL"""
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        new_filename = f"{uuid.uuid4().hex}.{ext}"
        data_stream = io.BytesIO(file_bytes)

        self.client.put_object(
            bucket_name=self.avatar_bucket,
            object_name=new_filename,
            data=data_stream,
            length=len(file_bytes),
            content_type=content_type
        )

        protocol = "https" if settings.MINIO_SECURE else "http"
        return f"{protocol}://{settings.MINIO_ENDPOINT}/{self.avatar_bucket}/{new_filename}"

    # ==========================================
    # 📄 知识库文档管理
    # ==========================================
    def upload_document(self, file_bytes: bytes, object_name: str, content_type: str) -> str:
        """
        上传文档到 documents 桶，并返回内部存储路径标识
        object_name 一般建议使用 "kb_id/filename" 的格式，方便分类
        """
        data_stream = io.BytesIO(file_bytes)

        self.client.put_object(
            bucket_name=self.doc_bucket,
            object_name=object_name,
            data=data_stream,
            length=len(file_bytes),
            content_type=content_type
        )

        # 文档一般不对外公开直链，所以我们只返回内部的路径标识 (例如: documents/kb_xxx/test.pdf)
        return f"{self.doc_bucket}/{object_name}"

    def download_document(self, object_name: str) -> bytes:
        """
        供后台解析任务下载文件内容使用
        返回文件的二进制流
        """
        try:
            # 兼容带有 bucket 前缀的路径 (如果我们之前存的是 bucket_name/object_name)
            if object_name.startswith(f"{self.doc_bucket}/"):
                object_name = object_name.split("/", 1)[1]

            response = self.client.get_object(self.doc_bucket, object_name)
            return response.read()
        finally:
            # 必须确保连接被释放，否则高并发时会卡死
            if 'response' in locals():
                response.close()
                response.release_conn()


# 导出单例对象，方便其他地方直接引入调用
minio_service = MinioService()