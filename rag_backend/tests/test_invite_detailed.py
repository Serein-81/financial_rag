import traceback
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.services.invite_code_service import InviteCodeService

async def test_get_invite_codes():
    try:
        print("Testing get_tenant_invite_codes...")

        # 模拟API调用
        async with AsyncSessionLocal() as db:
            # 检查表是否存在
            result = await db.execute(text('SELECT COUNT(*) FROM invite_codes'))
            count = result.scalar()
            print(f"Found {count} invite codes in database")

            # 尝试调用服务
            from app.middleware.tenant_middleware import set_tenant_context_for_db
            await set_tenant_context_for_db(db, "test_tenant_001")

            codes = await InviteCodeService.get_tenant_invite_codes(
                db=db,
                tenant_id="test_tenant_001",
                skip=0,
                limit=20,
                include_inactive=False
            )
            print(f"Successfully retrieved {len(codes)} invite codes")
            return codes
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None

asyncio.run(test_get_invite_codes())
