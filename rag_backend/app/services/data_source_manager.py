"""
数据源连接管理器
支持多种数据源的连接和查询
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from abc import ABC, abstractmethod
import json
import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from minio import Minio, ResponseError

from app.core.exceptions import (
    ExternalAPIException,
    DatabaseException,
    CacheException,
    ServiceException
)

logger = logging.getLogger(__name__)


class DataSourceType(str, Enum):
    """数据源类型"""
    REST_API = "rest_api"
    DATABASE = "database"
    FILE = "file"
    WEBHOOK = "webhook"
    EXCEL = "excel"
    CSV = "csv"
    MINIO = "minio"


class DataSourceConfig:
    """数据源配置"""

    def __init__(
        self,
        source_type: DataSourceType,
        name: str,
        config: Dict[str, Any],
        enabled: bool = True
    ):
        self.source_type = source_type
        self.name = name
        self.config = config
        self.enabled = enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "name": self.name,
            "config": self.config,
            "enabled": self.enabled
        }


class BaseDataConnector(ABC):
    """数据连接器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def query(self, query_str: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """执行查询"""
        pass

    @abstractmethod
    async def fetch_data(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """获取数据"""
        pass


class RESTAPIDataConnector(BaseDataConnector):
    """REST API 数据连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "")
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30)

    async def connect(self) -> bool:
        """建立连接"""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.get("/", headers=self.headers)
                if response.status_code >= 400:
                    raise ExternalAPIException(
                        message=f"REST API连接失败: HTTP {response.status_code}",
                        api_name="REST_API",
                        endpoint=self.base_url,
                        status_code=response.status_code,
                        response_body=response.text
                    )
                return True
        except httpx.TimeoutException:
            raise ExternalAPIException(
                message="REST API连接超时",
                api_name="REST_API",
                endpoint=self.base_url
            )
        except httpx.HTTPError as e:
            raise ExternalAPIException(
                message=f"REST API连接失败: {str(e)}",
                api_name="REST_API",
                endpoint=self.base_url
            )

    async def disconnect(self):
        """断开连接"""
        pass

    async def query(self, query_str: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """执行查询"""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post(
                    query_str,
                    json=params or {},
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, list) else [data]
        except httpx.TimeoutException:
            raise ExternalAPIException(
                message="REST API查询超时",
                api_name="REST_API",
                endpoint=query_str
            )
        except httpx.HTTPStatusError as e:
            raise ExternalAPIException(
                message=f"REST API查询失败: HTTP {e.response.status_code}",
                api_name="REST_API",
                endpoint=query_str,
                status_code=e.response.status_code,
                response_body=e.response.text
            )
        except httpx.HTTPError as e:
            raise ExternalAPIException(
                message=f"REST API查询失败: {str(e)}",
                api_name="REST_API",
                endpoint=query_str
            )

    async def fetch_data(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """获取数据"""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.get(endpoint, params=params, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise ExternalAPIException(
                message="REST API获取数据超时",
                api_name="REST_API",
                endpoint=endpoint
            )
        except httpx.HTTPStatusError as e:
            raise ExternalAPIException(
                message=f"REST API获取数据失败: HTTP {e.response.status_code}",
                api_name="REST_API",
                endpoint=endpoint,
                status_code=e.response.status_code,
                response_body=e.response.text
            )
        except httpx.HTTPError as e:
            raise ExternalAPIException(
                message=f"REST API获取数据失败: {str(e)}",
                api_name="REST_API",
                endpoint=endpoint
            )


class DatabaseDataConnector(BaseDataConnector):
    """数据库连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.db_type = config.get("db_type", "postgresql")
        self.connection_string = config.get("connection_string", "")

    async def connect(self) -> bool:
        """建立连接"""
        try:
            if self.db_type == "postgresql":
                from app.db.session import engine
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return True
            return False
        except SQLAlchemyError as e:
            raise DatabaseException(
                message=f"数据库连接失败: {str(e)}",
                operation="connect",
                original_error=str(e)
            )
        except (ValueError, KeyError) as e:
            raise DatabaseException(
                message=f"数据库连接数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)},
                is_critical=True
            )
        except (OSError, IOError) as e:
            raise DatabaseException(
                message=f"数据库连接IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)},
                is_critical=True
            )
        except Exception as e:
            raise DatabaseException(
                message=f"数据库连接失败: {str(e)}",
                operation="connect",
                original_error=str(e)
            )

    async def disconnect(self):
        """断开连接"""
        pass

    async def query(self, query_str: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """执行查询"""
        try:
            from app.db.session import engine
            from sqlalchemy import text

            async with engine.connect() as conn:
                result = await conn.execute(text(query_str), params or {})
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as e:
            raise DatabaseException(
                message=f"数据库查询失败: {str(e)}",
                operation="query",
                query=query_str[:200],
                original_error=str(e)
            )
        except (ValueError, KeyError) as e:
            raise DatabaseException(
                message=f"数据库查询数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)},
                is_critical=True
            )
        except (OSError, IOError) as e:
            raise DatabaseException(
                message=f"数据库查询IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)},
                is_critical=True
            )
        except Exception as e:
            raise DatabaseException(
                message=f"数据库查询失败: {str(e)}",
                operation="query",
                query=query_str[:200] if query_str else None,
                original_error=str(e)
            )

    async def fetch_data(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """获取数据"""
        return await self.query(endpoint, params)


class MinioDataConnector(BaseDataConnector):
    """MinIO 对象存储连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.endpoint = config.get("endpoint", "localhost:9000")
        self.access_key = config.get("access_key", "")
        self.secret_key = config.get("secret_key", "")
        self.bucket_name = config.get("bucket_name", "")
        self.secure = config.get("secure", False)

    async def connect(self) -> bool:
        """建立连接"""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            return self.client.bucket_exists(self.bucket_name)
        except ResponseError as e:
            raise CacheException(
                message=f"MinIO连接失败: {str(e)}",
                cache_type="minio",
                is_critical=True
            )
        except (ValueError, KeyError) as e:
            raise CacheException(
                message=f"MinIO连接数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)},
                is_critical=True
            )
        except (OSError, IOError) as e:
            raise CacheException(
                message=f"MinIO连接IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)},
                is_critical=True
            )
        except Exception as e:
            raise CacheException(
                message=f"MinIO连接失败: {str(e)}",
                cache_type="minio",
                is_critical=True
            )

    async def disconnect(self):
        """断开连接"""
        pass

    async def query(self, query_str: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """不支持查询操作"""
        logger.warning("MinIO连接器不支持query操作")
        return []

    async def fetch_data(self, object_name: str, params: Optional[Dict] = None) -> Any:
        """获取对象数据"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()

            if params and params.get("as_json"):
                return json.loads(data.decode('utf-8'))
            return data
        except ResponseError as e:
            raise CacheException(
                message=f"MinIO获取数据失败: {str(e)}",
                cache_type="minio",
                key=object_name,
                is_critical=True
            )
        except json.JSONDecodeError as e:
            raise CacheException(
                message=f"MinIO数据JSON解析失败: {str(e)}",
                cache_type="minio",
                key=object_name,
                is_critical=False
            )
        except (ValueError, KeyError) as e:
            raise CacheException(
                message=f"MinIO获取数据数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)},
                is_critical=False
            )
        except (OSError, IOError) as e:
            raise CacheException(
                message=f"MinIO获取数据IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)},
                is_critical=False
            )
        except Exception as e:
            raise CacheException(
                message=f"MinIO获取数据失败: {str(e)}",
                cache_type="minio",
                key=object_name,
                is_critical=True
            )


class ExcelDataConnector(BaseDataConnector):
    """Excel 数据连接器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_path = config.get("file_path", "")

    async def connect(self) -> bool:
        """检查文件是否存在"""
        import os
        return os.path.exists(self.file_path)

    async def disconnect(self):
        """断开连接"""
        pass

    async def query(self, sheet_name: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """查询Excel数据"""
        try:
            import pandas as pd

            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            return df.to_dict('records')
        except FileNotFoundError:
            raise ServiceException(
                message=f"Excel文件不存在: {self.file_path}",
                code="FILE_NOT_FOUND",
                details={"file_path": self.file_path}
            )
        except ImportError:
            raise ServiceException(
                message="缺少pandas库，请安装: pip install pandas openpyxl",
                code="DEPENDENCY_MISSING",
                details={"required_package": "pandas"}
            )
        except (ValueError, KeyError) as e:
            raise ServiceException(
                message=f"Excel查询数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise ServiceException(
                message=f"Excel查询IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise ServiceException(
                message=f"Excel查询失败: {str(e)}",
                code="EXCEL_ERROR",
                details={"file_path": self.file_path, "sheet_name": sheet_name}
            )

    async def fetch_data(self, sheet_name: str = "Sheet1", params: Optional[Dict] = None) -> Any:
        """获取Excel数据"""
        return await self.query(sheet_name, params)


class DataSourceManager:
    """
    数据源管理器
    
    统一管理多种数据源
    """

    def __init__(self):
        self._connectors: Dict[str, BaseDataConnector] = {}
        self._configs: Dict[str, DataSourceConfig] = {}
        logger.info("✅ 数据源管理器初始化完成")

    def register_datasource(
        self,
        name: str,
        source_type: DataSourceType,
        config: Dict[str, Any],
        enabled: bool = True
    ) -> bool:
        """
        注册数据源
        
        Args:
            name: 数据源名称
            source_type: 数据源类型
            config: 配置信息
            enabled: 是否启用
            
        Returns:
            是否注册成功
        """
        try:
            source_config = DataSourceConfig(source_type, name, config, enabled)
            self._configs[name] = source_config

            connector = self._create_connector(source_config)
            if connector:
                self._connectors[name] = connector
                logger.info(f"✅ 数据源已注册: {name} ({source_type.value})")
                return True

            return False
        except ServiceException:
            raise
        except (ValueError, KeyError) as e:
            raise ServiceException(
                message=f"数据源注册数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise ServiceException(
                message=f"数据源注册IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise ServiceException(
                message=f"数据源注册失败: {str(e)}",
                code="DATASOURCE_REGISTRATION_ERROR",
                details={"name": name, "source_type": source_type.value}
            )

    def _create_connector(self, config: DataSourceConfig) -> Optional[BaseDataConnector]:
        """创建连接器"""
        try:
            if config.source_type == DataSourceType.REST_API:
                return RESTAPIDataConnector(config.config)
            elif config.source_type == DataSourceType.DATABASE:
                return DatabaseDataConnector(config.config)
            elif config.source_type == DataSourceType.MINIO:
                return MinioDataConnector(config.config)
            elif config.source_type == DataSourceType.EXCEL:
                return ExcelDataConnector(config.config)
            else:
                logger.warning(f"不支持的数据源类型: {config.source_type}")
                return None
        except ServiceException:
            raise
        except (ValueError, KeyError) as e:
            raise ServiceException(
                message=f"创建连接器数据错误: {str(e)}",
                details={"error_type": "data_error", "original_error": str(e)}
            )
        except (OSError, IOError) as e:
            raise ServiceException(
                message=f"创建连接器IO错误: {str(e)}",
                details={"error_type": "io_error", "original_error": str(e)}
            )
        except Exception as e:
            raise ServiceException(
                message=f"创建连接器失败: {str(e)}",
                code="CONNECTOR_CREATION_ERROR",
                details={"source_type": config.source_type.value}
            )

    async def connect(self, name: str) -> bool:
        """连接数据源"""
        connector = self._connectors.get(name)
        if connector:
            return await connector.connect()
        return False

    async def connect_all(self):
        """连接所有启用的数据源"""
        for name, connector in self._connectors.items():
            config = self._configs.get(name)
            if config and config.enabled:
                success = await connector.connect()
                if not success:
                    logger.warning(f"⚠️ 数据源连接失败: {name}")

    async def disconnect(self, name: str):
        """断开数据源连接"""
        connector = self._connectors.get(name)
        if connector:
            await connector.disconnect()

    async def query(
        self,
        source_name: str,
        query_str: str,
        params: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """查询数据"""
        connector = self._connectors.get(source_name)
        if connector:
            return await connector.query(query_str, params)
        return []

    async def fetch_data(
        self,
        source_name: str,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Any:
        """获取数据"""
        connector = self._connectors.get(source_name)
        if connector:
            return await connector.fetch_data(endpoint, params)
        return None

    def get_datasource_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取数据源信息"""
        config = self._configs.get(name)
        if config:
            return config.to_dict()
        return None

    def list_datasources(self) -> List[Dict[str, Any]]:
        """列出租户所有数据源"""
        return [
            config.to_dict()
            for config in self._configs.values()
        ]

    def remove_datasource(self, name: str) -> bool:
        """移除数据源"""
        if name in self._connectors:
            del self._connectors[name]
        if name in self._configs:
            del self._configs[name]
            logger.info(f"✅ 数据源已移除: {name}")
            return True
        return False


data_source_manager = DataSourceManager()
