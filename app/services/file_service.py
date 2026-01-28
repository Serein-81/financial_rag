import os
from pypdf import PdfReader
from docx import Document as DocxDocument


class FileService:
    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        """
        根据文件类型，提取文件中的所有文字内容
        """
        content = ""

        try:
            # 1. 处理 PDF
            if "pdf" in file_type.lower():
                reader = PdfReader(file_path)
                # 遍历每一页提取文字
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n"

            # 2. 处理 Word
            elif "word" in file_type.lower() or "docx" in file_type.lower():
                doc = DocxDocument(file_path)
                # 遍历每一个段落
                for para in doc.paragraphs:
                    content += para.text + "\n"

            # 3. 处理 TXT / Markdown
            elif "text" in file_type.lower():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

            else:
                return f"不支持的文件类型: {file_type}"

            return content.strip()  # 去除首尾空白

        except Exception as e:
            print(f"❌ 文件解析失败: {e}")
            raise e


# 方便调用的单例实例
file_service = FileService()