"""
Token 计数器

使用 tiktoken 库进行精确的 Token 计数
支持多种编码模型
"""

import tiktoken
from typing import List, Dict, Union
import logging

logger = logging.getLogger(__name__)


class TokenTracker:
    """
    Token 计数器
    
    基于 tiktoken 提供精确的 Token 计数功能
    
    支持的编码模型:
    - cl100k_base (GPT-4, GPT-3.5-turbo, text-embedding-ada-002)
    - p50k_base (Codex, text-davinci-002)
    - p50k_edit (text-davinci-edit-001)
    - r50k_base (GPT-3, davinci)
    """
    
    ENCODING_MODELS = {
        "gpt-4": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-embedding-ada-002": "cl100k_base",
        "glm-4": "cl100k_base",
        "glm-3-turbo": "cl100k_base",
        "claude": "cl100k_base",
        "minimax": "cl100k_base",
        "default": "cl100k_base"
    }
    
    def __init__(self, model: str = "gpt-3.5-turbo"):
        """
        初始化 Token 计数器
        
        Args:
            model: 模型名称，用于选择编码
        """
        self.model = model
        self._cached_encodings: Dict[str, tiktoken.Encoding] = {}
        self._encoding = self._get_encoding(model)
    
    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """获取编码器"""
        encoding_name = self.ENCODING_MODELS.get(model, "cl100k_base")
        
        if encoding_name not in self._cached_encodings:
            try:
                self._cached_encodings[encoding_name] = tiktoken.get_encoding(encoding_name)
            except (ValueError, KeyError) as e:
                logger.warning(f"[TokenTracker] 无法加载编码 {encoding_name}数据错误: {e}, 使用 cl100k_base")
                self._cached_encodings[encoding_name] = tiktoken.get_encoding("cl100k_base")
            except (OSError, IOError) as e:
                logger.warning(f"[TokenTracker] 无法加载编码 {encoding_name}IO错误: {e}, 使用 cl100k_base")
                self._cached_encodings[encoding_name] = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning(f"[TokenTracker] 无法加载编码 {encoding_name}: {e}, 使用 cl100k_base")
                self._cached_encodings[encoding_name] = tiktoken.get_encoding("cl100k_base")
        
        return self._cached_encodings[encoding_name]
    
    def count_tokens(self, text: str) -> int:
        """
        计算单个文本的 Token 数量
        
        Args:
            text: 输入文本
            
        Returns:
            Token 数量
        """
        if not text:
            return 0
        
        try:
            return len(self._encoding.encode(text))
        except (ValueError, KeyError) as e:
            logger.warning(f"[TokenTracker] Token 计数数据错误: {e}")
            return self._estimate_tokens_fallback(text)
        except (OSError, IOError) as e:
            logger.warning(f"[TokenTracker] Token 计数IO错误: {e}")
            return self._estimate_tokens_fallback(text)
        except Exception as e:
            logger.warning(f"[TokenTracker] Token 计数失败: {e}")
            return self._estimate_tokens_fallback(text)
    
    def count_messages_tokens(self, messages: List[Dict[str, str]], role_key: str = "role") -> int:
        """
        计算消息列表的总 Token 数量
        
        使用 ChatML 格式计算：
        - 每条消息有额外的 3-4 个 Token (角色标记、名称等)
        - 消息之间有空分隔符
        
        Args:
            messages: 消息列表，每条消息包含 role 和 content
            role_key: 角色字段名
            
        Returns:
            总 Token 数量
        """
        if not messages:
            return 0
        
        total_tokens = 0
        
        for message in messages:
            role = message.get(role_key, "user")
            content = message.get("content", "")
            
            if content:
                content_tokens = self.count_tokens(content)
                total_tokens += content_tokens
            
            total_tokens += self._get_message_overhead(role)
        
        return total_tokens
    
    def _get_message_overhead(self, role: str) -> int:
        """
        获取消息的开销 Token 数
        
        ChatML 格式:
        - <|im_start|> + role + "\n" = ~4 tokens
        - <|im_end|> = ~1 token
        
        Args:
            role: 角色名称
            
        Returns:
            开销 Token 数
        """
        overhead_per_role = {
            "system": 4,
            "user": 4,
            "assistant": 4,
            "tool": 4,
            "function": 4
        }
        return overhead_per_role.get(role, 4)
    
    def count_messages_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        role_key: str = "role"
    ) -> int:
        """
        计算包含工具定义的 Token 数量
        
        Args:
            messages: 消息列表
            tools: 工具定义列表
            role_key: 角色字段名
            
        Returns:
            总 Token 数量
        """
        message_tokens = self.count_messages_tokens(messages, role_key)
        tool_tokens = self.count_tools_tokens(tools)
        
        return message_tokens + tool_tokens
    
    def count_tools_tokens(self, tools: List[Dict]) -> int:
        """
        计算工具定义的 Token 数量
        
        Args:
            tools: 工具定义列表
            
        Returns:
            Token 数量
        """
        if not tools:
            return 0
        
        total_tokens = 0
        tools_header = '{"role": "system", "content": "You are a helpful assistant with access to the following tools:' 
        total_tokens += self.count_tokens(tools_header)
        
        for tool in tools:
            tool_str = str(tool)
            total_tokens += self.count_tokens(tool_str)
        
        tools_footer = '"}'
        total_tokens += self.count_tokens(tools_footer)
        
        return total_tokens
    
    def estimate_completion_tokens(self, prompt_tokens: int, max_tokens: int = 1000) -> int:
        """
        估算完成（Completion）可用的 Token 数
        
        Args:
            prompt_tokens: 提示（Prompt）使用的 Token 数
            max_tokens: 模型最大 Token 数
            
        Returns:
            可用于生成的 Token 数
        """
        return max(0, max_tokens - prompt_tokens)
    
    def truncate_to_tokens(self, text: str, max_tokens: int, direction: str = "start") -> str:
        """
        截断文本到指定 Token 数
        
        Args:
            text: 输入文本
            max_tokens: 最大 Token 数
            direction: 截断方向 ("start" 从开头, "end" 从结尾)
            
        Returns:
            截断后的文本
        """
        if not text:
            return text
        
        tokens = self._encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        if direction == "end":
            truncated_tokens = tokens[-max_tokens:]
        else:
            truncated_tokens = tokens[:max_tokens]
        
        return self._encoding.decode(truncated_tokens)
    
    def split_by_tokens(
        self, 
        text: str, 
        max_tokens_per_chunk: int,
        overlap_tokens: int = 0
    ) -> List[str]:
        """
        按 Token 数分割文本
        
        Args:
            text: 输入文本
            max_tokens_per_chunk: 每个块的最大 Token 数
            overlap_tokens: 相邻块之间的重叠 Token 数
            
        Returns:
            分割后的文本块列表
        """
        if not text:
            return []
        
        tokens = self._encoding.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = start + max_tokens_per_chunk
            chunk_tokens = tokens[start:end]
            chunks.append(self._encoding.decode(chunk_tokens))
            start = end - overlap_tokens
        
        return chunks
    
    def _estimate_tokens_fallback(self, text: str) -> int:
        """
        回退的 Token 估算方法（当 tiktoken 失败时）
        
        简单估算：平均 1 Token ≈ 4 字符（中文）或 0.75 单词（英文）
        
        Args:
            text: 输入文本
            
        Returns:
            估算的 Token 数
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        return int(chinese_chars / 2) + int(other_chars / 4)
    
    def get_token_info(self, text: str) -> Dict[str, Union[int, str]]:
        """
        获取文本的详细 Token 信息
        
        Args:
            text: 输入文本
            
        Returns:
            包含详细信息的字典
        """
        return {
            "text": text[:100] + "..." if len(text) > 100 else text,
            "char_count": len(text),
            "token_count": self.count_tokens(text),
            "encoding": self.model,
            "estimated": False
        }


token_tracker = TokenTracker()
