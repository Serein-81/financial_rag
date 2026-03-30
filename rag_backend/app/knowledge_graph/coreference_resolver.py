"""指代消解器 - 将代词替换为具体实体"""
import logging
from typing import Optional
from app.services.llm_service import llm_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class CoreferenceResolver:
    """指代消解器 - 处理代词指代问题"""
    
    async def resolve(self, text: str) -> str:
        """
        将文本中的代词替换为具体指代的实体
        
        Args:
            text: 原始文本
            
        Returns:
            消解后的文本
        """
        if not getattr(settings, 'ENABLE_COREFERENCE_RESOLUTION', True):
            logger.info("指代消解功能未开启")
            return text
        
        # 检查是否包含常见代词
        pronouns = ['它', '他', '她', '这个', '那个', '其', '该', '此']
        if not any(p in text for p in pronouns):
            logger.debug("文本中无代词，跳过指代消解")
            return text
        
        prompt = f"""将以下文本中的代词替换为具体指代的实体。

原文：{text}

要求：
1. 识别所有代词（它、他、她、这个、那个、其、该、此等）
2. 根据上下文推断代词指代的具体实体
3. 将代词替换为实体名称
4. 保持句子的流畅性和语义不变
5. 只返回替换后的文本，不要其他说明

示例1：
原文：张三买了手机。它很贵。
返回：张三买了手机。手机很贵。

示例2：
原文：苹果公司发布了新产品。它的销量很好。
返回：苹果公司发布了新产品。新产品的销量很好。

示例3：
原文：李四在阿里巴巴工作。他是工程师。
返回：李四在阿里巴巴工作。李四是工程师。

现在处理：
"""
        
        try:
            logger.info(f"开始指代消解，原文长度: {len(text)}")
            
            response = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[]
            )
            
            resolved_text = response.strip()
            
            # 简单验证：消解后的文本不应该太短或太长
            if len(resolved_text) < len(text) * 0.5 or len(resolved_text) > len(text) * 2:
                logger.warning(f"消解结果异常，使用原文。原文长度: {len(text)}, 消解后: {len(resolved_text)}")
                return text
            
            logger.info(f"指代消解完成，消解后长度: {len(resolved_text)}")
            logger.debug(f"原文: {text}")
            logger.debug(f"消解后: {resolved_text}")
            
            return resolved_text
            
        except Exception as e:
            logger.error(f"指代消解失败: {e}", exc_info=True)
            return text  # 失败时返回原文


# 全局实例
coreference_resolver = CoreferenceResolver()
