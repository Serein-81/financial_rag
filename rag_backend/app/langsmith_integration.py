"""
LangSmith 集成模块

为原生 httpx LLM 适配器添加 LangSmith 追踪

方案：使用 @traceable 装饰器
- 优点：无需重构现有代码
- 缺点：需要手动在关键函数上添加装饰器
"""

import os
import logging
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)


def setup_langsmith_config():
    """
    配置 LangSmith 环境变量
    
    在项目启动时调用一次即可
    """
    # 从 .env 文件读取 LangSmith 配置
    # LANGSMITH_TRACING=true
    # LANGSMITH_ENDPOINT=https://api.smith.langchain.com
    # LANGSMITH_API_KEY=REDACTED_LANGSMITH_KEY
    # LANGSMITH_PROJECT=financial_rag
    
    # 如果 .env 已配置，会自动读取（通过 python-dotenv）
    # 此函数确保兼容旧版本配置或手动设置
    required_vars = {
        "LANGSMITH_API_KEY": os.getenv("LANGSMITH_API_KEY", ""),
        "LANGSMITH_PROJECT": os.getenv("LANGSMITH_PROJECT", "financial_rag"),
        "LANGSMITH_ENDPOINT": os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        "LANGSMITH_TRACING": os.getenv("LANGSMITH_TRACING", "false")
    }
    
    for key, value in required_vars.items():
        if value and not os.getenv(key):
            os.environ[key] = value
            logger.info(f"[LangSmith] 设置环境变量: {key}={value}")


def get_langsmith_config() -> Dict[str, Any]:
    """
    获取 LangSmith 配置信息
    
    Returns:
        配置字典
    """
    return {
        "api_key": os.getenv("LANGSMITH_API_KEY"),
        "project": os.getenv("LANGSMITH_PROJECT", "financial_rag"),
        "endpoint": os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        "tracing": os.getenv("LANGSMITH_TRACING", "false").lower() == "true",
        "enabled": bool(os.getenv("LANGSMITH_API_KEY")) and os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    }


