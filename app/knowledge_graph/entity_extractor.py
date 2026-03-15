"""实体提取器 - 使用 LLM（增强版：置信度评分 + 消歧 + 指代消解）"""
import json
from typing import List, Dict
from app.services.llm_service import llm_service
from app.core.config import settings
from app.knowledge_graph.coreference_resolver import coreference_resolver


class EntityExtractor:
    """使用 LLM 提取实体（支持置信度评分和消歧）"""
    
    def __init__(self):
        self.confidence_threshold = getattr(settings, 'ENTITY_CONFIDENCE_THRESHOLD', 0.7)
    
    async def extract(self, text: str, resolve_coreference: bool = True) -> List[Dict]:
        """
        提取实体（带置信度评分和消歧）
        
        Args:
            text: 输入文本
            resolve_coreference: 是否进行指代消解
        """
        if not settings.ENABLE_ENTITY_EXTRACTION:
            print("⚠️  实体提取功能未开启")
            return []
        
        # 1. 指代消解（可选）
        original_text = text
        if resolve_coreference:
            try:
                text = await coreference_resolver.resolve(text)
                if text != original_text:
                    print(f"   🔄 指代消解完成")
            except Exception as e:
                print(f"   ⚠️  指代消解失败，使用原文: {e}")
                text = original_text
        
        # 2. 实体提取
        prompt = f"""从以下文本中提取实体，返回 JSON 数组格式。

文本：{text}

要求：
1. 识别人名(PERSON)、地名(LOCATION)、组织(ORGANIZATION)、概念(CONCEPT)、产品(PRODUCT)等实体
2. 为每个实体评估置信度（0-1之间的小数）：
   - 明确的专有名词（如"张三"、"北京"）：0.9-1.0
   - 常见名词但上下文清晰：0.7-0.9
   - 可能有歧义的实体：0.5-0.7
   - 不确定的实体：<0.5
3. 对于可能有歧义的实体，添加消歧信息（disambiguated_name）：
   - "苹果"在科技语境 → "苹果公司"
   - "苹果"在食品语境 → "苹果（水果）"
   - "张三"如果有职位信息 → "张三（软件工程师）"
4. 返回格式：[{{"name": "实体名", "type": "类型", "confidence": 0.95, "disambiguated_name": "消歧后名称"}}]
5. 只返回 JSON 数组，不要其他内容
6. 如果没有实体，返回空数组 []

示例1：
文本：张三在北京的阿里巴巴公司担任软件工程师
返回：[{{"name":"张三","type":"PERSON","confidence":0.95,"disambiguated_name":"张三（软件工程师）"}},{{"name":"北京","type":"LOCATION","confidence":1.0}},{{"name":"阿里巴巴","type":"ORGANIZATION","confidence":1.0,"disambiguated_name":"阿里巴巴公司"}},{{"name":"软件工程师","type":"CONCEPT","confidence":0.9}}]

示例2：
文本：苹果发布了新款手机
返回：[{{"name":"苹果","type":"ORGANIZATION","confidence":0.95,"disambiguated_name":"苹果公司"}},{{"name":"手机","type":"PRODUCT","confidence":0.9}}]
"""
        
        try:
            print(f"   📤 调用 LLM 提取实体（带置信度评分）...")
            response = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[]
            )
            
            print(f"   📥 LLM 原始响应: {response[:200]}...")
            
            # 清理响应
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            print(f"   🔧 清理后响应: {response[:200]}...")
            
            entities = json.loads(response)
            
            if not isinstance(entities, list):
                print(f"   ⚠️  响应不是数组: {type(entities)}")
                return []
            
            # 过滤和分类实体
            high_confidence = []
            low_confidence = []
            
            for entity in entities:
                confidence = entity.get('confidence', 1.0)
                
                # 确保必要字段存在
                if 'name' not in entity or 'type' not in entity:
                    continue
                
                # 使用消歧后的名称（如果有）
                if 'disambiguated_name' in entity and entity['disambiguated_name']:
                    entity['original_name'] = entity['name']
                    entity['name'] = entity['disambiguated_name']
                
                if confidence >= self.confidence_threshold:
                    high_confidence.append(entity)
                else:
                    low_confidence.append(entity)
            
            print(f"   ✅ 成功解析 {len(entities)} 个实体")
            print(f"   📊 高置信度: {len(high_confidence)}, 低置信度: {len(low_confidence)}")
            
            if low_confidence:
                print(f"   ⚠️  低置信度实体（已过滤）: {[e['name'] for e in low_confidence]}")
            
            return high_confidence
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON 解析失败: {e}")
            print(f"   响应内容: {response}")
            return []
        except Exception as e:
            print(f"   ❌ 实体提取失败: {e}")
            import traceback
            traceback.print_exc()
            return []


# 全局实例
entity_extractor = EntityExtractor()
