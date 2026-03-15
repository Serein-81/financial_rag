"""关系提取器 - 使用 LLM"""
import json
from typing import List, Dict
from app.services.llm_service import llm_service
from app.core.config import settings


class RelationExtractor:
    """使用 LLM 提取实体关系"""
    
    async def extract(self, text: str, entities: List[Dict]) -> List[Dict]:
        """提取关系"""
        if not settings.ENABLE_RELATION_EXTRACTION or not entities:
            return []
        
        entity_names = [e['name'] for e in entities]
        
        prompt = f"""从文本中识别实体之间的关系，返回 JSON 数组格式。

文本：{text}
实体：{', '.join(entity_names)}

要求：
1. 识别实体之间的关系（如：工作于、位于、属于等）
2. 返回格式：[{{"source":"实体1","target":"实体2","type":"关系类型"}}]
3. 只返回 JSON 数组，不要其他内容
4. 如果没有关系，返回空数组 []

示例：
文本：张三在北京的阿里巴巴公司工作
实体：张三, 北京, 阿里巴巴
返回：[{{"source":"张三","target":"阿里巴巴","type":"工作于"}},{{"source":"阿里巴巴","target":"北京","type":"位于"}}]
"""
        
        try:
            response = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[]
            )
            
            # 清理响应
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            relations = json.loads(response)
            return relations if isinstance(relations, list) else []
        except Exception as e:
            print(f"❌ 关系提取失败: {e}")
            return []


# 全局实例
relation_extractor = RelationExtractor()
