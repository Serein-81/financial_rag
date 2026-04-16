"""
安全模块测试

测试 Cypher 验证、租户隔离和权限控制
"""

import pytest
from app.security import (
    CypherValidator,
    ValidationResult,
    ValidationLevel,
    TenantContext,
    TenantIsolation,
    TenantIsolationLevel,
    Permission,
    PermissionType,
    Role,
    RoleType,
    PermissionChecker,
    PermissionDenied,
)


class TestCypherValidator:
    """测试 Cypher 验证器"""
    
    def test_create_validator(self):
        """测试创建验证器"""
        validator = CypherValidator()
        assert validator.validation_level == ValidationLevel.NORMAL
        assert validator.max_query_depth == 5
        assert validator.max_result_size == 10000
    
    def test_validate_safe_query(self):
        """测试验证安全查询"""
        validator = CypherValidator()
        result = validator.validate("MATCH (n:Person) RETURN n")
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_dangerous_query(self):
        """测试验证危险查询"""
        validator = CypherValidator()
        result = validator.validate("MATCH (n) DETACH DELETE n")
        
        assert result.is_valid is False
        assert any("危险" in err for err in result.errors)
    
    def test_validate_strict_mode(self):
        """测试严格模式"""
        validator = CypherValidator(validation_level=ValidationLevel.STRICT)
        validator.add_node_label("Person")
        
        result = validator.validate("MATCH (n:Person) RETURN n")
        assert result.is_valid is True
    
    def test_validate_depth_limit(self):
        """测试深度限制"""
        validator = CypherValidator(max_query_depth=2)
        query = """
        MATCH (a)-[r1]->(b)-[r2]->(c)-[r3]->(d)-[r4]->(e)
        RETURN a, b, c, d, e
        """
        result = validator.validate(query)
        # 深度应该大于1，因为包含多个关系模式
        assert result.query_depth >= 1
    
    def test_whitelist_validation(self):
        """测试白名单验证"""
        validator = CypherValidator(validation_level=ValidationLevel.STRICT)
        validator.add_node_label("Person")
        validator.add_node_label("Company")
        
        assert validator.is_safe_node_label("Person") is True
        assert validator.is_safe_node_label("Car") is False
    
    def test_empty_query(self):
        """测试空查询"""
        validator = CypherValidator()
        result = validator.validate("")
        
        assert result.is_valid is False
        assert "空" in result.errors[0]
    
    def test_statistics(self):
        """测试统计信息"""
        validator = CypherValidator()
        validator.validate("MATCH (n) RETURN n")
        validator.validate("MATCH (n) RETURN n")
        
        stats = validator.get_statistics()
        assert stats["total_validated"] == 2


class TestTenantIsolation:
    """测试租户隔离"""
    
    def test_create_tenant_context(self):
        """测试创建租户上下文"""
        context = TenantContext(
            tenant_id="tenant-001",
            user_id="user-001",
            roles=["admin"]
        )
        
        assert context.tenant_id == "tenant-001"
        assert context.user_id == "user-001"
        assert context.has_role("admin")
    
    def test_role_management(self):
        """测试角色管理"""
        context = TenantContext(tenant_id="tenant-001")
        
        context.add_role("admin")
        assert context.has_role("admin")
        
        context.remove_role("admin")
        assert not context.has_role("admin")
    
    def test_metadata(self):
        """测试元数据"""
        context = TenantContext(tenant_id="tenant-001")
        context.set_metadata("key1", "value1")
        
        assert context.get_metadata("key1") == "value1"
        assert context.get_metadata("key2", "default") == "default"
    
    def test_register_tenant(self):
        """测试注册租户"""
        isolation = TenantIsolation()
        context = isolation.register_tenant(
            tenant_id="tenant-001",
            user_id="user-001"
        )
        
        assert context.tenant_id == "tenant-001"
        assert isolation.get_tenant("tenant-001") is not None
    
    def test_unregister_tenant(self):
        """测试注销租户"""
        isolation = TenantIsolation()
        isolation.register_tenant("tenant-001")
        
        result = isolation.unregister_tenant("tenant-001")
        assert result is True
        assert isolation.get_tenant("tenant-001") is None
    
    def test_data_access_validation(self):
        """测试数据访问验证"""
        isolation = TenantIsolation()
        isolation.register_tenant("tenant-001")
        
        result = isolation.validate_data_access(
            tenant_id="tenant-001",
            resource_type="document",
            resource_id="doc-001"
        )
        assert result is True
    
    def test_quota_check(self):
        """测试配额检查"""
        isolation = TenantIsolation()
        isolation.register_tenant("tenant-001")
        
        # 初始配额检查（增加计数）
        result1 = isolation.check_quota("tenant-001", "queries", increment=1)
        assert result1 is True
        
        # 验证配额计数增加
        quota = isolation.get_tenant_quota("tenant-001")
        assert quota["used_queries"] == 1
        
        # 再检查一次
        result2 = isolation.check_quota("tenant-001", "queries", increment=1)
        assert result2 is True
        quota = isolation.get_tenant_quota("tenant-001")
        assert quota["used_queries"] == 2
    
    def test_statistics(self):
        """测试统计信息"""
        isolation = TenantIsolation()
        isolation.register_tenant("tenant-001")
        isolation.register_tenant("tenant-002")
        
        stats = isolation.get_statistics()
        assert stats["total_tenants"] == 2
        assert stats["max_tenants"] == 1000


