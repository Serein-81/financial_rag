"""
查询优化服务
实现查询改写、多查询生成和 MMR 重排序
"""
import logging
import os
from typing import List, Dict, Any, Optional
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self):
        """初始化查询优化器"""
        self.enable_mmr = os.getenv('ENABLE_MMR', 'true').lower() == 'true'
        self.mmr_lambda_param = float(os.getenv('MMR_LAMBDA', '0.9'))
        self.mmr_max_results = int(os.getenv('MMR_MAX_RESULTS', '20'))
        
        logger.info(
            f"🔧 查询优化器配置: "
            f"MMR={'开启' if self.enable_mmr else '关闭'}, "
            f"lambda={self.mmr_lambda_param}, "
            f"max_results={self.mmr_max_results}"
        )
    
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
    
    async def detect_query_intent(self, query: str) -> Dict[str, Any]:
        """
        检测查询意图
        
        用于判断是否需要启用 MMR 多样性优化
        
        Args:
            query: 用户查询
            
        Returns:
            意图检测结果
        """
        diversity_keywords = [
            "不同", "各种", "多种", "多样化", "相关", "例子",
            "案例", "文章", "材料", "文档", "资料",
            "有没有", "都有哪些", "分别有哪些"
        ]
        
        precision_keywords = [
            "规定", "条款", "第", "条", "税率", "公式",
            "计算", "如何", "怎样", "步骤", "流程",
            "具体", "准确", "正确", "哪个"
        ]
        
        query_lower = query.lower()
        
        diversity_score = sum(1 for kw in diversity_keywords if kw in query_lower)
        precision_score = sum(1 for kw in precision_keywords if kw in query_lower)
        
        if diversity_score > precision_score:
            intent_type = "diversity"
            needs_mmr = True
            suggested_lambda = 0.6
        else:
            intent_type = "precision"
            needs_mmr = False
            suggested_lambda = 0.95
        
        return {
            "type": intent_type,
            "needs_more_context": diversity_score > 0,
            "needs_mmr": needs_mmr,
            "suggested_lambda": suggested_lambda,
            "suggested_top_k": 5 if precision_score > diversity_score else 10,
            "suggested_threshold": 0.5 if precision_score > diversity_score else 0.3
        }
    
    def mmr_rerank(
        self,
        results: List[Dict[str, Any]],
        query_embedding: List[float],
        lambda_param: float = None,
        top_k: Optional[int] = None,
        force_diversity: bool = False
    ) -> List[Dict[str, Any]]:
        """
        MMR (Maximal Marginal Relevance) 重排序
        平衡相关性和多样性
        
        Args:
            results: 检索结果列表，每个结果需要有 'embedding' 和 'score'
            query_embedding: 查询向量
            lambda_param: 平衡参数 (0-1)，越大越重视相关性，越小越重视多样性
                          默认使用配置值（精确场景为 0.9，多样性场景为 0.6）
            top_k: 返回结果数量
            force_diversity: 强制启用多样性模式
            
        Returns:
            重排序后的结果
        """
        if not results:
            return []
        
        if lambda_param is None:
            lambda_param = self.mmr_lambda_param
        
        if not force_diversity and lambda_param >= 0.9:
            logger.info(f"🎯 高精度模式 (λ={lambda_param})，跳过 MMR 多样性筛选，直接按相关性排序")
            sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
            return sorted_results[:top_k] if top_k else sorted_results
        
        try:
            import numpy as np
            
            query_emb = np.array(query_embedding, dtype=np.float32)
            query_norm = np.linalg.norm(query_emb)
            if query_norm > 0:
                query_emb = query_emb / query_norm
            
            embeddings = []
            for r in results:
                emb = r.get('embedding')
                if emb:
                    if isinstance(emb, list):
                        embeddings.append(np.array(emb, dtype=np.float32))
                    else:
                        embeddings.append(emb)
                else:
                    embeddings.append(None)
            
            relevance_scores = []
            for emb in embeddings:
                if emb is not None:
                    emb_norm = np.linalg.norm(emb)
                    if emb_norm > 0:
                        emb = emb / emb_norm
                    score = np.dot(query_emb, emb)
                    relevance_scores.append(float(score))
                else:
                    relevance_scores.append(r.get('score', 0))
            
            selected = []
            remaining_indices = list(range(len(results)))
            
            first_idx = max(remaining_indices, key=lambda i: relevance_scores[i])
            selected.append(first_idx)
            remaining_indices.remove(first_idx)
            
            target_count = min(top_k if top_k else len(results), len(results))
            while remaining_indices and len(selected) < target_count:
                best_score = -float('inf')
                best_idx = None
                
                for idx in remaining_indices:
                    relevance = relevance_scores[idx]
                    
                    max_similarity = 0.0
                    if selected and embeddings[idx] is not None:
                        sims = []
                        for sel_idx in selected:
                            if embeddings[sel_idx] is not None:
                                sim = np.dot(embeddings[idx], embeddings[sel_idx])
                                sims.append(sim)
                        if sims:
                            max_similarity = max(sims)
                    
                    mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                    
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = idx
                
                if best_idx is not None:
                    selected.append(best_idx)
                    remaining_indices.remove(best_idx)
                else:
                    break
            
            selected_results = [results[i] for i in selected]
            
            logger.info(f"🎯 MMR 重排: {len(selected_results)} 个结果 (λ={lambda_param}, 模式={'多样性' if force_diversity else '自适应'})")
            return selected_results
            
        except ImportError:
            logger.warning("⚠️ NumPy 不可用，使用纯 Python 实现")
            return self._mmr_rerank_python(results, query_embedding, lambda_param, top_k)
        except Exception as e:
            logger.error(f"❌ MMR 重排失败: {e}")
            return results[:top_k] if top_k else results
    
    def _mmr_rerank_python(
        self,
        results: List[Dict[str, Any]],
        query_embedding: List[float],
        lambda_param: float,
        top_k: Optional[int]
    ) -> List[Dict[str, Any]]:
        """
        纯 Python 实现的 MMR（备用）
        注意：性能较差，生产环境建议安装 NumPy
        """
        import math
        
        def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = math.sqrt(sum(a * a for a in vec1))
            norm2 = math.sqrt(sum(b * b for b in vec2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
        
        selected = []
        remaining = results.copy()
        
        if remaining:
            first = max(remaining, key=lambda x: x.get('score', 0))
            selected.append(first)
            remaining.remove(first)
        
        target_count = top_k if top_k else len(results)
        while remaining and len(selected) < target_count:
            best_score = -float('inf')
            best_item = None
            
            for item in remaining:
                relevance = cosine_similarity(query_embedding, item['embedding'])
                
                max_similarity = 0.0
                if selected:
                    for s in selected:
                        sim = cosine_similarity(item['embedding'], s['embedding'])
                        if sim > max_similarity:
                            max_similarity = sim
                
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item
            
            if best_item:
                selected.append(best_item)
                remaining.remove(best_item)
            else:
                break
        
        return selected
    
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
