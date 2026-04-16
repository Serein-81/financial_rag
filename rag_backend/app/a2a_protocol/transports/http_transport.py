"""
HTTP Agent Transport

HTTP 传输实现
用于跨服务的 Agent 通信
支持：
1. 同步请求-响应
2. 异步通知
3. SSE 流式接收
4. 多租户安全穿透
"""

import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator, List
from datetime import datetime

from .base import TransportConfig, AgentTransport, TransportError

logger = logging.getLogger(__name__)


class HttpAgentTransport(AgentTransport):
    """
    HTTP 传输
    
    特点：
    1. RESTful API - 标准 HTTP 接口
    2. JSON 序列化 - 跨语言支持
    3. SSE 流式 - 实时事件推送
    4. 多租户穿透 - JWT/Bearer Token
    
    适用场景：
    - 跨服务/跨节点通信
    - 微服务架构
    - 云原生部署
    """
    
    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._subscriptions: Dict[str, Any] = {}
        self._retry_times = config.retry_times
        self._retry_delay = config.retry_delay
    
    async def connect(self) -> None:
        """建立 HTTP 连接池"""
        if self._connected:
            return
        
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                limits=httpx.Limits(
                    max_connections=self.config.max_connections,
                    max_keepalive_connections=20
                ),
                verify=self.config.ssl_verify
            )
        
        self._connected = True
        logger.info(f"🔗 HTTP Transport 连接成功: {self.config.url}")
    
    async def disconnect(self) -> None:
        """断开 HTTP 连接"""
        if not self._connected:
            return
        
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self._connected = False
        logger.info("🔌 HTTP Transport 连接断开")
    
    def _get_headers(self, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """
        获取请求头
        
        自动添加租户信息用于安全穿透
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self.config.headers
        }
        
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        
        return headers
    
    async def send_message(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息（同步请求-响应模式）
        
        RESTful: POST /a2a/v1/tasks/send
        """
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/tasks/send"
        
        payload = {
            "message": message.get("content", message),
            "sessionId": message.get("session_id"),
            "acceptedOutputModes": message.get("accepted_output_modes", ["text"])
        }
        
        headers = self._get_headers(tenant_id)
        
        for attempt in range(self._retry_times):
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                logger.info(f"✅ HTTP 消息发送成功: {to_agent}")
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    logger.warning(f"⚠️ 服务器错误，重试 {attempt + 1}/{self._retry_times}: {e}")
                    if attempt < self._retry_times - 1:
                        await asyncio.sleep(self._retry_delay)
                        continue
                raise TransportError(
                    f"HTTP {e.response.status_code}: {e.response.text}",
                    code=e.response.status_code
                )
                
            except httpx.RequestError as e:
                logger.warning(f"⚠️ 请求错误，重试 {attempt + 1}/{self._retry_times}: {e}")
                if attempt < self._retry_times - 1:
                    await asyncio.sleep(self._retry_delay)
                    continue
                raise TransportError(f"请求失败: {str(e)}", code=503)
        
        raise TransportError("重试次数耗尽", code=503)
    
    async def send_notification(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> None:
        """
        发送通知（单向消息）
        
        RESTful: POST /a2a/v1/notifications
        """
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/notifications"
        
        payload = {
            "to_agent": to_agent,
            "content": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        headers = self._get_headers(tenant_id)
        
        try:
            response = await self._client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            logger.debug(f"✅ HTTP 通知发送成功: {to_agent}")
            
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP 通知发送失败: {e}")
            raise TransportError(f"通知发送失败: {str(e)}", code=500)
    
    async def subscribe(
        self,
        agent: str,
        event_types: List[str],
        callback,
        tenant_id: Optional[str] = None
    ) -> str:
        """
        订阅事件
        
        RESTful: POST /a2a/v1/subscriptions
        """
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/subscriptions"
        
        payload = {
            "agent": agent,
            "event_types": event_types
        }
        
        headers = self._get_headers(tenant_id)
        
        try:
            response = await self._client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            subscription_id = data.get("subscription_id")
            self._subscriptions[subscription_id] = callback
            
            logger.info(f"📥 HTTP 订阅成功: {subscription_id}")
            return subscription_id
            
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP 订阅失败: {e}")
            raise TransportError(f"订阅失败: {str(e)}", code=500)
    
    async def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        if subscription_id not in self._subscriptions:
            return
        
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/subscriptions/{subscription_id}"
        
        try:
            response = await self._client.delete(url)
            response.raise_for_status()
            
            del self._subscriptions[subscription_id]
            logger.info(f"📤 HTTP 取消订阅: {subscription_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP 取消订阅失败: {e}")
    
    async def stream_events(
        self,
        task_id: str,
        tenant_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式接收事件（SSE 模式）
        
        RESTful: GET /a2a/v1/tasks/{task_id}/subscribe
        """
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/tasks/{task_id}/subscribe"
        headers = self._get_headers(tenant_id)
        headers["Accept"] = "text/event-stream"
        
        try:
            async with self._client.stream("GET", url, headers=headers) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        data = line[6:]
                        
                        if data == "[DONE]":
                            break
                        
                        try:
                            import json
                            event_data = json.loads(data)
                            yield event_data
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ SSE 数据解析失败: {data}")
                            
                    elif line.startswith("event: "):
                        event_type = line[6:]
                        logger.debug(f"SSE 事件类型: {event_type}")
                        
        except httpx.HTTPError as e:
            logger.error(f"❌ SSE 流失败: {e}")
            raise TransportError(f"SSE 流失败: {str(e)}", code=500)
    
    async def get_task_status(self, task_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取任务状态
        
        RESTful: GET /a2a/v1/tasks/{task_id}
        """
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/tasks/{task_id}"
        headers = self._get_headers(tenant_id)
        
        try:
            response = await self._client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"❌ 获取任务状态失败: {e}")
            raise TransportError(f"获取任务状态失败: {str(e)}", code=500)
    
    async def cancel_task(self, task_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        取消任务
        
        RESTful: POST /a2a/v1/tasks/{task_id}/cancel
        """
        if not self._connected:
            await self.connect()
        
        url = f"{self.config.url}/a2a/v1/tasks/{task_id}/cancel"
        headers = self._get_headers(tenant_id)
        
        try:
            response = await self._client.post(url, headers=headers)
            response.raise_for_status()
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"❌ 取消任务失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not self._connected or not self._client:
            return False
        
        try:
            url = f"{self.config.url}/health"
            response = await self._client.get(url, timeout=5.0)
            return response.status_code == 200
        except (ValueError, KeyError):
            return False
        except (OSError, IOError):
            return False
        except TimeoutError:
            return False
        except Exception:
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取传输统计"""
        return {
            "type": "http",
            "connected": self._connected,
            "url": self.config.url,
            "subscriptions": len(self._subscriptions),
            "timeout": self.config.timeout,
        }
