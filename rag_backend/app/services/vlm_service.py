"""
VLM (Vision Language Model) 服务

用于图片内容识别和理解
支持硅基流动平台的Qwen2-VL等视觉大模型
"""

import base64
import logging
from typing import Optional, Dict, Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class VLMService:
    """
    视觉大模型服务
    
    职责：
    1. 调用多模态模型识别图片内容
    2. 支持图片OCR和内容理解
    3. 生成图片描述文本
    """
    
    _instance = None
    _client = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        
        self.api_key = settings.SILICONFLOW_API_KEY
        self.base_url = "https://api.siliconflow.cn/v1"
        
        self.default_model = "Qwen/Qwen2-VL-72B-Instruct"
        self.fallback_model = "Qwen/Qwen2-VL-7B-Instruct"
        
        self._enabled = bool(self.api_key)
        
        if self._enabled:
            logger.info("[VLM服务] 视觉大模型服务初始化完成")
            logger.info(f"[VLM服务] 默认模型: {self.default_model}")
        else:
            logger.warning("[VLM服务] 未配置SILICONFLOW_API_KEY，图片OCR功能不可用")
    
    @property
    def is_enabled(self) -> bool:
        """检查VLM服务是否启用"""
        return self._enabled
    
    async def describe_image(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        使用VLM描述图片内容
        
        Args:
            image_bytes: 图片字节数据
            prompt: 提示词（可选）
            model: 使用的模型（可选）
        
        Returns:
            str: 图片内容描述
        """
        if not self._enabled:
            logger.warning("[VLM服务] 服务未启用，返回占位符")
            return "[图片内容，需要OCR识别]"
        
        model = model or self.default_model
        
        default_prompt = (
            "作为专业的文档分析助手，请详细描述这张图片的内容。\n"
            "请提取所有可见的文字、数据、图表信息。\n"
            "如果这是截图或流程图，请描述其结构和步骤。\n"
            "如果包含表格，请以文本形式还原表格内容。\n"
            "请用中文回答，保持专业和准确。"
        )
        
        prompt = prompt or default_prompt
        
        try:
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 2048,
                "temperature": 0.3
            }
            
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
            
            description = result["choices"][0]["message"]["content"]
            logger.info(f"[VLM服务] 图片描述成功，长度: {len(description)} 字符")
            
            return description
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[VLM服务] HTTP错误: {e.response.status_code} - {e.response.text}")
            return f"[图片OCR失败: HTTP {e.response.status_code}]"
        except httpx.RequestError as e:
            logger.error(f"[VLM服务] 请求错误: {str(e)}")
            return "[图片OCR失败: 网络错误]"
        except Exception as e:
            logger.error(f"[VLM服务] 描述失败: {str(e)}")
            return "[图片OCR失败]"
    
    async def extract_text_from_image(
        self,
        image_bytes: bytes,
        language: str = "auto"
    ) -> str:
        """
        从图片中提取文字（OCR）
        
        Args:
            image_bytes: 图片字节数据
            language: 语言设置 (auto, chinese, english)
        
        Returns:
            str: 提取的文字内容
        """
        if language == "chinese":
            prompt = "请提取图片中所有的中文文字，保持原格式。"
        elif language == "english":
            prompt = "Please extract all English text from this image, keeping the original format."
        else:
            prompt = "请提取图片中所有可见的文字内容，包括中英文，保持原有格式和结构。"
        
        return await self.describe_image(image_bytes, prompt)
    
    async def analyze_chart(
        self,
        image_bytes: bytes,
        role: str = "财务分析师"
    ) -> str:
        """
        分析图表内容
        
        Args:
            image_bytes: 图表图片字节数据
            role: 分析角色
        
        Returns:
            str: 图表分析结果
        """
        prompt = (
            f"作为专业的{role}，请详细分析这张图表。\n"
            "请提取：\n"
            "1. 图表类型（折线图、柱状图、饼图等）\n"
            "2. 所有数据点和数值\n"
            "3. 趋势和模式\n"
            "4. 关键结论\n"
            "5. 任何异常或特殊情况\n"
            "请用结构化方式呈现分析结果。"
        )
        
        return await self.describe_image(image_bytes, prompt)
    
    async def describe_screenshot(
        self,
        image_bytes: bytes
    ) -> str:
        """
        描述截图内容
        
        Args:
            image_bytes: 截图字节数据
        
        Returns:
            str: 截图内容描述
        """
        prompt = (
            "这是一张截图或界面图片。\n"
            "请详细描述：\n"
            "1. 界面类型（网页、软件界面、文档等）\n"
            "2. 主要内容和布局\n"
            "3. 所有可见的文字信息\n"
            "4. 任何操作步骤或流程\n"
            "5. 关键元素和交互\n"
            "请尽可能详细地描述所有可见内容。"
        )
        
        return await self.describe_image(image_bytes, prompt)
    
    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


vlm_service = VLMService()
