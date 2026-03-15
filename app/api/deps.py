# app/api/deps.py
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
# 👇 关键修改 1：引入 HTTPBearer 和 HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import ValidationError
from uuid import UUID

from app.core.config import settings
from app.db import AsyncSessionLocal
from app.models.user import User
from app.schemas.auth import TokenPayload

# 👇 关键修改 2：改用 HTTPBearer
# 这会让 Swagger UI 的小锁弹窗变成一个简单的 "Value" 输入框，专门用来粘贴 Token
# 不再绑定具体的 loginUrl，解耦了登录方式
security = HTTPBearer()


# 👇 关键修改 3：参数变了
async def get_current_user(token_creds: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    依赖项：
    1. 从 Header (Authorization: Bearer <token>) 拿到 Token
    2. 解密 Token
    3. 查数据库找用户
    4. 返回用户对象 (或者报错)
    """

    # 从对象中提取出纯字符串 Token
    token = token_creds.credentials

    # 定义通用的 401 错误响应
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # A. 解密 Token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # B. 提取 User ID (我们在 security.py 里把 ID 存进了 'sub' 字段)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        token_data = TokenPayload(sub=user_id_str)

    except (JWTError, ValidationError):
        # 如果 Token 格式不对、签名不对、或者过期
        raise credentials_exception

    # C. 查数据库
    async with AsyncSessionLocal() as db:
        # 注意：user_id 在 token 里是字符串，查询时最好转回 UUID
        try:
            user_uuid = UUID(token_data.sub)
        except ValueError:
            raise credentials_exception

        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalars().first()

        if user is None:
            raise credentials_exception

        # D. (可选) 检查用户是否被封号
        if not user.is_active:
            raise HTTPException(status_code=400, detail="用户账号已停用")

        return user


async def get_db() -> AsyncSession:
    """
    数据库会话依赖
    
    用于 FastAPI 的依赖注入，自动管理数据库会话的生命周期
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()