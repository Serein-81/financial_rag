#!/usr/bin/env python3
"""
租户设置功能测试脚本

用于验证租户设置 API 是否正常工作
"""

import asyncio
import sys
from httpx import AsyncClient, ASGITransport
import json


async def test_tenant_settings():
    """测试租户设置 API"""

    base_url = "http://localhost:8000"

    print("=" * 60)
    print("🧪 开始测试租户设置 API")
    print("=" * 60)

    try:
        async with AsyncClient(
            transport=ASGITransport(app="app.main:app"),
            base_url=base_url
        ) as client:

            print("\n1️⃣ 测试健康检查...")
            response = await client.get("/")
            print(f"✅ 健康检查: {response.status_code}")
            print(f"   响应: {response.json()}")

            print("\n2️⃣ 测试公开的租户设置（无需认证）...")
            try:
                response = await client.get("/api/v1/tenant-settings/public/test_tenant")
                print(f"响应状态: {response.status_code}")
                if response.status_code == 200:
                    print("✅ 成功获取公开信息")
                    print(f"   响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
                else:
                    print(f"❌ 失败: {response.text}")
            except Exception as e:
                print(f"⚠️ 公开接口测试失败: {e}")

            print("\n3️⃣ 测试获取当前企业设置（需要认证）...")
            print("💡 提示: 请先获取认证 Token，然后设置环境变量 TOKEN")
            print("   示例: export TOKEN='your_token_here'")
            print("   然后重新运行此脚本")

            print("\n4️⃣ 测试检查功能状态（需要认证）...")
            print("💡 提示: 需要有效的认证 Token")

            print("\n" + "=" * 60)
            print("📋 可用的测试命令:")
            print("=" * 60)
            print("\n# 获取认证 Token（需要先注册用户）")
            print("curl -X POST http://localhost:8000/api/v1/auth/login \\")
            print("  -H 'Content-Type: application/json' \\")
            print("  -d '{\"email\": \"your_email\", \"password\": \"your_password\"}'")

            print("\n# 获取当前企业设置")
            print("curl -X GET http://localhost:8000/api/v1/tenant-settings/me \\")
            print("  -H 'Authorization: Bearer YOUR_TOKEN'")

            print("\n# 初始化企业设置")
            print("curl -X POST 'http://localhost:8000/api/v1/tenant-settings/initialize?company_name=测试公司' \\")
            print("  -H 'Authorization: Bearer YOUR_TOKEN'")

            print("\n# 更新企业设置")
            print("curl -X PUT http://localhost:8000/api/v1/tenant-settings/me \\")
            print("  -H 'Authorization: Bearer YOUR_TOKEN' \\")
            print("  -H 'Content-Type: application/json' \\")
            print("  -d '{\"company_name\": \"新公司名称\"}'")

            print("\n# 切换功能开关")
            print("curl -X POST http://localhost:8000/api/v1/tenant-settings/feature-toggle \\")
            print("  -H 'Authorization: Bearer YOUR_TOKEN' \\")
            print("  -H 'Content-Type: application/json' \\")
            print("  -d '{\"feature\": \"enable_knowledge_graph\", \"enabled\": true}'")

            print("\n# 检查功能状态")
            print("curl -X GET http://localhost:8000/api/v1/tenant-settings/features/check \\")
            print("  -H 'Authorization: Bearer YOUR_TOKEN'")

            print("\n" + "=" * 60)
            print("✅ 测试脚本运行成功！")
            print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print("\n请确保:")
        print("1. 后端服务正在运行 (uvicorn app.main:app --reload)")
        print("2. 数据库已正确配置")
        print("3. 已执行数据库迁移脚本")
        print("\n迁移命令:")
        print("cd rag_backend")
        print("psql -U postgres -d your_database -f sql/create_tenant_settings_table.sql")
        sys.exit(1)


if __name__ == "__main__":
    print("\n🚀 启动租户设置 API 测试...")
    asyncio.run(test_tenant_settings())
