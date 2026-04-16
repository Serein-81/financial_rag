import asyncio
import httpx
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.security import create_access_token
from datetime import timedelta

async def get_admin_user():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('''
            SELECT u.id, u.tenant_id
            FROM users u
            WHERE u.is_admin = true
            LIMIT 1
        '''))
        return result.fetchone()

async def main():
    # 获取管理员用户
    admin = await get_admin_user()
    if not admin:
        print("No admin user found")
        return

    user_id, tenant_id = admin
    print(f"Admin user: {user_id}, tenant: {tenant_id}")

    # 创建token
    expires_delta = timedelta(hours=24)
    token = create_access_token(
        subject=str(user_id),
        expires_delta=expires_delta,
        tenant_id=tenant_id
    )
    print(f"Token created: {token[:50]}...")

    # 测试API调用 - 不跟随重定向
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0, follow_redirects=False) as client:
        headers = {"Authorization": f"Bearer {token}"}
        print("\n测试 GET /api/v1/invite-codes (NO redirect)")
        try:
            response = await client.get("/api/v1/invite-codes", headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            if response.status_code == 307:
                print(f"Redirect to: {response.headers.get('location')}")
            elif response.status_code == 200:
                print(f"Success: {len(response.json())} invite codes")
        except Exception as e:
            print(f"Request failed: {e}")

asyncio.run(main())
