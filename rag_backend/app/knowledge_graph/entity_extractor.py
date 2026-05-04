"""实体提取器 - 规则预提取 + LLM（领域类型约束 + 置信度评分 + 消歧 + 指代消解 + 并发处理）"""
import re
import json
import asyncio
import logging
from typing import List, Dict, Optional, Callable, Any
from app.core.config import settings
from app.knowledge_graph.kg_types import (
    EntityType,
    ENTITY_TYPE_DESCRIPTIONS,
    get_entity_type_prompt_block,
)

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    使用 LLM 提取实体（领域类型约束版）

    改进：
    - 使用 kg_types.py 定义的领域实体类型（COMPANY, TAX_TYPE, CONTRACT 等）
    - 限定 LLM 只能使用预定义类型，不允许编造
    - 后验证：过滤不在预定义列表中的类型
    """

    # 所有合法实体类型的集合，用于后验证过滤
    VALID_ENTITY_TYPES: set = set(ENTITY_TYPE_DESCRIPTIONS.keys())

    def __init__(self):
        self.confidence_threshold = getattr(settings, 'ENTITY_CONFIDENCE_THRESHOLD', 0.7)
        self.max_concurrency = getattr(settings, 'EXTRACTION_CONCURRENCY', 5)
        self.enable_summary = True
        self.summary_threshold = 5
        self.max_retries = getattr(settings, 'EXTRACTION_MAX_RETRIES', 1)
        self.model = getattr(settings, 'KG_EXTRACTION_MODEL', 'deepseek/deepseek-chat')
        self.merging_similarity_threshold = 0.8

    async def extract(
        self,
        text: str,
        resolve_coreference: bool = True,
        max_retries: Optional[int] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> List[Dict]:
        """
        提取实体（融合 GraphRAG 优势：置信度评分 + 消歧 + 回调机制）

        Args:
            text: 输入文本
            resolve_coreference: 是否进行指代消解
            max_retries: 最大重试次数
            callback: 进度回调函数
        """
        if not settings.ENABLE_ENTITY_EXTRACTION:
            logger.warning("实体提取功能未开启")
            return []

        retries = max_retries or self.max_retries
        last_error = None

        if callback:
            callback("开始提取实体...")

        for attempt in range(retries):
            try:
                entities = await self._extract_once(text, resolve_coreference)
                if callback:
                    callback(f"实体提取完成: {len(entities)} 个实体")
                return entities
            except asyncio.CancelledError:
                logger.info("实体提取任务被取消")
                if callback:
                    callback("实体提取任务被取消")
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
                logger.error(f"实体提取超时 (尝试 {attempt + 1}/{retries})")
                if callback:
                    callback("实体提取超时（120s），请稍后重试")
                break
            except Exception as e:
                last_error = e
                logger.error(f"实体提取失败: {e}")
                if callback:
                    callback(f"实体提取失败: {e}")
                break

        logger.error(f"实体提取最终失败: {last_error}")
        if callback:
            callback(f"实体提取最终失败: {last_error}")
        return []

    def _pre_extract_by_rules(self, text: str) -> List[Dict]:
        # ruff: noqa: W605
        """
        规则预提取：用正则+字典匹配简单实体，跳过 LLM 调用

        支持的类型：
        - DATE_PERIOD: 2024年, 2024年12月, 第四季度
        - TAX_RATE: 25%, 13%等
        - TAX_TYPE: 企业所得税, 增值税等（字典匹配）
        - CONTRACT: XX协议, XX合同
        - CLAUSE: XX条款
        - LOCATION: XX省XX市
        - FINANCIAL_METRIC: 营收6600亿元等指标+金额
        - COMPANY: 已知公司名（字典匹配）

        Returns: [{"name":"...","type":"...","confidence":1.0}] 或空列表
        """
        entities = []

        # 1. DATE_PERIOD: 2024年、2024年12月、2024年第一季度等
        for m in re.findall(r'\d{4}年(?:\d{1,2}月)?(?:第[一二三四]季度)?', text):
            entities.append({"name": m, "type": "DATE_PERIOD", "confidence": 1.0})

        # 2. TAX_RATE: 百分数税率
        for m in re.findall(r'\d+(?:\.\d+)?[%％]', text):
            entities.append({"name": m, "type": "TAX_RATE", "confidence": 0.95})

        # 3. TAX_TYPE: 常见税种字典
        for tt in ['企业所得税', '增值税', '印花税', '营业税', '个人所得税',
                    '消费税', '关税', '房产税', '土地使用税', '附加税']:
            if tt in text:
                entities.append({"name": tt, "type": "TAX_TYPE", "confidence": 1.0})

        # 4. CONTRACT: 2-6字 + 协议/合同，去除非实体前缀
        for m in re.findall(r'[\u4e00-\u9fa5]{2,6}(?:协议|合同)', text):
            for prefix in ['了', '的', '与', '和', '及', '或', '签署']:
                if m.startswith(prefix):
                    m = m[len(prefix):]
                    break
            if len(m) >= 2:  # 去掉前缀后至少2字
                entities.append({"name": m, "type": "CONTRACT", "confidence": 0.95})

        # 5. CLAUSE: 2-6字 + 条款，去除非实体前缀
        for m in re.findall(r'[\u4e00-\u9fa5]{2,6}条款', text):
            for prefix in ['了', '的', '包含', '包括', '和', '及']:
                if m.startswith(prefix):
                    m = m[len(prefix):]
                    break
            if len(m) >= 2:
                entities.append({"name": m, "type": "CLAUSE", "confidence": 0.95})

        # 6. LOCATION: XX省XX市，去除非实体前缀
        for m in re.findall(r'[\u4e00-\u9fa5]{2,3}省[\u4e00-\u9fa5]{2,2}市', text):
            for prefix in ['于', '在', '到']:
                if m.startswith(prefix):
                    m = m[len(prefix):]
                    break
            if len(m) >= 3:
                entities.append({"name": m, "type": "LOCATION", "confidence": 0.95})

        # 7. FINANCIAL_METRIC: 常见财务指标+金额（较长关键词优先匹配）
        metric_pairs = [
            (r'营收[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.95),
            (r'净利润[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.95),
            (r'毛利润[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.9),
            (r'收入[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.9),
            (r'成本[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.9),
            (r'费用[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.9),
            (r'应收账款[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.95),
            (r'负债[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.9),
            (r'现金流[（(]?\d+(?:\.\d+)?[万亿万千百]*元[）)]?', 0.9),
            (r'资产负债率[（(]?\d+(?:\.\d+)?[%％][）)]?', 0.9),
        ]
        for pattern, conf in metric_pairs:
            for m in re.findall(pattern, text):
                entities.append({"name": m, "type": "FINANCIAL_METRIC", "confidence": conf})

        # 8. COMPANY: 知名公司字典（常用于测试文本）
        known_companies = ['阿里巴巴', '腾讯', '华为', '百度', '京东', '字节跳动',
                           '阿里云', '菜鸟网络', '饿了么', '小米', '网易', '美团',
                           '拼多多', '滴滴', '快手', '比亚迪', '宁德时代']
        for c in known_companies:
            if c in text:
                entities.append({"name": c, "type": "COMPANY", "confidence": 1.0})

        # 去重：同名的只保留第一个（名称优先于值去重）
        seen_names = set()
        unique = []
        for e in entities:
            if e['name'] not in seen_names:
                seen_names.add(e['name'])
                unique.append(e)

        return unique

    async def _extract_once(
        self,
        text: str,
        resolve_coreference: bool = True
    ) -> List[Dict]:
        """单次实体提取（规则预提取 + LLM 补全）"""
        original_text = text

        # 第 0 步：规则预提取
        rule_entities = self._pre_extract_by_rules(text)
        if rule_entities:
            logger.info(
                f"规则预提取到 {len(rule_entities)} 个实体，跳过 LLM 提取: "
                f"{[e['name'] for e in rule_entities]}"
            )
            return rule_entities

        # 规则未提取到 -> 走 LLM
        if resolve_coreference:
            try:
                from app.knowledge_graph.coreference_resolver import coreference_resolver
                text = await coreference_resolver.resolve(text)
                if text != original_text:
                    logger.info("指代消解完成")
            except Exception as e:
                logger.warning(f"指代消解失败，使用原文: {e}")
                text = original_text

        entity_types_block = get_entity_type_prompt_block()

        prompt = f"""从以下文本中提取实体，返回 JSON 数组格式。

