from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid
from datetime import datetime
from enum import Enum


class GroupMemberStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"


class GroupRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ChatGroup(Base):
    __tablename__ = "chat_groups"
    
    id = Column(String, primary_key=True, default=lambda: f"grp_{uuid.uuid4().hex}")
    tenant_id = Column(String, nullable=False, index=True)
    
    name = Column(String, nullable=False)
    description = Column(String)
    avatar_url = Column(String, nullable=True)
    
    status = Column(String, default="active")
    created_by = Column(String, nullable=False)
    
    # 使用 JSONB 提升查询性能
    settings = Column(JSONB, default=lambda: {
        "allow_member_invite": True,
        "require_approval": False,
        "max_members": 100
    })
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)
    
    members = relationship("GroupMember", back_populates="group", lazy="dynamic")
    messages = relationship("GroupMessage", back_populates="group", lazy="dynamic")
    invitations = relationship("GroupInvitation", back_populates="group", lazy="dynamic")
    
    def __repr__(self):
        return f"<ChatGroup(id={self.id}, name={self.name})>"


class GroupMember(Base):
    __tablename__ = "group_members"
    
    id = Column(String, primary_key=True, default=lambda: f"gmem_{uuid.uuid4().hex}")
    group_id = Column(String, ForeignKey("chat_groups.id"), nullable=False)
    
    user_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    
    role = Column(String, default=GroupRole.MEMBER.value)
    status = Column(String, default=GroupMemberStatus.ACTIVE.value)
    
    invited_by = Column(String, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)
    
    # 使用 JSONB 提升查询性能
    notification_settings = Column(JSONB, default=lambda: {
        "all_messages": True,
        "mentions_only": False
    })
    
    group = relationship("ChatGroup", back_populates="members")
    
    def __repr__(self):
        return f"<GroupMember(id={self.id}, user_id={self.user_id}, group_id={self.group_id})>"


class GroupInvitation(Base):
    __tablename__ = "group_invitations"
    
    id = Column(String, primary_key=True, default=lambda: f"ginv_{uuid.uuid4().hex}")
    group_id = Column(String, ForeignKey("chat_groups.id"), nullable=False)
    
    invitee_id = Column(String, nullable=False)
    inviter_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    
    status = Column(String, default="pending")
    message = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    
    group = relationship("ChatGroup", back_populates="invitations")
    
    def __repr__(self):
        return f"<GroupInvitation(id={self.id}, invitee_id={self.invitee_id}, status={self.status})>"


class GroupMessage(Base):
    __tablename__ = "group_messages"
    
    id = Column(String, primary_key=True, default=lambda: f"gmsg_{uuid.uuid4().hex}")
    group_id = Column(String, ForeignKey("chat_groups.id"), nullable=False)
    
    sender_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    
    content = Column(Text, nullable=False)
    content_type = Column(String, default="text")
    
    # 注意：由于 SQLAlchemy 保留字限制，字段名为 extra_metadata 但映射到数据库的 metadata 列
    extra_metadata = Column("metadata", JSON, default=dict)
    
    is_deleted = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("ChatGroup", back_populates="messages")
    
    def __repr__(self):
        return f"<GroupMessage(id={self.id}, sender_id={self.sender_id})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "sender_id": self.sender_id,
            "tenant_id": self.tenant_id,
            "content": self.content,
            "content_type": self.content_type,
            "metadata": self.extra_metadata,  # 映射到 extra_metadata 属性
            "is_deleted": self.is_deleted,
            "is_edited": self.is_edited,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "created_at": self.created_at.isoformat()
        }


class MessageReadReceipt(Base):
    __tablename__ = "message_read_receipts"
    
    id = Column(String, primary_key=True, default=lambda: f"mrr_{uuid.uuid4().hex}")
    message_id = Column(String, ForeignKey("group_messages.id"), nullable=False)
    user_id = Column(String, nullable=False)
    group_id = Column(String, nullable=False)
    
    read_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    
    def __repr__(self):
        return f"<MessageReadReceipt(message_id={self.message_id}, user_id={self.user_id})>"
