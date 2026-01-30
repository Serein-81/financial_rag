from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.future import select
from pydantic import ValidationError
from uuid import UUID

from app.core.config import settings
from app.db import AsyncSessionLocal
from app.models.user import User
from app.schemas.auth import TokenPayload

# 1. 定义 Token 获取路径
# 这告诉 FastAPI：如果用户没登录，Swagger UI 应该跳转到哪个接口去获取 Token
# 这里的路径必须对应我们下一个要写的 login 接口路径
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


# 2. 核心依赖：获取当前用户
async def get_current_user(token: str = Depends(reusable_oauth2)) -> User:
    """
    依赖项：
    1. 从 Header 拿到 Token
    2. 解密 Token
    3. 查数据库找用户
    4. 返回用户对象 (或者报错)
    """

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