"""关系提取器 - 使用 LLM（领域类型约束 + 并发处理 + 批量提取 + 智能合并）"""
import json
import asyncio
import logging
from typing import List, Dict, Optional, Callable, Any
from app.core.config import settings
from app.knowledge_graph.kg_types import (
    RelationType,
    RELATION_TYPE_DESCRIPTIONS,
    get_relation_type_prompt_block,
)

logger = logging.getLogger(__name__)


class RelationExtractor:
    """
    使用 LLM 提取实体关系（领域类型约束版）

    改进：
    - 使用 kg_types.py 定义的关系类型（WORKS_AT, SIGNED, SUBJECT_TO 等）
    - 限定 LLM 只能使用预定义类型，不允许编造
    - 后验证：过滤不在预定义列表中的类型
    """

    # 所有合法关系类型的集合，用于后验证过滤
    VALID_RELATION_TYPES: set = set(RELATION_TYPE_DESCRIPTIONS.keys())

    def __init__(self):
        self.max_concurrency = getattr(settings, 'EXTRACTION_CONCURRENCY', 5)
        self.max_retries = getattr(settings, 'EXTRACTION_MAX_RETRIES', 1)
        self.model = getattr(settings, 'KG_EXTRACTION_MODEL', 'deepseek/deepseek-chat')
        self.enable_description = True

    async def extract(
        self,
        text: str,
        entities: List[Dict],
        max_retries: Optional[int] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> List[Dict]:
        """
        提取关系（融合 GraphRAG 优势：错误恢复 + 回调机制 + LLM描述）

        Args:
            text: 输入文本
            entities: 已提取的实体列表
            max_retries: 最大重试次数
            callback: 进度回调函数
        """
        if not settings.ENABLE_RELATION_EXTRACTION or not entities:
            return []

        retries = max_retries or self.max_retries
        last_error = None

        if callback:
            callback("开始提取关系...")

        for attempt in range(retries):
            try:
                relations = await self._extract_once(text, entities)
                if callback:
                    callback(f"关系提取完成: {len(relations)} 个关系")
                return relations
            except asyncio.CancelledError:
                logger.info("关系提取任务被取消")
                if callback:
                    callback("关系提取任务被取消")
                return []
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"JSON 解析失败 (尝试 {attempt + 1}/{retries}): {e}")
                if callback:
                    callback(f"JSON 解析失败 (尝试 {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    await asyncio.sleep(1)
            except asyncio.TimeoutError:
                last_error = TimeoutError("LLM 调用超时（120s），请检查 DeepSeek API 状态或稍后重试")
                logger.error(f"关系提取超时 (尝试 {attempt + 1}/{retries})")
                if callback:
                    callback("关系提取超时（120s），请稍后重试")
                break
            except Exception as e:
                last_error = e
                logger.error(f"关系提取失败: {e}")
                if callback:
                    callback(f"关系提取失败: {e}")
                break

        logger.error(f"关系提取最终失败: {last_error}")
        if callback:
            callback(f"关系提取最终失败: {last_error}")
        return []

    async def _extract_once(
        self,
        text: str,
        entities: List[Dict]
    ) -> List[Dict]:
        """单次关系提取（使用预定义关系类型，限制实体数量避免提示词过长）"""
        # 按置信度排序，取前10个最核心的实体
        # 避免 29 个实体全列到提示词里导致 DeepSeek 处理超时
        sorted_entities = sorted(
            entities,
            key=lambda e: e.get('confidence', 1.0),
            reverse=True
        )[:10]
        entity_names = [e['name'] for e in sorted_entities]
        relation_types_block = get_relation_type_prompt_block()

        prompt = f"""从文本中识别实体之间的关系，返回 JSON 数组格式。

文本：{text}
已提取的实体：{', '.join(entity_names)}

{relation_types_block}

要求：
1. 关系类型必须严格从上面定义的类型中选择，不要编造新类型
2. source 和 target 必须在已提取的实体列表中
3. 为每个关系评估置信度（0-1之间的小数）：
   - 明确的关系：0.9-1.0
   - 较明确的关系：0.7-0.9
   - 可能存在的关系：0.5-0.7
   - 不确定的关系：<0.5
4. 返回格式：[{{"source":"实体1","target":"实体2","type":"WORKS_AT","confidence":0.95}}]
5. 只返回 JSON 数组，不要其他内容
6. 如果没有关系，返回空数组 []

示例（公司税务场景）：
文本：阿里巴巴2023年营收8687亿元，适用企业所得税25%税率
实体：阿里巴巴, 2023年, 8687亿元, 企业所得税, 25%
返回：[{{"source":"阿里巴巴","target":"营收","type":"HAS_METRIC","confidence":0.95}},{{"source":"阿里巴巴","target":"企业所得税","type":"SUBJECT_TO","confidence":0.95}},{{"source":"企业所得税","target":"25%","type":"HAS_RATE","confidence":0.95}}]

示例（合同场景）：
文本：张三代表腾讯与华为签署了5G技术合作协议
实体：张三, 腾讯, 华为, 5G技术合作协议
返回：[{{"source":"张三","target":"腾讯","type":"WORKS_AT","confidence":0.95}},{{"source":"腾讯","target":"5G技术合作协议","type":"SIGNED","confidence":0.9}},{{"source":"华为","target":"5G技术合作协议","type":"SIGNED","confidence":0.9}}]
"""

        from app.services.llm_service import llm_service
        logger.info(
            "调用 LLM 提取关系（使用服务默认模型），"
            f"实体数: {len(entity_names)}（从 {len(entities)} 中取了前10个）..."
        )
        # 给 DeepSeek API 加 120 秒超时，避免无限等待
        response = await asyncio.wait_for(
            llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[],
            ),
            timeout=120.0,
        )

        logger.info(f"LLM 响应收到，长度: {len(response)} 字符")

        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        logger.info(f"准备解析 JSON，长度: {len(response)}")

        relations = json.loads(response)

        logger.info(f"JSON 解析完成，关系数量: {len(relations)}")

        if not isinstance(relations, list):
            logger.warning(f"关系提取响应不是数组: {type(relations)}")
            return []

        # 过滤：必须包含 source/target，且类型必须在预定义集合中
        filtered_relations = []
        invalid_type_count = 0
        for r in relations:
            if not isinstance(r, dict) or 'source' not in r or 'target' not in r:
                continue
            rtype = r.get('type', '')
            if rtype not in self.VALID_RELATION_TYPES:
                invalid_type_count += 1
                logger.debug(f"跳过未定义的关系类型: {rtype} ({r.get('source')}→{r.get('target')})")
                continue
            filtered_relations.append(r)

        if invalid_type_count:
            logger.warning(
                f"过滤了 {invalid_type_count} 个未定义类型的关系"
                f"（仅保留 {len(filtered_relations)} 个有效关系）"
            )

        logger.info(f"成功提取 {len(filtered_relations)} 个关系")
        return filtered_relations

    async def extract_batch(
        self,
        texts: List[str],
        entities_per_text: List[List[Dict]],
        callback: Optional[Callable] = None
    ) -> List[Dict]:
        """
        批量提取关系（新增：并发处理）

        融合 RAG 项目的并发处理能力
        """
        if not settings.ENABLE_RELATION_EXTRACTION:
            return []

        if len(texts) != len(entities_per_text):
            logger.error("文本数量和实体列表数量不匹配")
            return []

        limiter = asyncio.Semaphore(self.max_concurrency)

        async def worker(text: str, entities: List[Dict], idx: int):
            async with limiter:
                relations = await self.extract(text, entities)
                if callback:
                    callback(f"关系提取进度: {idx + 1}/{len(texts)}")
                return relations

        tasks = [
            asyncio.create_task(worker(text, entities, i))
            for i, (text, entities) in enumerate(zip(texts, entities_per_text))
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_relations = []
            for relations in results:
                if not isinstance(relations, Exception) and isinstance(relations, list):
                    all_relations.extend(relations)

            merged_relations = self._merge_relations(all_relations)

            if callback:
                callback(f"✅ 关系提取完成，共 {len(merged_relations)} 个关系")

            logger.info(f"批量关系提取完成，共 {len(merged_relations)} 个关系")
            return merged_relations

        except Exception as e:
            logger.error(f"批量关系提取失败: {e}")
            return []

    def _merge_relations(self, relations: List[Dict]) -> List[Dict]:
        """
        合并重复关系（融合 GraphRAG 语义合并优势）

        增强点：
        1. 基于 source+target+type 的精确匹配
        2. 基于语义的反向关系匹配（新增）
        3. 保留现有优势：置信度聚合 + 权重累加
        """
        merged = {}

        for relation in relations:
            if not isinstance(relation, dict):
                logger.warning(f"跳过非字典关系: {type(relation)}")
                continue

            source = relation.get('source', '')
            target = relation.get('target', '')

            if not source or not target:
                logger.warning(f"跳过无源或目标的的关系: {relation}")
                continue

            relation_type = relation.get('type', 'RELATED_TO')

            key = f"{source}|{target}|{relation_type}"

            if key in merged:
                self._merge_relation_data(merged[key], relation)
            else:
                reverse_key = f"{target}|{source}|{relation_type}"
                if reverse_key in merged:
                    self._merge_relation_data(merged[reverse_key], relation)
                    merged[reverse_key]['is_directed'] = True
                else:
                    relation_copy = relation.copy()
                    relation_copy['weight'] = relation_copy.get('weight', 1)
                    relation_copy['occurrence_count'] = 1
                    merged[key] = relation_copy

        return list(merged.values())

    def _merge_relation_data(self, existing: Dict[str, Any], new: Dict[str, Any]) -> None:
        """
        合并关系数据（新增）

        融合 GraphRAG 的边合并逻辑
        """
        existing['occurrence_count'] = existing.get('occurrence_count', 1) + 1

        if new.get('confidence', 0) > existing.get('confidence', 0):
            existing['confidence'] = new['confidence']

        if 'description' in new:
            if 'description' in existing:
                existing['description'] += f" | {new['description']}"
            else:
                existing['description'] = new['description']

        if 'weight' in new:
            existing['weight'] = existing.get('weight', 1.0) + new['weight']
        else:
            existing['weight'] = existing.get('weight', 1.0) + 1

        if 'source_texts' in new:
            if 'source_texts' not in existing:
                existing['source_texts'] = []
            existing['source_texts'].extend(new['source_texts'])

        if 'properties' in new:
            if 'properties' not in existing:
                existing['properties'] = {}
            existing['properties'].update(new['properties'])

    async def _generate_relation_description(
        self,
        source: str,
        target: str,
        relation_type: str,
        context_texts: List[str],
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        使用 LLM 为关系生成描述（新增）

        融合 GraphRAG 的关系摘要生成能力
        """
        if not context_texts or not self.enable_description:
            return None

        if callback:
            callback(f"为关系「{source}-{relation_type}-{target}」生成描述...")

        context = " ".join(context_texts[:3])

        prompt = f"""为以下关系生成简洁的描述性摘要：

源实体：{source}
目标实体：{target}
关系类型：{relation_type}

相关上下文：{context}

要求：
1. 生成 30-50 字的中文描述
2. 概括关系的具体含义
3. 如果上下文不足以生成有意义的描述，返回 null
4. 只返回描述内容，不要其他内容
"""

        try:
            from app.services.llm_service import llm_service
            description = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[]
            )

            description = description.strip()
            if description and description != "null":
                if callback:
                    callback(f"✅ 关系「{source}-{relation_type}-{target}」描述生成完成")
                return description
            return None

        except Exception as e:
            logger.warning(f"关系描述生成失败 {source}-{target}: {e}")
            if callback:
                callback(f"⚠️ 关系「{source}-{relation_type}-{target}」描述生成失败")
            return None

    async def extract_with_descriptions(
        self,
        text: str,
        entities: List[Dict],
        texts_context: Optional[List[str]] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> List[Dict]:
        """
        提取关系并生成描述（新增）

        融合 GraphRAG 的完整工作流：提取 → 合并 → 摘要生成
        """
        if callback:
            callback("🚀 开始提取关系并生成描述...")

        relations = await self.extract(text, entities, callback=callback)

        if not relations or not texts_context:
            return relations

        if callback:
            callback(f"📊 开始为 {len(relations)} 个关系生成描述...")

        for relation in relations:
            source = relation.get('source', '')
            target = relation.get('target', '')
            relation_type = relation.get('type', 'RELATED_TO')

            relation_contexts = [
                ctx for ctx in texts_context
                if source in ctx and target in ctx
            ]

            if relation_contexts:
                description = await self._generate_relation_description(
                    source,
                    target,
                    relation_type,
                    relation_contexts,
                    callback
                )
                if description:
                    relation['description'] = description

        if callback:
            callback("✅ 所有关系描述生成完成")

        return relations


relation_extractor = RelationExtractor()
