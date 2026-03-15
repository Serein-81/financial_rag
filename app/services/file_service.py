# app/services/file_service.py
"""
文件服务 - 重构版
使用策略模式 + 工厂模式实现可扩展的文件解析
"""
from app.services.minio_service import minio_service
from app.parsers.parser_factory import FileParserFactory


class FileService:
    """
    文件服务类
    
    职责：
    1. 从 MinIO 下载文件
    2. 委托给对应的解析器提取文本
    3. 统一异常处理和日志记录
    """
    
    def __init__(self):
        self.parser_factory = FileParserFactory
    
    async def extract_text(self, file_path: str, file_type: str) -> str:
        """
        根据文件类型，提取文件中的所有文字内容（异步版本）
        
        使用策略模式：根据文件类型选择对应的解析策略
        
        Args:
            file_path: MinIO中的文件路径
            file_type: 文件MIME类型
            
        Returns:
            str: 提取的文本内容
            
        Raises:
            ValueError: 不支持的文件类型
            Exception: 文件解析失败
        """
        try:
            # 1. 从 MinIO 下载文件到内存
            file_bytes = minio_service.download_document(file_path)
            
            # 2. 使用工厂模式获取对应的解析器
            parser = self.parser_factory.get_parser(file_type)
            
            if parser is None:
                supported_types = self.parser_factory.get_supported_types()
                raise ValueError(
                    f"不支持的文件类型: {file_type}\n"
                    f"支持的类型: {', '.join(supported_types)}"
                )
            
            # 3. 使用策略模式执行解析
            content = await parser.parse(file_bytes)
            
            return content
            
        except ValueError as e:
            # 业务异常直接抛出
            print(f"⚠️ 文件类型不支持: {e}")
            raise
        except Exception as e:
            # 其他异常包装后抛出
            print(f"❌ 文件解析失败: {e}")
            raise Exception(f"文件解析失败: {str(e)}")
    
    def is_supported_type(self, file_type: str) -> bool:
        """
        检查是否支持指定的文件类型
        
        Args:
            file_type: 文件的 MIME 类型
            
        Returns:
            bool: 是否支持
        """
        return self.parser_factory.is_supported(file_type)
    
    def get_supported_types(self) -> list[str]:
        """
        获取所有支持的文件类型
        
        Returns:
            list[str]: 支持的 MIME 类型列表
        """
        return self.parser_factory.get_supported_types()


# 单例实例
file_service = FileService()