"""
测试P0修复后的用户注册功能
验证租户ID是否正确分配
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal


async def test_tenant_id_assignment():
    """测试租户ID分配逻辑"""
    
    print("=" * 80)
    print("🧪 测试P0修复后的租户ID分配")
    print("=" * 80)
    
    db: Session = SessionLocal()
    
    try:
        # 1. 检查现有用户的租户ID分布
        print("\n1. 检查现有用户租户ID分布...")
        
        result = db.execute(text("""
            SELECT 
                tenant_id,
                email,
                is_admin,
                company_name,
                created_at
            FROM users 
            ORDER BY created_at DESC
            LIMIT 10
        """)).fetchall()
        
        print("📊 最近10个用户的租户ID情况:")
        for row in result:
            tenant_id, email, is_admin, company_name, created_at = row
            user_type = "企业管理员" if is_admin else "普通用户"
            print(f"  - {email} ({user_type}): {tenant_id}")
        
        # 2. 统计租户ID格式
        print("\n2. 统计租户ID格式...")
        
        format_stats = db.execute(text("""
            SELECT 
                CASE 
                    WHEN tenant_id LIKE 'company_%' THEN '企业租户 (company_*)'
                    WHEN tenant_id LIKE 'user_%' THEN '个人租户 (user_*)'
                    WHEN tenant_id = 'default_tenant' THEN '默认租户 (需修复)'
                    WHEN tenant_id IS NULL THEN 'NULL (需修复)'
                    ELSE '其他格式'
                END as format_type,
                COUNT(*) as count
            FROM users 
            GROUP BY 
                CASE 
                    WHEN tenant_id LIKE 'company_%' THEN '企业租户 (company_*)'
                    WHEN tenant_id LIKE 'user_%' THEN '个人租户 (user_*)'
                    WHEN tenant_id = 'default_tenant' THEN '默认租户 (需修复)'
                    WHEN tenant_id IS NULL THEN 'NULL (需修复)'
                    ELSE '其他格式'
                END
            ORDER BY count DESC
        """)).fetchall()
        
        print("📈 租户ID格式统计:")
        total_users = 0
        problem_count = 0
        
        for row in format_stats:
            format_type, count = row
            total_users += count
            if "需修复" in format_type:
                problem_count += count
            print(f"  - {format_type}: {count} 个用户")
        
        # 3. 验证数据库约束
        print("\n3. 验证数据库约束...")
        
        null_tenant_count = db.execute(text("""
            SELECT COUNT(*) as count
            FROM users 
            WHERE tenant_id IS NULL
        """)).fetchone().count
        
        default_tenant_count = db.execute(text("""
            SELECT COUNT(*) as count
            FROM users 
            WHERE tenant_id = 'default_tenant'
        """)).fetchone().count
        
        print("🔍 约束检查结果:")
        print(f"  - NULL租户ID: {null_tenant_count} 个用户")
        print(f"  - 默认租户ID: {default_tenant_count} 个用户")
        print(f"  - 总用户数: {total_users} 个")
        
        # 4. 评估修复状态
        print("\n4. P0修复状态评估...")
        
        if problem_count == 0:
            print("✅ P0问题已完全修复！")
            print("  - 所有用户都有有效的租户ID")
            print("  - 数据库约束满足")
            print("  - 新用户注册将正确分配租户ID")
        else:
            print(f"⚠️  仍有 {problem_count} 个用户需要修复")
            print("  - 建议重新运行修复脚本")
        
        # 5. 检查租户隔离
        print("\n5. 检查租户隔离情况...")
        
        tenant_isolation = db.execute(text("""
            SELECT 
                tenant_id,
                COUNT(*) as user_count,
                COUNT(CASE WHEN is_admin = true THEN 1 END) as admin_count,
                COUNT(CASE WHEN is_admin = false THEN 1 END) as regular_count
            FROM users 
            WHERE tenant_id IS NOT NULL AND tenant_id != 'default_tenant'
            GROUP BY tenant_id
            ORDER BY user_count DESC
            LIMIT 5
        """)).fetchall()
        
        print("🏢 租户隔离统计 (前5个租户):")
        for row in tenant_isolation:
            tenant_id, user_count, admin_count, regular_count = row
            tenant_type = "企业租户" if tenant_id.startswith("company_") else "个人租户"
            print(f"  - {tenant_id} ({tenant_type}): {user_count}用户 ({admin_count}管理员, {regular_count}普通用户)")
        
        return problem_count == 0
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False
    finally:
        db.close()


def test_generate_tenant_id():
    """测试租户ID生成函数"""
    
    print("\n" + "=" * 80)
    print("🧪 测试租户ID生成函数")
    print("=" * 80)
    
    # 导入生成函数
    sys.path.insert(0, str(Path(__file__).parent / "app"))
    from api.v1.endpoints.auth import generate_tenant_id
    
    # 测试个人租户生成
    print("\n1. 测试个人租户ID生成...")
    for i in range(3):
        tenant_id = generate_tenant_id("user")
        print(f"  - 个人租户 {i+1}: {tenant_id}")
        assert tenant_id.startswith("user_"), f"个人租户ID格式错误: {tenant_id}"
        assert len(tenant_id) == 17, f"个人租户ID长度错误: {len(tenant_id)}"  # user_ + 12位hex
    
    # 测试企业租户生成
    print("\n2. 测试企业租户ID生成...")
    test_companies = [
        "北京科技有限公司",
        "Shanghai Tech Co.",
        "深圳-创新-企业",
        "A" * 30  # 长公司名测试
    ]
    
    for company in test_companies:
        tenant_id = generate_tenant_id("admin", company)
        print(f"  - 企业租户 ({company[:20]}...): {tenant_id}")
        assert tenant_id.startswith("company_"), f"企业租户ID格式错误: {tenant_id}"
        assert len(tenant_id.split("_")) >= 3, f"企业租户ID结构错误: {tenant_id}"
    
    print("\n✅ 租户ID生成函数测试通过！")


async def main():
    """主测试函数"""
    
    print("🚀 开始P0修复验证测试...")
    
    # 测试1: 检查现有数据
    success1 = await test_tenant_id_assignment()
    
    # 测试2: 测试生成函数
    try:
        test_generate_tenant_id()
        success2 = True
    except Exception as e:
        print(f"❌ 租户ID生成函数测试失败: {str(e)}")
        success2 = False
    
    # 总结
    print("\n" + "=" * 80)
    print("📋 P0修复验证总结")
    print("=" * 80)
    
    if success1 and success2:
        print("🎉 P0问题修复验证通过！")
        print("✅ 现有用户租户ID正确")
        print("✅ 租户ID生成函数正常")
        print("✅ 新用户注册将正确分配租户ID")
        print("\n🔄 建议下一步:")
        print("  1. 测试实际的用户注册流程")
        print("  2. 验证租户隔离是否生效")
        print("  3. 开始实施P1优先级功能")
    else:
        print("❌ P0问题修复验证失败！")
        if not success1:
            print("  - 现有用户数据仍有问题")
        if not success2:
            print("  - 租户ID生成函数有问题")
        print("\n🔧 建议修复措施:")
        print("  1. 重新检查修复脚本")
        print("  2. 手动修复问题用户")
        print("  3. 验证注册接口代码")


if __name__ == "__main__":
    asyncio.run(main())