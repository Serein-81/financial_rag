"""
工具结果格式化工具

用于格式化工具返回的结果，确保输出的一致性和可读性
"""

import re
from typing import List


class ToolResultFormatter:
    """工具结果格式化器"""

    SIMILARITY_THRESHOLD = 0.75

    @classmethod
    def format_empty_result(cls, tool_name: str = "搜索") -> str:
        """
        格式化空结果
        
        Args:
            tool_name: 工具名称
            
        Returns:
            格式化后的空结果
        """
        return "[检索结果为空]"
    
    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """
        规范化文本用于去重比较
        
        Args:
            text: 原始文本
            
        Returns:
            规范化后的文本
        """
        text = re.sub(r'\s+', '', text)
        text = text.lower()
        return text

    @classmethod
    def _calculate_text_similarity(cls, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（基于字符集重叠）
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度分数 [0, 1]
        """
        if not text1 or not text2:
            return 0.0
        
        set1 = set(cls._normalize_text(text1))
        set2 = set(cls._normalize_text(text2))
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0

    @classmethod
    def _is_duplicate_content(cls, content: str, seen_contents: List[str]) -> bool:
        """
        检查内容是否与已见内容重复
        
        Args:
            content: 待检查的内容
            seen_contents: 已见内容列表
            
        Returns:
            是否重复
        """
        normalized_new = cls._normalize_text(content)
        
        for seen in seen_contents:
            normalized_seen = cls._normalize_text(seen)
            if normalized_new == normalized_seen:
                return True
            
            similarity = cls._calculate_text_similarity(content, seen)
            if similarity > cls.SIMILARITY_THRESHOLD:
                return True
        
        return False
    
    @classmethod
    def format_knowledge_result(cls, results: List, max_content_length: int = 500) -> str:
        """
        格式化知识库检索结果，包含去重逻辑
        
        Args:
            results: 检索结果列表
            max_content_length: 每个结果的最大长度
            
        Returns:
            格式化后的结果
        """
        if not results:
            return cls.format_empty_result("知识库")
        
        formatted_results = []
        seen_contents: List[str] = []
        
        for result in results:
            content = result.content if hasattr(result, 'content') else str(result)
            
            if cls._is_duplicate_content(content, seen_contents):
                continue
            
            seen_contents.append(content)
            
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            
            metadata_parts = []
            if hasattr(result, 'source_file') and result.source_file:
                metadata_parts.append(f"来源：{result.source_file}")
            if hasattr(result, 'score') and result.score is not None:
                metadata_parts.append(f"相似度：{float(result.score):.2%}")
            if getattr(result, 'answerability_score', None) is not None:
                metadata_parts.append(f"可回答性：{float(result.answerability_score):.2%}")
            flags = getattr(result, 'evidence_flags', None) or {}
            if flags:
                quality_notes = []
                if flags.get("has_process_steps"):
                    quality_notes.append("包含流程步骤")
                elif flags.get("asks_process"):
                    quality_notes.append("缺少明确流程步骤")
                if flags.get("is_code_or_plan_fragment"):
                    quality_notes.append("偏代码/方案片段")
                if not flags.get("enough_context", True):
                    quality_notes.append("上下文不足")
                if flags.get("top_gap_clear"):
                    quality_notes.append("top1分差明显")
                if quality_notes:
                    metadata_parts.append(f"证据质量：{'、'.join(quality_notes)}")
            source = f"（{' | '.join(metadata_parts)}）" if metadata_parts else ""
            
            formatted_results.append(source + "\n" + content if source else content)
        
        if not formatted_results:
            return cls.format_empty_result("知识库")
        
        return "\n\n".join(formatted_results)
    
    @classmethod
    def is_meaningful_result(cls, text: str) -> bool:
        """
        检查工具结果是否有意义
        
        Args:
            text: 工具返回的文本
            
        Returns:
            是否有意义
        """
        if not text:
            return False
        
        empty_indicators = [
            "未找到",
            "没有找到",
            "empty",
            "no result",
            "检索结果为空",
        ]
        
        text_lower = text.lower()
        for indicator in empty_indicators:
            if indicator in text_lower:
                return False
        
        return True


tool_result_formatter = ToolResultFormatter()
