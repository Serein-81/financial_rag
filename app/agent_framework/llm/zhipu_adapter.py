# app/agent_framework/llm/zhipu_adapter.py

"""
智谱 AI 适配器

封装智谱 AI 的调用逻辑
"""

from typing import AsyncGenerator, Optional
try:
    from zhipuai import ZhipuAI
    ZHIPU_AVAILABLE = True
except ImportError:
    ZHIPU_AVAILABLE = False
    ZhipuAI = None

from .base_adapter import BaseLLMAdapter


class ZhipuAdapter(BaseLLMAdapter):
    """
    智谱 AI 适配器
    
    封装智谱 AI 的 API 调用
    """
    
    def __init__(
        self, 
        api_key: str,
        model_name: str = "glm-4-flash",
        **kwargs
    ):
        """
        初始化智谱 AI 适配器
        
        Args:
            api_key: API 密钥
            model_name: 模型名称
            **kwargs: 其他配置
        """
        super().__init__(model_name, **kwargs)
        
        if not ZHIPU_AVAILABLE:
            raise ImportError("zhipuai 包未安装，请运行: pip install zhipuai")
        
        if not api_key:
            raise ValueError("智谱 AI API Key 不能为空")
        
        self.client = ZhipuAI(api_key=api_key)
        self.api_key = api_key
        
        print(f"✅ 智谱 AI 适配器初始化完成")
        print(f"   - 模型: {self.model_name}")
        print(f"   - API Key: {api_key[:8]}...{api_key[-4:]}")
    
    async def generate(
        self, 
        prompt: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        生成回答（非流式）
        
        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
            
        Returns:
            生成的文本
        """
        try:
            # 构建消息格式
            messages = [{"role": "user", "content": prompt}]
            
            # 准备请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": False
            }
            
            # 添加可选参数
            if max_tokens:
                request_params["max_tokens"] = max_tokens
            
            # 合并其他参数
            request_params.update(kwargs)
            
            print(f"🤖 [智谱AI] 调用模型: {self.model_name}")
            print(f"    提示词长度: {len(prompt)} 字符")
            print(f"    温度: {temperature}")
            
            # 调用 API
            response = self.client.chat.completions.create(**request_params)
            
            # 提取结果
            result = response.choices[0].message.content
            
            print(f"✅ [智谱AI] 生成完成，长度: {len(result)} 字符")
            
            return result
            
        except Exception as e:
            error_msg = f"智谱 AI 调用失败: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            raise Exception(error_msg)
    
    async def stream_generate(
        self, 
        prompt: str, 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回答
        
        Args:
            prompt: 输入提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
            
        Yields:
            逐步生成的文本片段
        """
        try:
            # 构建消息格式
            messages = [{"role": "user", "content": prompt}]
            
            # 准备请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }
            
            # 添加可选参数
            if max_tokens:
                request_params["max_tokens"] = max_tokens
            
            # 合并其他参数
            request_params.update(kwargs)
            
            print(f"🌊 [智谱AI] 流式调用: {self.model_name}")
            print(f"    提示词长度: {len(prompt)} 字符")
            
            # 调用流式 API
            response = self.client.chat.completions.create(**request_params)
            
            total_chars = 0
            
            # 逐个返回文本片段
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_chars += len(content)
                    yield content
            
            print(f"✅ [智谱AI] 流式生成完成，总长度: {total_chars} 字符")
            
        except Exception as e:
            error_msg = f"智谱 AI 流式调用失败: {str(e)}"
            print(f"❌ [智谱AI] {error_msg}")
            yield f"[错误: {error_msg}]"