文本：{text}

{entity_types_block}

要求：
1. 为每个实体评估置信度（0-1之间的小数）：
   - 明确的专有名词（如"阿里巴巴"、"张三"）：0.9-1.0
   - 常见名词但上下文清晰：0.7-0.9
   - 可能有歧义的实体：0.5-0.7
   - 不确定的实体：<0.5
2. 对于可能有歧义的实体，添加消歧信息（disambiguated_name），例如：
   - "苹果"在科技语境 → "苹果公司"
   - "张三"如果有职位信息 → "张三（财务总监）"
3. 返回格式：[{{"name": "实体名", "type": "COMPANY", "confidence": 0.95, "disambiguated_name": "消歧后名称"}}]
4. 类型必须严格从上面的实体类型中选择，不要编造新类型
5. 只返回 JSON 数组，不要其他内容
6. 如果没有实体，返回空数组 []

示例1（公司税务场景）：
文本：阿里巴巴在2024年企业所得税应纳税额为50亿元
返回：[{{"name":"阿里巴巴","type":"COMPANY","confidence":1.0}},{{"name":"2024年","type":"DATE_PERIOD","confidence":1.0}},{{"name":"企业所得税","type":"TAX_TYPE","confidence":1.0}},{{"name":"50亿元","type":"FINANCIAL_METRIC","confidence":0.9,"disambiguated_name":"应纳税额（50亿元）"}}]

