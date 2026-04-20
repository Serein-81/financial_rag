"""
租户 Repository 单元测试

测试目标：
1. 验证 BaseRepository 的租户隔离功能
2. 验证 TaxReportRepository 的特定功能
3. 验证 DocumentRepository 的特定功能
4. 验证 Mixins 的正确性

使用方法：
    pytest tests/test_tenant_repository.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextvars import ContextVar


class TestMixins:
    """Mixin 类测试"""
    
    def test_tenant_mixin_fields(self):
        """测试 TenantMixin 字段"""
        from app.models.mixins import TenantMixin
        
        assert hasattr(TenantMixin, 'tenant_id')
    
    def test_timestamp_mixin_fields(self):
        """测试 TimestampMixin 字段"""
        from app.models.mixins import TimestampMixin
        
        assert hasattr(TimestampMixin, 'created_at')
        assert hasattr(TimestampMixin, 'updated_at')
    
    def test_uuid_primary_key_mixin_fields(self):
        """测试 UUIDPrimaryKeyMixin 字段"""
        from app.models.mixins import UUIDPrimaryKeyMixin
        
        assert hasattr(UUIDPrimaryKeyMixin, 'id')
    
    def test_tenant_timestamp_mixin_fields(self):
        """测试 TenantTimestampMixin 字段"""
        from app.models.mixins import TenantTimestampMixin
        
        assert hasattr(TenantTimestampMixin, 'tenant_id')
        assert hasattr(TenantTimestampMixin, 'created_at')
        assert hasattr(TenantTimestampMixin, 'updated_at')
    
    def test_full_mixin_fields(self):
        """测试 FullMixin 字段"""
        from app.models.mixins import FullMixin
        
        assert hasattr(FullMixin, 'id')
        assert hasattr(FullMixin, 'tenant_id')
        assert hasattr(FullMixin, 'created_at')
        assert hasattr(FullMixin, 'updated_at')


class TestBaseRepository:
    """BaseRepository 测试"""
    
    @pytest.fixture
    def mock_model(self):
        """创建模拟模型"""
        from sqlalchemy import Column, String
        from app.db.base import Base
        
        class MockModel(Base):
            __tablename__ = "mock_model"
            
            id = Column(String(50), primary_key=True)
            tenant_id = Column(String(50), nullable=False, index=True)
            name = Column(String(100))
            status = Column(String(20))
        
        return MockModel
    
    @pytest.fixture
    def mock_session(self):
        """创建模拟会话"""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session
    
    @pytest.fixture
    def repo(self, mock_session, mock_model):
        """创建 Repository 实例"""
        from app.repositories.base import BaseRepository
        return BaseRepository(mock_session, mock_model)
    
    def test_repository_initialization(self, repo, mock_session, mock_model):
        """测试 Repository 初始化"""
        assert repo.session == mock_session
        assert repo.model == mock_model
        assert repo._tenant_column is not None
    
    def test_get_tenant_column(self, repo):
        """测试获取 tenant_id 列"""
        tenant_column = repo._get_tenant_column()
        assert tenant_column is not None
    
    @patch('app.repositories.base.get_current_tenant_id')
    def test_tenant_id_from_context(self, mock_get_tenant, repo):
        """测试从上下文获取 tenant_id"""
        mock_get_tenant.return_value = "tenant_123"
        
        tenant_id = repo.tenant_id
        
        assert tenant_id == "tenant_123"
    
    @patch('app.repositories.base.get_current_tenant_id')
    def test_tenant_id_missing_raises_error(self, mock_get_tenant, repo):
        """测试缺少 tenant_id 时抛出错误"""
        mock_get_tenant.return_value = None
        
        with pytest.raises(ValueError) as exc_info:
            _ = repo.tenant_id
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_requires_tenant_id(self, repo):
        """测试 get 方法需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.get("some_id")
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_with_tenant_id(self, repo, mock_session):
        """测试带 tenant_id 的 get 方法"""
        from unittest.mock import MagicMock
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await repo.get("some_id", tenant_id="tenant_123")
        
        assert result is None
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_requires_tenant_id(self, repo):
        """测试 list 方法需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.list()
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_list_with_tenant_id(self, repo, mock_session):
        """测试带 tenant_id 的 list 方法"""
        from unittest.mock import MagicMock
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result
        
        results = await repo.list(tenant_id="tenant_123")
        
        assert isinstance(results, list)
        mock_session.execute.assert_called_once()
    
    @patch('app.repositories.base.get_current_tenant_id')
    @pytest.mark.asyncio
    async def test_create_auto_sets_tenant_id(self, mock_get_tenant, repo, mock_session):
        """测试 create 方法自动设置 tenant_id"""
        from unittest.mock import MagicMock
        
        mock_get_tenant.return_value = "tenant_123"
        mock_session.refresh = AsyncMock()
        
        instance = MagicMock()
        instance.id = "new_id"
        mock_session.add = MagicMock()
        
        result = await repo.create(name="Test")
        
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_count_requires_tenant_id(self, repo):
        """测试 count 方法需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.count()
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_count_with_tenant_id(self, repo, mock_session):
        """测试带 tenant_id 的 count 方法"""
        from unittest.mock import MagicMock
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result
        
        count = await repo.count(tenant_id="tenant_123")
        
        assert count == 0
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exists_requires_tenant_id(self, repo):
        """测试 exists 方法需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.exists("some_id")
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_paginate_requires_tenant_id(self, repo):
        """测试 paginate 方法需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.paginate()
        
        assert "Missing tenant context" in str(exc_info.value)


