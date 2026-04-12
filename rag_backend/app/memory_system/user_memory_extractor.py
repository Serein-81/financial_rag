"""
用户记忆提取器 (User Memory Extractor)

从对话历史中自动提取用户的：
1. Facts (事实信息) - 用户陈述的客观事实
2. Preferences (偏好设置) - 用户的偏好和习惯
3. Corrections (纠正信息) - 用户纠正的AI错误

设计原则：
- 复用 EntityExtractor 的 LLM 调用模式
- 低温度参数保证提取稳定性
- 异步非阻塞执行
- 完整的错误处理和日志记录
"""

import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from app.agent_framework.llm.factory import LLMAdapterFactory
from app.core.config import settings


@dataclass
class ExtractedFact:
    """提取的事实"""
    content: str
    category: str
    confidence: float
    source: str


@dataclass
class ExtractedPreference:
    """提取的偏好"""
    content: str
    category: str
    confidence: float
    source: str


@dataclass
class ExtractedCorrection:
    """提取的纠正信息"""
    original: str
    corrected: str
    confidence: float
    source: str


@dataclass
class UserMemoryExtractionResult:
    """用户记忆提取结果"""
    facts: List[ExtractedFact]
    preferences: List[ExtractedPreference]
    corrections: List[ExtractedCorrection]
    extraction_time: datetime
    total_items: int
    
    def is_empty(self) -> bool:
        """检查是否为空"""
        return (
            len(self.facts) == 0 and 
            len(self.preferences) == 0 and 
            len(self.corrections) == 0
        )
    
    def summary(self) -> str:
        """生成摘要"""
        total_categories = 3
        return (
            f"提取完成：共 {total_categories} 个类别 - "
            f"{len(self.facts)} 个事实，"
            f"{len(self.preferences)} 个偏好，"
            f"{len(self.corrections)} 个纠正"
        )