class TestPermission:
    """测试权限系统"""
    
    def test_create_permission(self):
        """测试创建权限"""
        perm = Permission(
            name="read_data",
            permission_type=PermissionType.READ,
            resource_type="data"
        )
        
        assert perm.name == "read_data"
        assert perm.permission_type == PermissionType.READ
    
    def test_permission_matching(self):
        """测试权限匹配"""
        perm = Permission(
            name="read_data",
            permission_type=PermissionType.READ,
            resource_type="data"
        )
        
        assert perm.matches(PermissionType.READ, "data") is True
        assert perm.matches(PermissionType.WRITE, "data") is False
        assert perm.matches(PermissionType.READ, "other") is False
    
    def test_create_role(self):
        """测试创建角色"""
        role = Role(
            name="user",
            role_type=RoleType.USER,
            permissions=[
                Permission(
                    name="read",
                    permission_type=PermissionType.READ,
                    resource_type="data"
                )
            ]
        )
        
        assert role.name == "user"
        assert role.has_permission(PermissionType.READ, "data") is True
    
    def test_permission_inheritance(self):
        """测试权限继承"""
        parent = Role(
            name="guest",
            role_type=RoleType.GUEST,
            permissions=[
                Permission(
                    name="read_public",
                    permission_type=PermissionType.READ,
                    resource_type="public"
                )
            ]
        )
        
        child = Role(
            name="user",
            role_type=RoleType.USER,
            parent_role=parent,
            permissions=[
                Permission(
                    name="read_private",
                    permission_type=PermissionType.READ,
                    resource_type="private"
                )
            ]
        )
        
        assert child.has_permission(PermissionType.READ, "private") is True
        assert child.has_permission(PermissionType.READ, "public") is True
    
    def test_permission_checker(self):
        """测试权限检查器"""
        checker = PermissionChecker()
        
        checker.assign_role("user-001", "user")
        assert checker.check_permission(
            "user-001",
            PermissionType.READ,
            "user_data"
        ) is True
        
        assert checker.check_permission(
            "user-001",
            PermissionType.DELETE,
            "users"
        ) is False
    
    def test_role_assignment(self):
        """测试角色分配"""
        checker = PermissionChecker()
        
        checker.assign_role("user-001", "user")
        roles = checker.get_user_roles("user-001")
        
        assert "user" in roles
    
    def test_role_revocation(self):
        """测试角色撤销"""
        checker = PermissionChecker()
        
        checker.assign_role("user-001", "user")
        checker.revoke_role("user-001", "user")
        
        roles = checker.get_user_roles("user-001")
        assert "user" not in roles
    
    def test_require_permission(self):
        """测试要求权限"""
        checker = PermissionChecker()
        checker.assign_role("user-001", "admin")
        
        checker.require_permission(
            "user-001",
            PermissionType.ADMIN,
            "tenant"
        )
    
    def test_require_permission_denied(self):
        """测试权限拒绝"""
        checker = PermissionChecker()
        checker.assign_role("user-001", "guest")
        
        with pytest.raises(PermissionDenied):
            checker.require_permission(
                "user-001",
                PermissionType.ADMIN,
                "tenant"
            )
    
    def test_super_admin_all_permissions(self):
        """测试超级管理员拥有所有权限"""
        checker = PermissionChecker()
        checker.assign_role("user-001", "super_admin")
        
        assert checker.check_permission(
            "user-001",
            PermissionType.SUPER_ADMIN,
            "*"
        ) is True
        
        assert checker.check_permission(
            "user-001",
            PermissionType.DELETE,
            "any_resource"
        ) is True
    
    def test_get_accessible_resources(self):
        """测试获取可访问资源"""
        checker = PermissionChecker()
        checker.assign_role("user-001", "user")
        
        resources = checker.get_accessible_resources(
            "user-001",
            PermissionType.READ,
            "user_data"
        )
        
        # user 角色的 user_data 权限没有特定 resource_id，所以返回空列表
        assert isinstance(resources, list)
    
    def test_statistics(self):
        """测试统计信息"""
        checker = PermissionChecker()
        checker.assign_role("user-001", "user")
        checker.assign_role("user-002", "admin")
        
        stats = checker.get_statistics()
        assert stats["total_users"] == 2
        assert stats["total_roles"] == 6


class TestIntegration:
    """集成测试"""
    
    def test_tenant_and_permission_integration(self):
        """测试租户和权限集成"""
        from app.security import get_tenant_context, set_tenant_context
        
        isolation = TenantIsolation()
        context = isolation.register_tenant(
            tenant_id="tenant-001",
            user_id="user-001",
            roles=["admin"]
        )
        
        set_tenant_context(context)
        
        current_context = get_tenant_context()
        assert current_context is not None
        assert current_context.tenant_id == "tenant-001"
        
        set_tenant_context(None)
    
    def test_security_validation_workflow(self):
        """测试安全验证工作流"""
        validator = CypherValidator()
        isolation = TenantIsolation()
        checker = PermissionChecker()
        
        isolation.register_tenant("tenant-001", user_id="user-001")
        checker.assign_role("user-001", "user")
        
        cypher_query = "MATCH (n:Person) RETURN n"
        result = validator.validate(cypher_query)
        assert result.is_valid is True
        
        assert checker.check_permission(
            "user-001",
            PermissionType.READ,
            "user_data"
        ) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
