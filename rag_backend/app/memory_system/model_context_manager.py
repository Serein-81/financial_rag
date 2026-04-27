"""
模型上下文管理器 (Model Context Manager)

功能：
1. 从 OpenRouter API 获取模型上下文长度
2. 本地缓存到 JSON 文件
3. 运行时从内存字典读取
4. 支持默认值后备机制
"""

import json
import logging
import os
import tempfile
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelContextManager:
    """
    模型上下文长度管理器
    
    特性：
    1. 启动时从 OpenRouter API 获取模型上下文长度
    2. 缓存到本地 JSON 文件
    3. 运行时从内存字典读取（O(1) 复杂度）
    4. API 失败时使用本地缓存 + 默认值后备
    """
    
    DEFAULT_MODEL_LIMITS = {
        "zhipu": 128000,
        "glm-4": 128000,
        "glm-4-flash": 128000,
        "glm-4-plus": 256000,
        "claude-3-sonnet": 200000,
        "claude-3.5-sonnet": 200000,
        "claude-3-opus": 200000,
        "claude-3.5-opus": 200000,
        "claude-haiku": 200000,
        "deepseek-chat": 64000,
        "deepseek/deepseek-chat": 64000,
        "deepseek/deepseek-chat-v3-0324": 64000,
        "qwen": 32000,
        "qwen/qwen": 32000,
        "qwen/qwen3": 32000,
        "qwen/qwen3.6-plus": 32000,
        "gpt-4": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-5": 256000,
        "gemini": 128000,
        "gemini-2": 128000,
        "gemini-2.5-pro": 1048576,
        "minimax": 1000000,
        "minimax-01": 1000000,
        "llama": 32000,
        "mistral": 32000,
        "command-r": 128000,
    }
    
    DEFAULT_CONTEXT_LIMIT = 8000
    
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        cache_file_name: str = "model_context_cache.json",
        reserved_output_tokens: int = 4000
    ):
        """
        初始化模型上下文管理器
        
        Args:
            cache_dir: 缓存目录，默认为项目根目录
            cache_file_name: 缓存文件名
            reserved_output_tokens: 为输出预留的 token 数
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent
        
        self._cache_dir = Path(cache_dir)
        self._cache_file = self._cache_dir / cache_file_name
        self._reserved_output_tokens = reserved_output_tokens
        
        self._memory_cache: Dict[str, int] = {}
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    async def initialize(self) -> bool:
        """
        初始化模型上下文管理器
        
        启动时调用：
        1. 尝试从 OpenRouter API 获取模型上下文长度
        2. API 失败则读取本地缓存
        3. 本地缓存也没有则使用默认值
        
        Returns:
            bool: 是否成功初始化
        """
        logger.info("[ModelContextManager] 开始初始化...")
        
        api_success = await self._fetch_and_cache_from_api()
        
        if not api_success:
            local_success = self._load_from_cache()
            if not local_success:
                logger.warning(
                    "[ModelContextManager] API 和本地缓存都不可用，"
                    "使用默认配置"
                )
                self._use_default_limits()
        
        self._initialized = True
        logger.info(
            f"[ModelContextManager] 初始化完成 | "
            f"缓存模型数: {len(self._memory_cache)}"
        )
        
        return True
    
    async def _fetch_and_cache_from_api(self) -> bool:
        """
        从 OpenRouter API 获取模型上下文长度并缓存
        
        Returns:
            bool: 是否成功获取
        """
        try:
            import httpx
            
            logger.info("[ModelContextManager] 正在从 OpenRouter API 获取模型信息...")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.OPENROUTER_API_URL)
                response.raise_for_status()
                
                data = response.json()
                
                if "data" not in data:
                    logger.warning("[ModelContextManager] API 返回数据格式错误")
                    return False
                
                for model in data["data"]:
                    model_id = model.get("id", "")
                    context_length = model.get("context_length")
                    
                    if model_id and context_length:
                        self._memory_cache[model_id] = context_length
                        
                        if "/" in model_id:
                            provider, name = model_id.split("/", 1)
                            short_key = f"{provider}/{name.split('-')[0]}"
                            if short_key not in self._memory_cache:
                                self._memory_cache[short_key] = context_length
                
                self._save_to_cache()
                
                logger.info(
                    f"[ModelContextManager] 成功从 API 获取 {len(data['data'])} 个模型信息"
                )
                return True
                
        except ImportError:
            logger.warning("[ModelContextManager] httpx 未安装，尝试使用 requests")
            return await self._fetch_with_requests()
        except Exception as e:
            logger.warning(f"[ModelContextManager] API 请求失败: {e}")
            return False
    
    async def _fetch_with_requests(self) -> bool:
        """使用 requests 库作为后备"""
        try:
            import requests
            
            logger.info("[ModelContextManager] 使用 requests 获取模型信息...")
            
            response = requests.get(self.OPENROUTER_API_URL, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if "data" not in data:
                return False
            
            for model in data["data"]:
                model_id = model.get("id", "")
                context_length = model.get("context_length")
                
                if model_id and context_length:
                    self._memory_cache[model_id] = context_length
            
            self._save_to_cache()
            logger.info(f"[ModelContextManager] 成功获取 {len(data['data'])} 个模型信息")
            return True
            
        except Exception as e:
            logger.warning(f"[ModelContextManager] requests 请求失败: {e}")
            return False
    
    def _load_from_cache(self) -> bool:
        """
        从本地缓存文件加载

        Returns:
            bool: 是否成功加载
        """
        cache_files_to_try = [self._cache_file]

        # 如果默认路径不可读，尝试临时目录中的回退缓存
        fallback_path = Path(tempfile.gettempdir()) / "rag_cache" / self._cache_file.name
        if fallback_path.exists():
            cache_files_to_try.append(fallback_path)

        for cache_file in cache_files_to_try:
            if not cache_file.exists():
                continue

            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                if isinstance(cache_data, dict):
                    self._memory_cache = cache_data
                    self._cache_file = cache_file
                    logger.info(
                        f"[ModelContextManager] 从缓存加载了 {len(self._memory_cache)} 个模型"
                    )
                    return True
                else:
                    logger.warning(f"[ModelContextManager] 缓存文件格式错误: {cache_file}")

            except Exception as e:
                logger.warning(f"[ModelContextManager] 读取缓存失败 {cache_file}: {e}")

        logger.info("[ModelContextManager] 本地缓存文件不存在")
        return False
    
    def _save_to_cache(self) -> None:
        """保存到本地缓存文件"""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"[ModelContextManager] 已保存缓存到 {self._cache_file}")
        except PermissionError:
            # Docker 环境中 /app 可能不可写，回退到临时目录
            try:
                fallback_dir = Path(tempfile.gettempdir()) / "rag_cache"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                fallback_file = fallback_dir / self._cache_file.name
                with open(fallback_file, "w", encoding="utf-8") as f:
                    json.dump(self._memory_cache, f, ensure_ascii=False, indent=2)
                self._cache_file = fallback_file
                logger.info(f"[ModelContextManager] 已保存缓存到可写路径: {fallback_file}")
            except Exception as fallback_error:
                logger.warning(f"[ModelContextManager] 保存缓存失败 (已尝试回退): {fallback_error}")
        except Exception as e:
            logger.warning(f"[ModelContextManager] 保存缓存失败: {e}")
    
    def _use_default_limits(self) -> None:
        """使用默认的模型限制"""
        self._memory_cache = self.DEFAULT_MODEL_LIMITS.copy()
        logger.info("[ModelContextManager] 使用默认模型限制配置")
    
    def get_context_limit(self, model_name: str) -> int:
        """
        获取模型的上下文限制
        
        运行时调用，直接从内存字典读取，O(1) 复杂度
        
        Args:
            model_name: 模型名称
            
        Returns:
            int: 可用于输入的 token 数（已减去输出预留）
        """
        if not model_name:
            return self.DEFAULT_CONTEXT_LIMIT - self._reserved_output_tokens
        
        model_lower = model_name.lower()
        
        if model_name in self._memory_cache:
            return max(
                self._memory_cache[model_name] - self._reserved_output_tokens,
                self.DEFAULT_CONTEXT_LIMIT
            )
        
        for cached_model, limit in self._memory_cache.items():
            if cached_model.lower() in model_lower or model_lower in cached_model.lower():
                return max(limit - self._reserved_output_tokens, self.DEFAULT_CONTEXT_LIMIT)
        
        for pattern, limit in self.DEFAULT_MODEL_LIMITS.items():
            if pattern.lower() in model_lower or model_lower in pattern.lower():
                return max(limit - self._reserved_output_tokens, self.DEFAULT_CONTEXT_LIMIT)
        
        logger.debug(f"[ModelContextManager] 未找到模型 {model_name}，使用默认值")
        return self.DEFAULT_CONTEXT_LIMIT - self._reserved_output_tokens
    
    def get_raw_context_limit(self, model_name: str) -> int:
        """
        获取模型的原始上下文限制（不含输出预留）
        
        Args:
            model_name: 模型名称
            
        Returns:
            int: 模型的原始上下文限制
        """
        if not model_name:
            return self.DEFAULT_CONTEXT_LIMIT
        
        model_lower = model_name.lower()
        
        if model_name in self._memory_cache:
            return self._memory_cache[model_name]
        
        for cached_model, limit in self._memory_cache.items():
            if cached_model.lower() in model_lower or model_lower in cached_model.lower():
                return limit
        
        for pattern, limit in self.DEFAULT_MODEL_LIMITS.items():
            if pattern.lower() in model_lower or model_lower in pattern.lower():
                return limit
        
        return self.DEFAULT_CONTEXT_LIMIT
    
    def set_context_limit(self, model_name: str, limit: int) -> None:
        """
        手动设置模型的上下文限制
        
        Args:
            model_name: 模型名称
            limit: 上下文限制
        """
        self._memory_cache[model_name] = limit
        self._save_to_cache()
        logger.info(f"[ModelContextManager] 已设置 {model_name} 的上下文限制为 {limit}")
    
    def get_all_cached_models(self) -> Dict[str, int]:
        """
        获取所有缓存的模型及其上下文限制
        
        Returns:
            Dict[str, int]: 模型名称到上下文限制的映射
        """
        return self._memory_cache.copy()
    
    def get_total_cached_count(self) -> int:
        """获取缓存的模型数量"""
        return len(self._memory_cache)
    
    async def refresh(self) -> bool:
        """
        刷新缓存
        
        强制从 API 重新获取
        
        Returns:
            bool: 是否成功刷新
        """
        logger.info("[ModelContextManager] 正在刷新缓存...")
        return await self._fetch_and_cache_from_api()


model_context_manager = ModelContextManager()
