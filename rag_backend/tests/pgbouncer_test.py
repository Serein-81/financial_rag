#!/usr/bin/env python3
"""
PgBouncer Transaction 模式 - 扩展测试脚本

测试新增的 Repository：
1. AgentTraceRepository
2. ToolCallTraceRepository  
3. TenantAuditLogRepository

使用方法：
    cd /app && python tests/pgbouncer_test.py
"""

import sys
sys.path.insert(0, '/app')

print('=' * 60)
print('PgBouncer Transaction 模式 - 扩展测试')
print('=' * 60)
print()

# 测试 1: 所有 Repository 导入
try:
    from app.repositories.base import BaseRepository
    from app.repositories.tax_report import TaxReportRepository
    from app.repositories.document import DocumentRepository
    from app.repositories.agent_trace import AgentTraceRepository, AgentStepRepository
    from app.repositories.tool_trace import ToolCallTraceRepository
    from app.repositories.tenant_audit_log import TenantAuditLogRepository
    print('[PASS] 测试 1: 所有 Repository 导入成功')
except Exception as e:
    print(f'[FAIL] 测试 1 失败: {e}')
    sys.exit(1)

# 测试 2: 配置验证
try:
    from app.core.config import settings
    assert settings.DB_POOL_SIZE == 5, 'DB_POOL_SIZE 配置错误'
    assert settings.PGBOUNCER_ENABLED == False, 'PGBOUNCER_ENABLED 默认值错误'
    print('[PASS] 测试 2: 配置验证通过')
    print(f'      - DATABASE_URL: {settings.DATABASE_URL}')
    print(f'      - DB_POOL_SIZE: {settings.DB_POOL_SIZE}')
    print(f'      - PGBOUNCER_ENABLED: {settings.PGBOUNCER_ENABLED}')
except Exception as e:
    print(f'[FAIL] 测试 2 失败: {e}')
    sys.exit(1)

# 测试 3: get_db 不包含 SET LOCAL
try:
    import inspect
    from app.db.session import get_db
    source = inspect.getsource(get_db)
    lines = source.split('\n')
    
    code_lines = []
    in_docstring = False
    docstring_delimiters = ('"""', "'''")
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if 'def get_db' in stripped or stripped.startswith('async def get_db'):
            continue
        if stripped.startswith('#'):
            continue
        if any(stripped.startswith(d) for d in docstring_delimiters):
            if not in_docstring:
                in_docstring = True
                continue
            else:
                in_docstring = False
                continue
        if in_docstring:
            continue
        code_lines.append(line)
    
    actual_code = '\n'.join(code_lines)
    
    if 'SET LOCAL' in actual_code:
        raise AssertionError('get_db 仍包含 SET LOCAL')
    if 'set_tenant_context_for_db' in actual_code:
        raise AssertionError('get_db 仍调用 set_tenant_context_for_db')
    print('[PASS] 测试 3: get_db 已移除 SET LOCAL 依赖')
except Exception as e:
    print(f'[FAIL] 测试 3 失败: {e}')
    sys.exit(1)

# 测试 4: Repository 功能验证
try:
    from unittest.mock import MagicMock, AsyncMock
    from sqlalchemy import Column, String
    from app.db.base import Base
    
    class TestModel(Base):
        __tablename__ = 'test_table'
        id = Column(String(50), primary_key=True)
        tenant_id = Column(String(50), nullable=False, index=True)
    
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    repo = BaseRepository(mock_session, TestModel)
    assert repo._tenant_column is not None, 'tenant_column 应不为 None'
    print('[PASS] 测试 4: Repository 功能验证')
except Exception as e:
    print(f'[FAIL] 测试 4 失败: {e}')
    sys.exit(1)

# 测试 5: 连接池配置
try:
    from app.db.session import engine, AsyncSessionLocal
    print('[PASS] 测试 5: 引擎和连接池配置成功')
except Exception as e:
    print(f'[FAIL] 测试 5 失败: {e}')
    sys.exit(1)

# 测试 6: TenantSecurityService 验证
try:
    from app.services.tenant_security_service import TenantSecurityService
    assert hasattr(TenantSecurityService, 'validate_tenant_access')
    assert hasattr(TenantSecurityService, 'log_security_event')
    print('[PASS] 测试 6: TenantSecurityService 验证')
except Exception as e:
    print(f'[FAIL] 测试 6 失败: {e}')
    sys.exit(1)

print()
print('=' * 60)
print('所有扩展测试通过！')
print('=' * 60)
print()
print('已创建的 Repository：')
print('  1. BaseRepository - 基础 Repository')
print('  2. TaxReportRepository - 税务报告')
print('  3. DocumentRepository - 文档')
print('  4. TenantAuditLogRepository - 租户审计日志')
print('  5. AgentTraceRepository - Agent 追踪')
print('  6. AgentStepRepository - Agent 步骤')
print('  7. ToolCallTraceRepository - 工具调用追踪')
print()
print('后续步骤：')
print('1. 继续改造其他 Service 层')
print('2. 配置 PgBouncer Transaction 模式')
print('3. 进行集成测试')
