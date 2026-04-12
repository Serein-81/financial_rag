"""
企业信息查询工具（云端 MCP 模式）

基于云端 MCP 协议实现的企业工商信息查询
通过 HTTP 调用本地后端 API 访问数据库

设计原则：
- 云端 MCP 工具：不直接访问数据库，通过 HTTP API 调用本地服务
- 本地 LangChain 工具：直接访问 PostgreSQL 数据库（高隐私、高权限）
- 租户隔离：通过 API 传递租户 ID，自动应用权限控制
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)


class EnterpriseSearchTool(ToolBase):
    """
    企业信息搜索工具（云端 MCP）
    
    通过调用本地后端 API 搜索企业工商信息
    不直接访问数据库，通过 HTTP API 实现租户隔离
    """
    
    def __init__(self):
        super().__init__(
            name="search_enterprise_info",
            description="根据企业名称或信用代码搜索企业工商信息。支持模糊搜索，返回企业摘要列表。",
            timeout=30
        )
    
    async def execute(
        self,
        query: str,
        search_type: str = "name",
        limit: int = 10,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        搜索企业信息
        
        Args:
            query: 搜索关键词（企业名称或信用代码）
            search_type: 搜索类型
                - name: 按企业名称搜索（默认）
                - credit_code: 按信用代码搜索
                - all: 同时搜索名称和信用代码
            limit: 返回数量限制，默认10条，最大50条
            tenant_id: 租户ID，用于权限隔离
        
        Returns:
            企业摘要信息列表
        
        Example:
            >>> tool = EnterpriseSearchTool()
            >>> result = await tool.execute(
            ...     query="科技",
            ...     search_type="name",
            ...     limit=5,
            ...     tenant_id="tenant_123"
            ... )
        """
        try:
            local_backend_url = self._get_local_backend_url()
            
            api_url = f"{local_backend_url}/api/v1/enterprise/search"
            
            payload = {
                "query": query,
                "search_type": search_type,
                "limit": limit
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Tenant-ID": tenant_id
            }
            
            response = await self._http_post(api_url, payload, headers)
            
            if response.get("success"):
                enterprises = response.get("data", [])
                return {
                    "success": True,
                    "count": len(enterprises),
                    "data": enterprises,
                    "message": f"找到 {len(enterprises)} 条企业信息"
                }
            else:
                return {
                    "success": False,
                    "error": response.get("detail", "搜索失败")
                }
                
        except Exception as e:
            logger.error(f"搜索企业信息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"搜索失败: {str(e)}"
            }
    
    def _get_local_backend_url(self) -> str:
        """获取本地后端 URL"""
        import os
        return os.getenv("LOCAL_BACKEND_URL", "http://localhost:8000")
    
    async def _http_post(self, url: str, payload: Dict, headers: Dict) -> Dict:
        """发送 HTTP POST 请求"""
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


