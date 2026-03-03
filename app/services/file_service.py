# app/services/file_service.py
import io
from pypdf import PdfReader
from docx import Document as DocxDocument
# 👇 补充1：引入我们刚刚写好的 MinIO 服务
from app.services.minio_service import minio_service

class FileService:
    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        """
        根据文件类型，提取文件中的所有文字内容
        """
        content = ""

        try:
            # 👇 补充2：核心桥梁！把 MinIO 里的文件拉取到内存中，变成字节流
            file_bytes = minio_service.download_document(file_path)
            file_stream = io.BytesIO(file_bytes)

            # 1. 处理 PDF (你的原逻辑，PdfReader 原生支持吃 BytesIO 内存流)
            if "pdf" in file_type.lower():
                reader = PdfReader(file_stream)
                # 遍历每一页提取文字
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n"

            # 2. 处理 Word (你的原逻辑，DocxDocument 原生支持吃 BytesIO 内存流)
            elif "word" in file_type.lower() or "docx" in file_type.lower():
                doc = DocxDocument(file_stream)
                # 遍历每一个段落
                for para in doc.paragraphs:
                    content += para.text + "\n"

            # 3. 处理 TXT / Markdown (补充：既然在内存里了，直接 decode 解码即可，不用 open)
            elif "text" in file_type.lower():
                content = file_bytes.decode('utf-8')

            else:
                return f"不支持的文件类型: {file_type}"

            return content.strip()  # 去除首尾空白

        except Exception as e:
            print(f"❌ 文件解析失败: {e}")
            raise e

# 方便调用的单例实例
file_service = FileService()