class LangSmithTracer:
    """
    LangSmith 追踪器
    
    用于手动追踪 LLM 调用
    """
    
    def __init__(self, project_name: Optional[str] = None):
        self.project_name = project_name or os.getenv("LANGSMITH_PROJECT", "financial_rag")
        self.client = None
        self._setup_client()
    
    def _setup_client(self):
        """初始化 LangSmith 客户端"""
        # 检查是否启用追踪
        if os.getenv("LANGSMITH_TRACING", "false").lower() != "true":
            logger.info("[LangSmith] LANGSMITH_TRACING 未启用，追踪已禁用")
            return
        
        api_key = os.getenv("LANGSMITH_API_KEY")
        if not api_key:
            logger.warning("[LangSmith] 未配置 LANGSMITH_API_KEY，追踪已禁用")
            return
        
        # 获取配置
        endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        self.project_name = os.getenv("LANGSMITH_PROJECT", "financial_rag")
        
        try:
            from langsmith import Client
            self.client = Client(
                api_key=api_key,
                api_url=endpoint
            )
            logger.info(f"[LangSmith] 客户端初始化成功 | 项目: {self.project_name} | 端点: {endpoint}")
        except ImportError:
            logger.warning("[LangSmith] langsmith 包未安装，请运行: pip install langsmith")
        except Exception as e:
            logger.error(f"[LangSmith] 客户端初始化失败: {e}")
    
    def trace_llm_call(
        self,
        model_name: str,
        prompt: str,
        response: str,
        token_usage: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        追踪 LLM 调用
        
        Args:
            model_name: 模型名称
            prompt: 输入提示
            response: 输出响应
            token_usage: Token 使用量 {"prompt": 100, "completion": 50, "total": 150}
            metadata: 额外元数据
        """
        if not self.client:
            return
        
        try:
            run = self.client.create_run(
                name=f"llm_call_{model_name}",
                run_type="llm",
                project_name=self.project_name,
                inputs={
                    "prompt": prompt,
                    "model": model_name
                },
                outputs={
                    "response": response
                },
                tags=["llm", model_name]
            )
            
            if token_usage:
                self.client.create_feedback(
                    run_id=run.id,
                    key="token_usage",
                    score=token_usage.get("total", 0),
                    metadata={
                        "prompt_tokens": token_usage.get("prompt", 0),
                        "completion_tokens": token_usage.get("completion", 0),
                        "total_tokens": token_usage.get("total", 0)
                    }
                )
            
            if metadata:
                for key, value in metadata.items():
                    self.client.create_feedback(
                        run_id=run.id,
                        key=f"metadata_{key}",
                        score=1.0,
                        comment=str(value)
                    )
            
            logger.debug(f"[LangSmith] 追踪 LLM 调用: {model_name} -> {run.id}")
            
        except Exception as e:
            logger.error(f"[LangSmith] 追踪失败: {e}")
    
    def trace_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        error: Optional[str] = None
    ):
        """
        追踪工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 调用参数
            result: 返回结果
            error: 错误信息
        """
        if not self.client:
            return
        
        try:
            run = self.client.create_run(
                name=f"tool_call_{tool_name}",
                run_type="tool",
                project_name=self.project_name,
                inputs={"arguments": arguments},
                outputs={"result": str(result)[:1000]},  # 截断避免过大
                error=error,
                tags=["tool", tool_name]
            )
            
            logger.debug(f"[LangSmith] 追踪工具调用: {tool_name} -> {run.id}")
            
        except Exception as e:
            logger.error(f"[LangSmith] 追踪失败: {e}")
    
    def flush(self):
        """
        刷新追踪记录（确保所有追踪已发送）
        
        用于程序结束时调用，确保所有追踪记录已发送完成
        
        使用场景：
        1. CLI 工具结束时
        2. 定时任务结束时
        3. 测试脚本结束时
        
        Web 服务（FastAPI）不需要调用此方法，因为服务长期运行
        """
        if not self.client:
            logger.debug("[LangSmith] flush() - 客户端未初始化，跳过")
            return
        
        try:
            if hasattr(self.client, 'flush'):
                logger.debug("[LangSmith] 调用 client.flush()...")
                self.client.flush()
                logger.info("[LangSmith] 追踪刷新完成")
            else:
                logger.debug("[LangSmith] flush() - 客户端不支持 flush()")
        except Exception as e:
            logger.warning(f"[LangSmith] flush() 失败: {e}")
    
    def wait_for_sync(self, timeout: float = 10.0):
        """
        等待追踪同步完成
        
        Args:
            timeout: 超时时间（秒）
        
        用于需要立即看到追踪结果的场景（如测试脚本）
        Web 服务不建议使用，会阻塞请求
        
        注意：
        - 如果使用 langsmith.run_helpers.wait_for_all_tracers 效果更好
        - 这个方法是简化版本，额外等待一段时间
        """
        if not self.client:
            return
        
        import time
        logger.debug(f"[LangSmith] 等待追踪同步，最多 {timeout} 秒...")
        time.sleep(timeout)
        logger.info("[LangSmith] 等待完成")


# 全局追踪器实例
_tracer: Optional[LangSmithTracer] = None


def get_tracer() -> LangSmithTracer:
    """获取全局追踪器"""
    global _tracer
    if _tracer is None:
        _tracer = LangSmithTracer()
    return _tracer


# ===== 装饰器方式 =====

def traceable(func):
    """
    可追踪装饰器
    
    用法:
    @traceable
    async def my_llm_call(prompt):
        # LLM 调用代码
        return response
    
    或者手动追踪:
    tracer = get_tracer()
    tracer.trace_llm_call(model_name="MiniMax", prompt=..., response=...)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        tracer = get_tracer()
        
        if not tracer.client:
            # 未启用追踪，直接执行
            return await func(*args, **kwargs)
        
        import time
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000
            
            # 自动追踪（需要函数有特定参数）
            model_name = kwargs.get("model_name", args[0] if args else "unknown")
            prompt = kwargs.get("prompt", args[1] if len(args) > 1 else "")
            
            tracer.trace_llm_call(
                model_name=model_name,
                prompt=str(prompt)[:1000],
                response=str(result)[:1000],
                metadata={"duration_ms": duration}
            )
            
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            
            if tracer.client:
                try:
                    run = tracer.client.create_run(
                        name=func.__name__,
                        run_type="error",
                        project_name=tracer.project_name,
                        inputs={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
                        error=str(e),
                        tags=["error", func.__name__]
                    )
                except:
                    pass
            
            raise
    
    return wrapper


# ===== 使用示例 =====

async def example_usage():
    """
    使用示例
    """
    
    # 1. 初始化配置
    setup_langsmith_config()
    
    # 2. 获取追踪器
    tracer = get_tracer()
    
    # 3. 在 MiniMax 适配器中使用
    if tracer.client:
        tracer.trace_llm_call(
            model_name="MiniMax-Text-01",
            prompt="分析公司财务状况",
            response="根据财务数据分析...",
            token_usage={
                "prompt": 234,
                "completion": 89,
                "total": 323
            },
            metadata={
                "temperature": 0.7,
                "session_id": "user_123"
            }
        )
    
    # 4. 在工具调用中使用
    tracer.trace_tool_call(
        tool_name="search_knowledge_base",
        arguments={"query": "税务法规", "top_k": 5},
        result={"documents": [...]},
        error=None
    )


# ===== 环境变量配置 =====

"""
.env 文件配置 (LangSmith):

# 启用 LangSmith 追踪
LANGSMITH_TRACING=true

# LangSmith API 端点
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# LangSmith API Key
LANGSMITH_API_KEY=REDACTED_LANGSMITH_KEY

# LangSmith 项目名称
LANGSMITH_PROJECT=financial_rag

提示：
1. 确保已安装 langsmith: pip install langsmith
2. 环境变量可以通过 .env 文件自动加载（使用 python-dotenv）
3. 或者手动设置：export LANGSMITH_TRACING=true
"""

if __name__ == "__main__":
    import asyncio
    
    # 配置
    setup_langsmith_config()
    
    # 检查配置
    config = get_langsmith_config()
    print(f"[LangSmith] 配置状态:")
    print(f"  启用: {config['enabled']}")
    print(f"  项目: {config['project']}")
    print(f"  API Key: {'***' + config['api_key'][-4:] if config['api_key'] else '未设置'}")
    
    # 测试追踪
    asyncio.run(example_usage())
