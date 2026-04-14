"""
提示词加载基类
"""

import os
from pathlib import Path
from typing import Optional, Dict


class PromptLoader:
    """提示词加载器"""
    
    _cache: Dict[str, str] = {}
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        if prompts_dir is None:
            self.prompts_dir = Path(__file__).parent
        else:
            self.prompts_dir = prompts_dir
    
    def load(self, file_path: str, use_cache: bool = True) -> str:
        """
        加载提示词文件
        
        Args:
            file_path: 相对于 prompts_dir 的路径
            use_cache: 是否使用缓存
            
        Returns:
            提示词内容
        """
        full_path = self.prompts_dir / file_path
        cache_key = str(full_path.resolve())
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        if not full_path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {full_path}")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if use_cache:
            self._cache[cache_key] = content
        
        return content
    
    def load_template(self, file_path: str, **kwargs) -> str:
        """
        加载提示词模板并替换占位符
        
        Args:
            file_path: 文件路径
            **kwargs: 替换参数
            
        Returns:
            格式化后的提示词
        """
        content = self.load(file_path)
        return content.format(**kwargs)
    
    @classmethod
    def clear_cache(cls):
        """清空缓存"""
        cls._cache.clear()
    
    @classmethod
    def reload(cls, file_path: str, prompts_dir: Optional[Path] = None) -> str:
        """
        强制重新加载提示词（清除缓存）
        
        Args:
            file_path: 文件路径
            prompts_dir: 提示词目录
            
        Returns:
            重新加载的内容
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent
        full_path = prompts_dir / file_path
        cache_key = str(full_path.resolve())
        
        if cache_key in cls._cache:
            del cls._cache[cache_key]
        
        loader = PromptLoader(prompts_dir)
        return loader.load(file_path, use_cache=False)
