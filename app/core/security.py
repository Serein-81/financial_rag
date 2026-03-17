# app/core/security.py
from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

# 密码加密上下文 (使用 bcrypt 算法)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码和数据库里的哈希是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    将明文密码转换为哈希字符串
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    生成 JWT 访问令牌
    :param data: 要编码的数据字典
    :param expires_delta: 过期时间，如果不传则使用配置文件的默认值
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 添加过期时间
    to_encode.update({"exp": expire})

    # 使用配置中的 SECRET_KEY 和 ALGORITHM 进行签名
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    解码 JWT 访问令牌
    :param token: JWT token 字符串
    :return: 解码后的 payload 字典
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.JWTError:
        return None


def verify_token(token: str) -> dict:
    """
    验证 JWT token 并返回 payload
    :param token: JWT token 字符串
    :return: 解码后的 payload 字典，如果验证失败返回 None
    """
    return decode_access_token(token)