# app/services/chunk_service.py
from typing import List
# 需要安装 langchain: pip install langchain
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# 注意：中间是下划线，不再是从 langchain 主包导入
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ChunkService:
    def __init__(self):
        # 初始化分割器 (对应你截图中的逻辑)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # 每个切片的大小 (约300-500中文字符效果较好)
            chunk_overlap=50,  # 切片重叠部分 (防止句子被切断导致语义丢失)
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],  # 优先按段落切，其次按句子切
            length_function=len,  # 计算长度的函数
        )

    def split_text(self, text: str) -> List[str]:
        """
        接收长文本，返回切分后的文本列表
        """
        if not text:
            return []

        # LangChain 的 split_text 方法会自动处理递归切分
        chunks = self.text_splitter.split_text(text)

        # 去除空白字符，过滤掉过短的切片
        return [c.strip() for c in chunks if c.strip()]


# 实例化单例，供外部调用
chunk_service = ChunkService()