"""
查询优化服务
实现查询改写、多查询生成和 MMR 重排序
"""
import logging
from typing import List, Dict, Any, Optional
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """查询优化器"""
    
    async def rewrite_query(self, query: str, num_variants: int = 3) -> List[str]:
        """
        查询改写 - 生成多个不同角度的查询
        
        Args:
            query: 原始查询
            num_variants: 生成变体数量
            
        Returns:
            改写后的查询列表（包含原始查询）
        """
        try:
            prompt = f"""请将以下查询改写为{num_variants}个不同角度的问题，帮助更全面地理解用户意图。

原始查询: {query}

要求:
1. 保持原意，但从不同角度表达
2. 可以是更具体的问题，也可以是相关的问题
3. 每个问题一行，不要编号
4. 直接输出问题，不要其他解释

改写后的查询:"""

            response = await llm_service.get_answer(prompt, [], [])
            
            # 解析响应，清理编号和格式
            import re
            variants = []
            for line in response.split('\n'):
                line = line.strip()
                if not line or len(line) < 5:
                    continue
                # 移除开头的编号（如 "1. ", "2. ", "- " 等）
                line = re.sub(r'^[\d\-\*\.]+\s*', '', line)
                line = line.strip()
                if line and len(line) > 5:
                    variants.append(line)
            
            # 去重
            unique_variants = []
            seen = set()
            for v in variants:
                v_lower = v.lower()
                if v_lower not in seen:
                    seen.add(v_lower)
                    unique_variants.append(v)
            
            # 限制数量并添加原始查询
            variants = unique_variants[:num_variants]
            if query not in variants:
                variants.insert(0, query)
            
            logger.info(f"🔄 查询改写: 生成 {len(variants)} 个变体")
            return variants
            
        except Exception as e:
            logger.error(f"❌ 查询改写失败: {e}")
            return [query]  # 失败时返回原始查询
    
    async def generate_hypothetical_document(self, query: str) -> str:
        """
        HyDE (Hypothetical Document Embeddings)
        生成假设文档，用于增强检索
        
        Args:
            query: 用户查询
            
        Returns:
            假设文档内容
        """
        try:
            prompt = f"""假设你要回答以下问题，请写一段简短的文档内容（200字以内），这段内容应该包含问题的答案。

问题: {query}

要求:
1. 直接写文档内容，不要前缀说明
2. 内容要专业、准确
3. 包含关键信息和术语
4. 200字以内

文档内容:"""

            response = await llm_service.get_answer(prompt, [], [])
            
            # 清理响应
            doc = response.strip()
            if len(doc) > 500:
                doc = doc[:500]
            
            logger.info(f"📄 HyDE: 生成假设文档 ({len(doc)} 字)")
            return doc
            
        except Exception as e:
            logger.error(f"❌ HyDE 生成失败: {e}")
            return query  # 失败时返回原始查询
    
    def mmr_rerank(
        self,
        results: List[Dict[str, Any]],
        query_embedding: List[float],
        lambda_param: float = 0.5,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        MMR (Maximal Marginal Relevance) 重排序
        平衡相关性和多样性
        
        Args:
            results: 检索结果列表，每个结果需要有 'embedding' 和 'score'
            query_embedding: 查询向量
            lambda_param: 平衡参数 (0-1)，越大越重视相关性，越小越重视多样性
            top_k: 返回结果数量
            
        Returns:
            重排序后的结果
        """
        if not results:
            return []
        
        try:
            import math
            
            # 如果结果没有 embedding，直接返回
            if not all('embedding' in r for r in results):
                logger.warning("⚠️ 结果缺少 embedding，跳过 MMR 重排")
                return results[:top_k] if top_k else results
            
            selected = []
            remaining = results.copy()
            
            # 计算余弦相似度
            def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
                dot_product = sum(a * b for a, b in zip(vec1, vec2))
                norm1 = math.sqrt(sum(a * a for a in vec1))
                norm2 = math.sqrt(sum(b * b for b in vec2))
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                return dot_product / (norm1 * norm2)
            
            # 选择第一个（最相关的）
            if remaining:
                first = max(remaining, key=lambda x: x.get('score', 0))
                selected.append(first)
                remaining.remove(first)
            
            # 迭代选择剩余结果
            target_count = top_k if top_k else len(results)
            while remaining and len(selected) < target_count:
                best_score = -float('inf')
                best_item = None
                
                for item in remaining:
                    # 相关性分数
                    relevance = cosine_similarity(query_embedding, item['embedding'])
                    
                    # 多样性分数（与已选择结果的最大相似度）
                    max_similarity = max(
                        cosine_similarity(item['embedding'], s['embedding'])
                        for s in selected
                    )
                    
                    # MMR 分数
                    mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                    
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_item = item
                
                if best_item:
                    selected.append(best_item)
                    remaining.remove(best_item)
                else:
                    break
            
            logger.info(f"🎯 MMR 重排: {len(selected)} 个结果 (λ={lambda_param})")
            return selected
            
        except Exception as e:
            logger.error(f"❌ MMR 重排失败: {e}")
            return results[:top_k] if top_k else results
    
    async def optimize_context(
        self,
        results: List[Dict[str, Any]],
        max_tokens: int = 2000
    ) -> str:
        """
        优化上下文构建
        去重、压缩、排序
        
        Args:
            results: 检索结果
            max_tokens: 最大 token 数
            
        Returns:
            优化后的上下文字符串
        """
        if not results:
            return ""
        
        try:
            # 1. 去重（基于内容相似度）
            unique_results = []
            seen_contents = set()
            
            for result in results:
                content = result.get('content', '')
                # 简单去重：检查前50个字符
                content_key = content[:50].strip()
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    unique_results.append(result)
            
            # 2. 按分数排序（最相关的在前）
            unique_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 3. 构建上下文（控制长度）
            context_parts = []
            current_length = 0
            max_chars = max_tokens * 4  # 粗略估计：1 token ≈ 4 字符
            
            for i, result in enumerate(unique_results):
                content = result.get('content', '')
                source = result.get('source_file', '未知来源')
                
                # 格式化片段
                snippet = f"[片段 {i+1}] (来源: {source})\n{content}\n"
                
                if current_length + len(snippet) > max_chars:
                    # 如果超过限制，截断最后一个片段
                    remaining = max_chars - current_length
                    if remaining > 100:  # 至少保留100字符
                        snippet = snippet[:remaining] + "...\n"
                        context_parts.append(snippet)
                    break
                
                context_parts.append(snippet)
                current_length += len(snippet)
            
            context = "\n".join(context_parts)
            
            logger.info(f"📝 上下文优化: {len(unique_results)} 个片段 → {len(context_parts)} 个片段 ({current_length} 字符)")
            return context
            
        except Exception as e:
            logger.error(f"❌ 上下文优化失败: {e}")
            # 失败时简单拼接
            return "\n\n".join(r.get('content', '') for r in results[:5])
    
    async def detect_query_intent(self, query: str) -> Dict[str, Any]:
        """
        检测查询意图
        
        Args:
            query: 用户查询
            
        Returns:
            意图信息字典
        """
        intent = {
            "type": "general",  # general, summary, factual, comparison, how-to
            "needs_more_context": False,
            "suggested_top_k": 5,
            "suggested_threshold": 0.3
        }
        
        # 总结类查询
        if any(word in query for word in ["总结", "概括", "归纳", "思想", "全文", "讲了什么", "主要内容"]):
            intent["type"] = "summary"
            intent["needs_more_context"] = True
            intent["suggested_top_k"] = 15
            intent["suggested_threshold"] = 0.25
        
        # 事实类查询
        elif any(word in query for word in ["什么是", "定义", "解释", "是什么"]):
            intent["type"] = "factual"
            intent["suggested_top_k"] = 3
            intent["suggested_threshold"] = 0.4
        
        # 对比类查询
        elif any(word in query for word in ["对比", "比较", "区别", "差异", "vs", "和"]):
            intent["type"] = "comparison"
            intent["needs_more_context"] = True
            intent["suggested_top_k"] = 10
            intent["suggested_threshold"] = 0.3
        
        # 操作类查询
        elif any(word in query for word in ["如何", "怎么", "怎样", "步骤", "方法"]):
            intent["type"] = "how-to"
            intent["suggested_top_k"] = 8
            intent["suggested_threshold"] = 0.35
        
        logger.info(f"🎯 查询意图: {intent['type']} (top_k={intent['suggested_top_k']})")
        return intent


# 全局实例
query_optimizer = QueryOptimizer()