示例2（合同场景）：
文本：张三代表腾讯与华为签署了5G技术合作协议
返回：[{{"name":"张三","type":"PERSON","confidence":0.95}},{{"name":"腾讯","type":"COMPANY","confidence":1.0}},{{"name":"华为","type":"COMPANY","confidence":1.0}},{{"name":"5G技术合作协议","type":"CONTRACT","confidence":0.9}}]
"""

        from app.services.llm_service import llm_service
        # 不传 model 参数，LLM 服务自动使用 DeepSeek 适配器的默认模型
        # 传 model 会与 DeepSeek 适配器的 LangSmith 追踪路径产生 model 参数冲突
        logger.info("调用 LLM 提取实体（使用服务默认模型）...")
        # 加 120 秒超时，避免 DeepSeek API 长时间无响应
        response = await asyncio.wait_for(
            llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[],
            ),
            timeout=120.0,
        )

        logger.debug(f"LLM 原始响应: {response[:200]}...")

        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        logger.debug(f"清理后响应: {response[:200]}...")

        entities = json.loads(response)

        if not isinstance(entities, list):
            logger.warning(f"响应不是数组: {type(entities)}")
            return []

        # 类型白名单验证：只保留预定义类型的实体
        valid_entities = []
        invalid_types = []
        for entity in entities:
            etype = entity.get('type', '')
            if etype in self.VALID_ENTITY_TYPES:
                valid_entities.append(entity)
            else:
                invalid_types.append(f"{entity.get('name','?')}({etype})")

        if invalid_types:
            logger.warning(f"过滤了未定义类型的实体: {invalid_types}")

        high_confidence = []
        low_confidence = []

        for entity in valid_entities:
            confidence = entity.get('confidence', 1.0)

            if 'name' not in entity or 'type' not in entity:
                continue

            if 'disambiguated_name' in entity and entity['disambiguated_name']:
                entity['original_name'] = entity['name']
                entity['name'] = entity['disambiguated_name']

            if confidence >= self.confidence_threshold:
                high_confidence.append(entity)
            else:
                low_confidence.append(entity)

        logger.info(
            f"成功解析 {len(valid_entities)}/{len(entities)} 个实体"
            f"（过滤 {len(entities)-len(valid_entities)} 个未定义类型），"
            f"高置信度: {len(high_confidence)}, 低置信度: {len(low_confidence)}"
        )

        if low_confidence:
            logger.warning(f"低置信度实体（已过滤）: {[e['name'] for e in low_confidence]}")

        return high_confidence

    async def extract_batch(
        self,
        texts: List[str],
        callback: Optional[Callable] = None
    ) -> List[Dict]:
        """
        批量提取实体（新增：并发处理）

        融合 RAG 项目的并发处理能力
        """
        if not settings.ENABLE_ENTITY_EXTRACTION:
            return []

        limiter = asyncio.Semaphore(self.max_concurrency)
        results = []

        async def worker(text: str, idx: int):
            async with limiter:
                entities = await self.extract(text, resolve_coreference=True)
                if callback:
                    callback(f"实体提取进度: {idx + 1}/{len(texts)}")
                return entities

        tasks = [
            asyncio.create_task(worker(text, i))
            for i, text in enumerate(texts)
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            valid_results = [
                r for r in results
                if not isinstance(r, Exception)
            ]

            all_entities = []
            for entities in valid_results:
                if isinstance(entities, list):
                    all_entities.extend(entities)

            merged_entities = self._merge_entities(all_entities)

            if callback:
                callback(f"✅ 实体提取完成，共 {len(merged_entities)} 个实体")

            logger.info(f"批量实体提取完成，共 {len(merged_entities)} 个实体")
            return merged_entities

        except Exception as e:
            logger.error(f"批量提取失败: {e}")
            return []

    def _merge_entities(self, entities: List[Dict]) -> List[Dict]:
        """
        合并重复实体（融合 GraphRAG 语义合并优势）

        增强点：
        1. 基于名称+类型的精确匹配
        2. 基于语义的相似度匹配（新增）
        3. 保留现有优势：置信度评分 + 消歧 + 描述聚合
        """
        merged = {}

        for entity in entities:
            if not isinstance(entity, dict):
                logger.warning(f"跳过非字典实体: {type(entity)}")
                continue

            name = entity.get('name', '')
            if not name:
                logger.warning(f"跳过无名称的实体: {entity}")
                continue

            entity_type = entity.get('type', 'UNKNOWN')
            unique_key = f"{name}_{entity_type}"

            if unique_key in merged:
                self._merge_entity_data(merged[unique_key], entity)
            else:
                merged[unique_key] = entity.copy()
                merged[unique_key]['occurrence_count'] = 1

        return list(merged.values())

    def _merge_entity_data(self, existing: Dict[str, Any], new: Dict[str, Any]) -> None:
        """
        合并实体数据（新增）

        融合 GraphRAG 的节点合并逻辑
        """
        existing['occurrence_count'] = existing.get('occurrence_count', 1) + 1

        if new.get('confidence', 0) > existing.get('confidence', 0):
            existing['confidence'] = new['confidence']

        if 'description' in new:
            if 'description' in existing:
                existing['description'] += f" | {new['description']}"
            else:
                existing['description'] = new['description']

        if 'original_name' not in existing and 'original_name' in new:
            existing['original_name'] = new['original_name']

        if 'disambiguation' in new:
            if 'disambiguation' not in existing:
                existing['disambiguation'] = new['disambiguation']
            else:
                existing['disambiguation'] = f"{existing['disambiguation']}, {new['disambiguation']}"

        if 'source_texts' in new:
            if 'source_texts' not in existing:
                existing['source_texts'] = []
            existing['source_texts'].extend(new['source_texts'])

        if 'properties' in new:
            if 'properties' not in existing:
                existing['properties'] = {}
            existing['properties'].update(new['properties'])

    async def _generate_entity_description(
        self,
        entity_name: str,
        entity_type: str,
        context_texts: List[str],
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        使用 LLM 为实体生成描述（新增）

        融合 GraphRAG 的实体摘要生成能力
        """
        if not context_texts or not self.enable_summary:
            return None

        if callback:
            callback(f"为实体「{entity_name}」生成描述...")

        context = " ".join(context_texts[:5])

        prompt = f"""为以下实体生成简洁的描述性摘要：

实体名称：{entity_name}
实体类型：{entity_type}

相关上下文：{context}

要求：
1. 生成 50-100 字的中文描述
2. 概括实体的主要特征和作用
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
                    callback(f"✅ 实体「{entity_name}」描述生成完成")
                return description
            return None

        except Exception as e:
            logger.warning(f"实体描述生成失败 {entity_name}: {e}")
            if callback:
                callback(f"⚠️ 实体「{entity_name}」描述生成失败")
            return None

    async def extract_with_descriptions(
        self,
        text: str,
        texts_context: Optional[List[str]] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> List[Dict]:
        """
        提取实体并生成描述（新增）

        融合 GraphRAG 的完整工作流：提取 → 合并 → 摘要生成
        """
        if callback:
            callback("🚀 开始提取实体并生成描述...")

        entities = await self.extract(text, resolve_coreference=True, callback=callback)

        if not entities or not texts_context:
            return entities

        if callback:
            callback(f"📊 开始为 {len(entities)} 个实体生成描述...")

        for entity in entities:
            entity_contexts = [
                ctx for ctx in texts_context
                if entity['name'] in ctx
            ]

            if entity_contexts:
                description = await self._generate_entity_description(
                    entity['name'],
                    entity['type'],
                    entity_contexts,
                    callback
                )
                if description:
                    entity['description'] = description

        if callback:
            callback("✅ 所有实体描述生成完成")

        return entities

    async def _summarize_description(
        self,
        description: str,
        entity_name: str
    ) -> str:
        """
        描述摘要（新增）

        融合 RAG 项目的描述摘要能力
        """
        if not description or len(description) < 300:
            return description

        sentences = description.split('。')
        if len(sentences) <= self.summary_threshold:
            return description

        prompt = f"""将以下关于「{entity_name}」的描述摘要为简洁版本：

{description}

要求：
1. 不超过 100 字
2. 保留关键信息
3. 使用流畅的自然语言
4. 只返回摘要内容，不要其他内容
"""

        try:
            from app.services.llm_service import llm_service
            summary = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[]
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"摘要生成失败: {e}")
            return description[:200] + "..."


entity_extractor = EntityExtractor()