class UserMemoryExtractor:
    """
    用户记忆提取器
    
    职责：
    1. 从对话历史中提取用户事实、偏好和纠正信息
    2. 格式化对话输入
    3. 解析LLM响应
    4. 错误处理和重试机制
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        初始化用户记忆提取器
        
        Args:
            confidence_threshold: 置信度阈值，低于此值的信息将被过滤
        """
        self.confidence_threshold = confidence_threshold
        
        # 初始化LLM适配器
        try:
            self.llm_adapter = LLMAdapterFactory.create_adapter(
                provider=settings.LLM_PROVIDER or "zhipu",
                api_key=settings.LLM_API_KEY,
                model_name=settings.LLM_MODEL_NAME or "glm-4-flash"
            )
        except Exception as e:
            print(f"⚠️ [用户记忆提取器] LLM适配器初始化失败: {e}")
            self.llm_adapter = None
        
        # 加载提取提示词
        self.extraction_prompt = self._load_extraction_prompt()
        
        print(f"🧠 [用户记忆提取器] 初始化完成 | 置信度阈值: {confidence_threshold}")
    
    def _load_extraction_prompt(self) -> str:
        """从文件加载提取提示词"""
        prompt_path = Path(__file__).parent.parent / "prompts" / "system" / "user_memory_extractor.md"
        
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    print(f"✅ [用户记忆提取器] 成功加载提示词: {prompt_path}")
                    return content
            except Exception as e:
                print(f"⚠️ [用户记忆提取器] 加载提示词失败: {e}")
        
        # 返回默认提示词
        return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """获取默认提示词（文件加载失败时使用）"""
        return """你是一个专业的用户信息提取专家。
        
请从对话历史中提取用户的：
1. 事实信息（Facts）- 用户陈述的客观事实
2. 偏好设置（Preferences）- 用户的偏好和习惯  
3. 纠正信息（Corrections）- 用户纠正的AI错误

请严格按照JSON格式输出：
{
  "facts": [{"content": "", "category": "", "confidence": 0.0-1.0, "source": ""}],
  "preferences": [{"content": "", "category": "", "confidence": 0.0-1.0, "source": ""}],
  "corrections": [{"original": "", "corrected": "", "confidence": 0.0-1.0, "source": ""}]
}

只提取明确表达的信息，confidence低于0.7的不提取。
"""
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """
        格式化对话历史
        
        Args:
            messages: 消息列表 [{"role": "user"|"assistant", "content": "..."}]
            
        Returns:
            格式化的对话字符串
        """
        if not messages:
            return "（无对话历史）"
        
        formatted = []
        for msg in messages:
            role = "用户" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "").strip()
            
            if content:
                # 限制每条消息的长度
                if len(content) > 500:
                    content = content[:500] + "..."
                formatted.append(f"{role}：{content}")
        
        return "\n".join(formatted)
    
    async def extract(self, messages: List[Dict[str, str]]) -> UserMemoryExtractionResult:
        """
        从对话历史中提取用户记忆
        
        Args:
            messages: 消息列表 [{"role": "user"|"assistant", "content": "..."}]
            
        Returns:
            UserMemoryExtractionResult: 包含提取的事实、偏好和纠正信息
        """
        if not messages:
            return UserMemoryExtractionResult(
                facts=[],
                preferences=[],
                corrections=[],
                extraction_time=datetime.now(),
                total_items=0
            )
        
        # 检查LLM适配器
        if not self.llm_adapter:
            print("⚠️ [用户记忆提取器] LLM适配器未初始化，跳过提取")
            return UserMemoryExtractionResult(
                facts=[],
                preferences=[],
                corrections=[],
                extraction_time=datetime.now(),
                total_items=0
            )
        
        try:
            # 1. 格式化对话
            formatted_conversation = self._format_conversation(messages)
            
            # 2. 构建提示词
            prompt = f"{self.extraction_prompt}\n\n## 对话历史\n\n{formatted_conversation}"
            
            # 3. 调用LLM
            print(f"🔍 [用户记忆提取器] 开始提取 | 消息数: {len(messages)}")
            
            response = await self.llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 低温度保证稳定性
                stream=False
            )
            
            # 4. 解析响应
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 5. 提取JSON
            extraction_result = self._parse_llm_response(response_text)
            
            # 6. 过滤低置信度
            extraction_result = self._filter_by_confidence(extraction_result)
            
            # 7. 记录日志
            print(f"✅ [用户记忆提取器] {extraction_result.summary()}")
            
            return extraction_result
        
        except Exception as e:
            print(f"❌ [用户记忆提取器] 提取失败: {e}")
            return UserMemoryExtractionResult(
                facts=[],
                preferences=[],
                corrections=[],
                extraction_time=datetime.now(),
                total_items=0
            )
    
    def _parse_llm_response(self, response_text: str) -> UserMemoryExtractionResult:
        """
        解析LLM响应
        
        Args:
            response_text: LLM返回的文本
            
        Returns:
            UserMemoryExtractionResult: 解析后的结果
        """
        try:
            # 尝试提取JSON
            json_match = re.search(
                r'\{[\s\S]*"facts"[\s\S]*\}',
                response_text,
                re.MULTILINE
            )
            
            if json_match:
                json_str = json_match.group(0)
                # 修复常见的JSON问题
                json_str = self._fix_json(json_str)
                data = json.loads(json_str)
            else:
                # 尝试解析整个响应
                data = json.loads(response_text)
            
            # 解析事实
            facts = [
                ExtractedFact(
                    content=item.get("content", ""),
                    category=item.get("category", "other"),
                    confidence=float(item.get("confidence", 0.0)),
                    source=item.get("source", "")
                )
                for item in data.get("facts", [])
                if item.get("content")
            ]
            
            # 解析偏好
            preferences = [
                ExtractedPreference(
                    content=item.get("content", ""),
                    category=item.get("category", "other"),
                    confidence=float(item.get("confidence", 0.0)),
                    source=item.get("source", "")
                )
                for item in data.get("preferences", [])
                if item.get("content")
            ]
            
            # 解析纠正
            corrections = [
                ExtractedCorrection(
                    original=item.get("original", ""),
                    corrected=item.get("corrected", ""),
                    confidence=float(item.get("confidence", 0.0)),
                    source=item.get("source", "")
                )
                for item in data.get("corrections", [])
                if item.get("corrected")
            ]
            
            return UserMemoryExtractionResult(
                facts=facts,
                preferences=preferences,
                corrections=corrections,
                extraction_time=datetime.now(),
                total_items=len(facts) + len(preferences) + len(corrections)
            )
        
        except json.JSONDecodeError as e:
            print(f"⚠️ [用户记忆提取器] JSON解析失败: {e}")
            print(f"   响应文本: {response_text[:200]}...")
            return UserMemoryExtractionResult(
                facts=[],
                preferences=[],
                corrections=[],
                extraction_time=datetime.now(),
                total_items=0
            )
    
    def _fix_json(self, json_str: str) -> str:
        """
        修复常见的JSON问题
        
        Args:
            json_str: 可能有问题JSON字符串
            
        Returns:
            修复后的JSON字符串
        """
        # 移除注释
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 移除尾随逗号
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        return json_str
    
    def _filter_by_confidence(
        self, 
        result: UserMemoryExtractionResult
    ) -> UserMemoryExtractionResult:
        """
        根据置信度过滤结果
        
        Args:
            result: 提取结果
            
        Returns:
            过滤后的结果
        """
        filtered_facts = [f for f in result.facts if f.confidence >= self.confidence_threshold]
        filtered_preferences = [p for p in result.preferences if p.confidence >= self.confidence_threshold]
        filtered_corrections = [c for c in result.corrections if c.confidence >= self.confidence_threshold]
        
        return UserMemoryExtractionResult(
            facts=filtered_facts,
            preferences=filtered_preferences,
            corrections=filtered_corrections,
            extraction_time=result.extraction_time,
            total_items=len(filtered_facts) + len(filtered_preferences) + len(filtered_corrections)
        )
    
    async def extract_facts_only(self, messages: List[Dict[str, str]]) -> List[ExtractedFact]:
        """
        仅提取事实信息（轻量级方法）
        
        Args:
            messages: 消息列表
            
        Returns:
            提取的事实列表
        """
        result = await self.extract(messages)
        return result.facts
    
    async def extract_preferences_only(self, messages: List[Dict[str, str]]) -> List[ExtractedPreference]:
        """
        仅提取偏好信息（轻量级方法）
        
        Args:
            messages: 消息列表
            
        Returns:
            提取的偏好列表
        """
        result = await self.extract(messages)
        return result.preferences
    
    async def extract_corrections_only(self, messages: List[Dict[str, str]]) -> List[ExtractedCorrection]:
        """
        仅提取纠正信息（轻量级方法）
        
        Args:
            messages: 消息列表
            
        Returns:
            提取的纠正列表
        """
        result = await self.extract(messages)
        return result.corrections