class TestTaxReportRepository:
    """TaxReportRepository 测试"""
    
    @pytest.fixture
    def mock_session(self):
        """创建模拟会话"""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session
    
    @pytest.fixture
    def repo(self, mock_session):
        """创建 TaxReportRepository 实例"""
        from app.repositories.tax_report import TaxReportRepository
        return TaxReportRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_find_duplicates_requires_tenant_id(self, repo):
        """测试 find_duplicates 需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.find_duplicates(filename="test.pdf")
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_find_duplicates_with_tenant_id(self, repo, mock_session):
        """测试带 tenant_id 的 find_duplicates"""
        from unittest.mock import MagicMock
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await repo.find_duplicates(
            tenant_id="tenant_123",
            filename="test.pdf"
        )
        
        assert result is None
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_status_requires_tenant_id(self, repo):
        """测试 get_by_status 需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.get_by_status("pending")
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_count_by_status_requires_tenant_id(self, repo):
        """测试 count_by_status 需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.count_by_status()
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_report_sets_tenant_id(self, repo, mock_session):
        """测试 create_report 方法设置 tenant_id"""
        from unittest.mock import MagicMock
        
        mock_session.refresh = AsyncMock()
        instance = MagicMock()
        instance.id = "new_report_id"
        mock_session.add = MagicMock()
        
        result = await repo.create_report(
            user_id="user_123",
            tenant_id="tenant_123",
            filename="test.pdf",
            original_filename="test.pdf",
            file_type="pdf",
            file_size=1024,
            minio_path="/path/to/file"
        )
        
        mock_session.add.assert_called_once()


class TestDocumentRepository:
    """DocumentRepository 测试"""
    
    @pytest.fixture
    def mock_session(self):
        """创建模拟会话"""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session
    
    @pytest.fixture
    def repo(self, mock_session):
        """创建 DocumentRepository 实例"""
        from app.repositories.document import DocumentRepository
        return DocumentRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_get_public_docs_requires_tenant_id(self, repo):
        """测试 get_public_docs 需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.get_public_docs()
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_by_kb_id_requires_tenant_id(self, repo):
        """测试 get_by_kb_id 需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.get_by_kb_id("kb_123")
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_private_docs_requires_tenant_id(self, repo):
        """测试 get_private_docs 需要 tenant_id"""
        with pytest.raises(ValueError) as exc_info:
            await repo.get_private_docs("user_123")
        
        assert "Missing tenant context" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_document_sets_tenant_id(self, repo, mock_session):
        """测试 create_document 方法设置 tenant_id"""
        from unittest.mock import MagicMock
        
        mock_session.refresh = AsyncMock()
        instance = MagicMock()
        instance.id = "new_doc_id"
        mock_session.add = MagicMock()
        
        result = await repo.create_document(
            tenant_id="tenant_123",
            kb_id="kb_456",
            user_id="user_789",
            filename="test.pdf",
            file_path="/path/to/file"
        )
        
        mock_session.add.assert_called_once()


class TestTenantContextIntegration:
    """租户上下文集成测试"""
    
    @patch('app.middleware.tenant_middleware.tenant_context')
    @patch('app.middleware.tenant_middleware.user_context')
    def test_context_var_usage(self, mock_user_context, mock_tenant_context):
        """测试 ContextVar 的使用"""
        from app.middleware.tenant_middleware import get_current_tenant_id, get_current_user_id
        
        mock_tenant_context.get.return_value = "test_tenant"
        mock_user_context.get.return_value = "test_user"
        
        tenant_id = get_current_tenant_id()
        user_id = get_current_user_id()
        
        assert tenant_id == "test_tenant"
        assert user_id == "test_user"
    
    @patch('app.middleware.tenant_middleware.tenant_context')
    def test_context_var_returns_none_when_not_set(self, mock_tenant_context):
        """测试 ContextVar 未设置时返回 None"""
        from app.middleware.tenant_middleware import get_current_tenant_id
        
        mock_tenant_context.get.return_value = None
        
        tenant_id = get_current_tenant_id()
        
        assert tenant_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
