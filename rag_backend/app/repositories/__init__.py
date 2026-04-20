"""
Repository 模式实现

提供标准化的数据库操作接口，自动处理租户隔离

使用方式：
    from app.repositories.base import BaseRepository
    
    class DocumentRepository(BaseRepository[Document]):
        def __init__(self, session: AsyncSession):
            super().__init__(session, Document)
        
        async def get_by_filename(self, filename: str):
            return await self.list(filename=filename)
"""

from app.repositories.base import BaseRepository

__all__ = ['BaseRepository']
