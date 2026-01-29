# app/services/embedding_service.py

from typing import List
from zhipuai import ZhipuAI
# ✅ 关键点：从统一配置中心导入 settings
from app.core import settings


class EmbeddingService:
    def __init__(self):
        # 默认使用智谱
        self.provider = "zhipu"

        self.client = None

        # ✅ 初始化逻辑：直接从 settings 读取 Key
        if self.provider == "zhipu":
            if not settings.ZHIPU_API_KEY:
                # 如果用户忘了在 .env 填 Key，这里打印个警告，防止报错懵逼
                print("❌ 警告: 未检测到 ZHIPU_API_KEY，请检查 .env 文件！")
            else:
                # 实例化客户端
                self.client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)

    async def get_embedding(self, text: str) -> List[float]:
        """
        核心方法：输入文本，输出向量
        """
        if self.provider == "zhipu":
            return self._get_zhipu_embedding(text)
        elif self.provider == "mock":
            return self._get_mock_embedding()
        else:
            raise ValueError(f"未知的 Embedding 提供商: {self.provider}")

    def _get_zhipu_embedding(self, text: str) -> List[float]:
        """
        调用智谱 AI 的 embedding-3 模型
        """
        try:
            if not self.client:
                print("❌ 智谱客户端未初始化 (可能是 Key 为空)")
                return []

            # 调用接口
            response = self.client.embeddings.create(
                model="embedding-3",
                input=text
            )
            # 返回向量数据
            return response.data[0].embedding

        except Exception as e:
            print(f"❌ 智谱 AI 调用失败: {e}")
            # 失败时返回空列表
            return []

    def _get_mock_embedding(self, dim: int = 1536) -> List[float]:
        """
        备用测试方法
        """
        import random
        return [random.random() for _ in range(dim)]


# 单例导出
embedding_service = EmbeddingService()