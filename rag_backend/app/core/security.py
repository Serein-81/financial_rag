# app/core/security.py
import uuid
from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError, InvalidHashError
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    TokenExpiredException,
    TokenInvalidException,
    TokenRevokedException
)

# 密码加密上下文 (使用 bcrypt 算法)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码和数据库里的哈希是否匹配
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        print(f"[PASSWORD ERROR] 未知的哈希格式: {hashed_password[:20]}...", flush=True)
        return False
    except InvalidHashError:
        print(f"[PASSWORD ERROR] 无效的哈希格式: {hashed_password[:20]}...", flush=True)
        return False
    except (ValueError, KeyError) as e:
        print(f"[PASSWORD ERROR] 密码验证数据错误: {e}", flush=True)
        return False
    except (OSError, IOError) as e:
        print(f"[PASSWORD ERROR] 密码验证IO错误: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[PASSWORD ERROR] 密码验证失败: {e}", flush=True)
        return False


def get_password_hash(password: str) -> str:
    """
    将明文密码转换为哈希字符串
    """
    try:
        return pwd_context.hash(password)
    except (ValueError, KeyError) as e:
        print(f"[PASSWORD ERROR] 密码哈希生成数据错误: {e}", flush=True)
        raise AuthenticationException(
            message=f"密码哈希生成数据错误: {str(e)}",
            details={"error_type": "data_error", "original_error": str(e)}
        )
    except (OSError, IOError) as e:
        print(f"[PASSWORD ERROR] 密码哈希生成IO错误: {e}", flush=True)
        raise AuthenticationException(
            message=f"密码哈希生成IO错误: {str(e)}",
            details={"error_type": "io_error", "original_error": str(e)}
        )
    except Exception as e:
        print(f"[PASSWORD ERROR] 密码哈希生成失败: {e}", flush=True)
        raise AuthenticationException(
            message=f"密码哈希生成失败: {str(e)}",
            code="PASSWORD_HASH_ERROR"
        )


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None, tenant_id: str = None, include_jti: bool = True) -> str:
    """
    生成 JWT 访问令牌
    
    :param subject: 用户ID或其他标识符
    :param expires_delta: 过期时间，如果不传则使用配置文件的默认值
    :param tenant_id: 租户ID（可选）
    :param include_jti: 是否包含 JWT ID（用于黑名单追踪）
    :return: JWT token 字符串
    """
    to_encode = {"sub": str(subject)}
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    
    if tenant_id:
        to_encode["tenant_id"] = tenant_id
    
    if include_jti:
        jti = str(uuid.uuid4())
        to_encode["jti"] = jti

    # 使用配置中的 SECRET_KEY 和 ALGORITHM 进行签名
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any], expires_delta: timedelta = None, tenant_id: str = None) -> str:
    """
    生成 JWT 刷新令牌（默认有效期7天）
    
    :param subject: 用户ID或其他标识符
    :param expires_delta: 过期时间，默认7天
    :param tenant_id: 租户ID（可选）
    :return: JWT refresh token 字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(days=7)
    
    return create_access_token(subject, expires_delta, tenant_id, include_jti=True)


def revoke_token(token: str) -> bool:
    """
    撤销 Token（添加到黑名单）
    
    :param token: JWT token 字符串
    :return: 是否撤销成功
    """
    from app.services.token_blacklist_service import token_blacklist_service
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False})
        jti = payload.get("jti")
        
        if not jti:
            print("[JWT WARN] Token 没有 JTI，无法撤销", flush=True)
            return False
        
        exp = payload.get("exp", 0)
        now = datetime.utcnow().timestamp()
        remaining_seconds = max(int(exp - now), 0)
        
        if remaining_seconds <= 0:
            print("[JWT WARN] Token 已过期，无需撤销", flush=True)
            return True
        
        return token_blacklist_service.add_to_blacklist(jti, remaining_seconds)
        
    except jwt.JWTError as e:
        print(f"[JWT ERROR] 撤销Token失败: {e}", flush=True)
        return False
    except (ValueError, KeyError) as e:
        print(f"[JWT ERROR] 撤销Token数据错误: {e}", flush=True)
        return False
    except (OSError, IOError) as e:
        print(f"[JWT ERROR] 撤销Token IO错误: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[JWT ERROR] 撤销Token异常: {e}", flush=True)
        return False


def decode_access_token(token: str, check_blacklist: bool = True) -> dict:
    """
    解码 JWT 访问令牌
    
    :param token: JWT token 字符串
    :param check_blacklist: 是否检查黑名单
    :return: 解码后的 payload 字典
    :raises TokenExpiredException: Token已过期
    :raises TokenInvalidException: Token无效
    :raises TokenRevokedException: Token已被撤销
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        if check_blacklist:
            from app.services.token_blacklist_service import token_blacklist_service
            jti = payload.get("jti")
            if jti and token_blacklist_service.is_blacklisted(jti):
                raise TokenRevokedException(
                    message="Token已被撤销",
                    code="TOKEN_REVOKED",
                    details={"jti": jti[:16] + "..."}
                )
        
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException(
            message="Token已过期",
            code="TOKEN_EXPIRED"
        )
    except jwt.JWTClaimsError as e:
        raise TokenInvalidException(
            message=f"Token claims错误: {str(e)}",
            code="TOKEN_CLAIMS_ERROR"
        )
    except jwt.JWTError as e:
        raise TokenInvalidException(
            message=f"Token解码错误: {str(e)}",
            code="TOKEN_DECODE_ERROR",
            details={"token_preview": token[:50] if token else None}
        )
    except (ValueError, KeyError) as e:
        raise TokenInvalidException(
            message=f"Token验证数据错误: {str(e)}",
            details={"error_type": "data_error", "original_error": str(e)}
        )
    except (OSError, IOError) as e:
        raise TokenInvalidException(
            message=f"Token验证IO错误: {str(e)}",
            details={"error_type": "io_error", "original_error": str(e)}
        )
    except Exception as e:
        raise TokenInvalidException(
            message=f"Token验证失败: {str(e)}",
            code="TOKEN_VALIDATION_ERROR"
        )


def verify_token(token: str, check_blacklist: bool = True) -> dict:
    """
    验证 JWT token 并返回 payload
    
    :param token: JWT token 字符串
    :param check_blacklist: 是否检查黑名单
    :return: 解码后的 payload 字典
    :raises TokenExpiredException: Token已过期
    :raises TokenInvalidException: Token无效
    :raises TokenRevokedException: Token已被撤销
    """
    return decode_access_token(token, check_blacklist)