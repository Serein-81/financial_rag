# app/schemas/user.py
"""用户个人资料管理相关的Schema模型"""
from pydantic import BaseModel, Field
from typing import Optional

class UserProfileUpdate(BaseModel):
    """用户信息更新请求模型"""
    full_name: Optional[str] = Field(None, max_length=100, description="真实姓名")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    company_name: Optional[str] = Field(None, max_length=200, description="企业名称")
    company_position: Optional[str] = Field(None, max_length=100, description="职位")