class EnterpriseDetailTool(ToolBase):
    """
    企业详细信息查询工具（云端 MCP）
    
    通过调用本地后端 API 获取企业完整工商信息
    不直接访问数据库，通过 HTTP API 实现租户隔离
    """
    
    def __init__(self):
        super().__init__(
            name="get_enterprise_detail",
            description="根据企业ID获取完整的工商信息，包括基本信息、联系方式、经营范围等。",
            timeout=30
        )
    
    async def execute(
        self,
        enterprise_id: str,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        获取企业详细信息
        
        Args:
            enterprise_id: 企业ID（UUID格式）
            tenant_id: 租户ID，用于权限隔离
        
        Returns:
            企业详细信息
        
        Example:
            >>> tool = EnterpriseDetailTool()
            >>> result = await tool.execute(
            ...     enterprise_id="550e8400-e29b-41d4-a716-446655440000",
            ...     tenant_id="tenant_123"
            ... )
        """
        try:
            local_backend_url = self._get_local_backend_url()
            
            api_url = f"{local_backend_url}/api/v1/enterprise/{enterprise_id}"
            
            headers = {
                "Content-Type": "application/json",
                "X-Tenant-ID": tenant_id
            }
            
            response = await self._http_get(api_url, headers)
            
            if response.get("success", True):
                return {
                    "success": True,
                    "data": response,
                    "message": "获取企业详情成功"
                }
            else:
                return {
                    "success": False,
                    "error": response.get("detail", "获取详情失败")
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "error": "企业信息不存在"
                }
            logger.error(f"获取企业详情失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取详情失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"获取企业详情失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取详情失败: {str(e)}"
            }
    
    async def execute_by_credit_code(
        self,
        credit_code: str,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        根据信用代码获取企业详细信息
        
        Args:
            credit_code: 统一社会信用代码（18位）
            tenant_id: 租户ID，用于权限隔离
        
        Returns:
            企业详细信息
        """
        try:
            local_backend_url = self._get_local_backend_url()
            
            api_url = f"{local_backend_url}/api/v1/enterprise/credit_code/{credit_code}"
            
            headers = {
                "Content-Type": "application/json",
                "X-Tenant-ID": tenant_id
            }
            
            response = await self._http_get(api_url, headers)
            
            if response.get("success", True):
                return {
                    "success": True,
                    "data": response,
                    "message": "获取企业信息成功"
                }
            else:
                return {
                    "success": False,
                    "error": response.get("detail", "获取失败")
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "error": "企业信息不存在"
                }
            logger.error(f"根据信用代码获取企业信息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"根据信用代码获取企业信息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取失败: {str(e)}"
            }
    
    def _get_local_backend_url(self) -> str:
        """获取本地后端 URL"""
        import os
        return os.getenv("LOCAL_BACKEND_URL", "http://localhost:8000")
    
    async def _http_get(self, url: str, headers: Dict) -> Dict:
        """发送 HTTP GET 请求"""
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()


class EnterpriseRiskAssessmentTool(ToolBase):
    """
    企业风险评估工具（云端 MCP）
    
    通过调用本地后端 API 获取或创建企业风险评估
    不直接访问数据库，通过 HTTP API 实现租户隔离
    """
    
    def __init__(self):
        super().__init__(
            name="assess_enterprise_risk",
            description="获取或创建企业风险评估报告，包括风险评分、风险等级、法律风险、财务风险等多维度评估。",
            timeout=30
        )
    
    async def execute(
        self,
        enterprise_id: str,
        latest_only: bool = True,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        获取企业风险评估
        
        Args:
            enterprise_id: 企业ID（UUID格式）
            latest_only: 是否仅返回最新评估，默认True
            tenant_id: 租户ID，用于权限隔离
        
        Returns:
            企业风险评估信息
        
        Example:
            >>> tool = EnterpriseRiskAssessmentTool()
            >>> result = await tool.execute(
            ...     enterprise_id="550e8400-e29b-41d4-a716-446655440000",
            ...     latest_only=True,
            ...     tenant_id="tenant_123"
            ... )
        """
        try:
            local_backend_url = self._get_local_backend_url()
            
            api_url = f"{local_backend_url}/api/v1/enterprise/{enterprise_id}/risk-assessment"
            
            headers = {
                "Content-Type": "application/json",
                "X-Tenant-ID": tenant_id
            }
            
            params = {"latest_only": latest_only}
            
            response = await self._http_get(api_url, headers, params)
            
            if response.get("risk_level"):
                return {
                    "success": True,
                    "data": response,
                    "message": "获取风险评估成功"
                }
            else:
                return {
                    "success": True,
                    "data": None,
                    "message": "暂无风险评估记录"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "error": "企业信息不存在"
                }
            logger.error(f"获取风险评估失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取风险评估失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"获取风险评估失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"获取风险评估失败: {str(e)}"
            }
    
    async def create_assessment(
        self,
        enterprise_id: str,
        risk_score: float,
        risk_level: str,
        tenant_id: str = "default",
        legal_risk: Optional[float] = None,
        financial_risk: Optional[float] = None,
        operational_risk: Optional[float] = None,
        compliance_risk: Optional[float] = None,
        risk_factors: Optional[str] = None,
        recommendations: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建企业风险评估
        
        Args:
            enterprise_id: 企业ID（UUID格式）
            risk_score: 综合风险评分（0-100）
            risk_level: 风险等级（低、中、高）
            tenant_id: 租户ID，用于权限隔离
            legal_risk: 法律风险评分
            financial_risk: 财务风险评分
            operational_risk: 经营风险评分
            compliance_risk: 合规风险评分
            risk_factors: 风险因素（JSON格式）
            recommendations: 建议措施（JSON格式）
        
        Returns:
            创建结果
        """
        try:
            local_backend_url = self._get_local_backend_url()
            
            api_url = f"{local_backend_url}/api/v1/enterprise/{enterprise_id}/risk-assessment"
            
            headers = {
                "Content-Type": "application/json",
                "X-Tenant-ID": tenant_id
            }
            
            payload = {
                "risk_score": risk_score,
                "risk_level": risk_level
            }
            
            if legal_risk is not None:
                payload["legal_risk"] = legal_risk
            if financial_risk is not None:
                payload["financial_risk"] = financial_risk
            if operational_risk is not None:
                payload["operational_risk"] = operational_risk
            if compliance_risk is not None:
                payload["compliance_risk"] = compliance_risk
            if risk_factors:
                payload["risk_factors"] = risk_factors
            if recommendations:
                payload["recommendations"] = recommendations
            
            response = await self._http_post(api_url, payload, headers)
            
            return response
                
        except Exception as e:
            logger.error(f"创建风险评估失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"创建风险评估失败: {str(e)}"
            }
    
    def _get_local_backend_url(self) -> str:
        """获取本地后端 URL"""
        import os
        return os.getenv("LOCAL_BACKEND_URL", "http://localhost:8000")
    
    async def _http_get(self, url: str, headers: Dict, params: Dict = None) -> Dict:
        """发送 HTTP GET 请求"""
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    
    async def _http_post(self, url: str, payload: Dict, headers: Dict) -> Dict:
        """发送 HTTP POST 请求"""
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


def register_enterprise_tools():
    """注册所有企业信息工具"""
    registry.register(EnterpriseSearchTool())
    registry.register(EnterpriseDetailTool())
    registry.register(EnterpriseRiskAssessmentTool())


enterprise_tools = [
    EnterpriseSearchTool(),
    EnterpriseDetailTool(),
    EnterpriseRiskAssessmentTool()
]
