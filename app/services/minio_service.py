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
        self.bucket_name = settings.MINIO_AVATAR_BUCKET
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """确保桶存在，如果不存在就自动创建一个"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"📦 自动创建了 MinIO Bucket: {self.bucket_name}")
        except S3Error as e:
            print(f"❌ 检查 MinIO Bucket 失败: {e}")

    def upload_avatar(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """上传头像并返回文件的直链 URL"""
        # 为了防止文件名冲突，给文件重命名为 UUID
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        new_filename = f"{uuid.uuid4().hex}.{ext}"

        # 转换为字节流供 MinIO 读取
        data_stream = io.BytesIO(file_bytes)

        # 上传到 MinIO
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=new_filename,
            data=data_stream,
            length=len(file_bytes),
            content_type=content_type  # 👈 关键点：告诉浏览器这是图片，直接显示而不是下载
        )

        # 拼接返回文件的访问 URL
        protocol = "https" if settings.MINIO_SECURE else "http"
        file_url = f"{protocol}://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{new_filename}"

        return file_url


# 导出单例对象，方便其他地方直接引入调用
minio_service = MinioService()