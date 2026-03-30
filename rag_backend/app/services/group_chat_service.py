"""群聊服务层"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from app.models.group_chat import ChatGroup, GroupMember, GroupInvitation, GroupMessage
from app.models.group_chat import GroupMemberStatus, GroupRole
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


class GroupChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis: Optional[RedisService] = None
    
    def set_redis(self, redis_service: RedisService):
        self.redis = redis_service
    
    async def create_group(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        description: Optional[str] = None
    ) -> ChatGroup:
        group = ChatGroup(
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by=user_id
        )
        
        self.db.add(group)
        await self.db.flush()
        
        member = GroupMember(
            group_id=group.id,
            user_id=user_id,
            tenant_id=tenant_id,
            role=GroupRole.OWNER.value,
            status=GroupMemberStatus.ACTIVE.value
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(group)
        
        logger.info(f"Created group {group.id} by user {user_id}")
        return group
    
    async def get_group(self, group_id: str) -> Optional[ChatGroup]:
        result = await self.db.execute(
            select(ChatGroup).where(ChatGroup.id == group_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_groups(
        self,
        user_id: str,
        tenant_id: str
    ) -> List[ChatGroup]:
        result = await self.db.execute(
            select(ChatGroup)
            .join(GroupMember, ChatGroup.id == GroupMember.group_id)
            .where(
                and_(
                    GroupMember.user_id == user_id,
                    GroupMember.status == GroupMemberStatus.ACTIVE.value,
                    ChatGroup.status == "active"
                )
            )
            .order_by(GroupMember.joined_at.desc())
        )
        return list(result.scalars().all())
    
    async def is_group_member(
        self,
        group_id: str,
        user_id: str
    ) -> bool:
        result = await self.db.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                    GroupMember.status == GroupMemberStatus.ACTIVE.value
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def get_member_role(
        self,
        group_id: str,
        user_id: str
    ) -> Optional[str]:
        result = await self.db.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                    GroupMember.status == GroupMemberStatus.ACTIVE.value
                )
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member else None
    
    async def can_invite(
        self,
        group_id: str,
        user_id: str
    ) -> bool:
        role = await self.get_member_role(group_id, user_id)
        return role in [GroupRole.OWNER.value, GroupRole.ADMIN.value]
    
    async def invite_members(
        self,
        group_id: str,
        inviter_id: str,
        tenant_id: str,
        invitee_ids: List[str],
        message: Optional[str] = None
    ) -> List[GroupInvitation]:
        group = await self.get_group(group_id)
        if not group:
            raise ValueError("群组不存在")
        
        invitations = []
        
        for invitee_id in invitee_ids:
            existing = await self.db.execute(
                select(GroupMember).where(
                    and_(
                        GroupMember.group_id == group_id,
                        GroupMember.user_id == invitee_id,
                        GroupMember.status == GroupMemberStatus.ACTIVE.value
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                continue
            
            pending = await self.db.execute(
                select(GroupInvitation).where(
                    and_(
                        GroupInvitation.group_id == group_id,
                        GroupInvitation.invitee_id == invitee_id,
                        GroupInvitation.status == "pending"
                    )
                )
            )
            
            if pending.scalar_one_or_none():
                continue
            
            invitation = GroupInvitation(
                group_id=group_id,
                invitee_id=invitee_id,
                inviter_id=inviter_id,
                tenant_id=tenant_id,
                message=message,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            self.db.add(invitation)
            invitations.append(invitation)
            
            await self._send_invitation_notification(
                invitee_id,
                group_id,
                group.name,
                inviter_id,
                message,
                invitation.id
            )
        
        await self.db.commit()
        logger.info(f"Created {len(invitations)} invitations for group {group_id}")
        return invitations
    
    async def _send_invitation_notification(
        self,
        user_id: str,
        group_id: str,
        group_name: str,
        inviter_id: str,
        message: Optional[str],
        invitation_id: str
    ):
        if self.redis:
            notification = {
                "type": "invitation_received",
                "group_id": group_id,
                "group_name": group_name,
                "inviter_id": inviter_id,
                "message": message,
                "invitation_id": invitation_id
            }
            
            key = f"notification:user:{user_id}"
            await self.redis.redis_client.lpush(
                key,
                json.dumps({
                    **notification,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
            await self.redis.redis_client.expire(key, 604800)
    
    async def get_pending_invitations(
        self,
        user_id: str,
        tenant_id: str
    ) -> List[dict]:
        result = await self.db.execute(
            select(GroupInvitation, ChatGroup.name)
            .join(ChatGroup, GroupInvitation.group_id == ChatGroup.id)
            .where(
                and_(
                    GroupInvitation.invitee_id == user_id,
                    GroupInvitation.tenant_id == tenant_id,
                    GroupInvitation.status == "pending"
                )
            )
            .order_by(GroupInvitation.created_at.desc())
        )
        
        return [
            {
                "invitation_id": inv.id,
                "group_id": inv.group_id,
                "group_name": name,
                "inviter_id": inv.inviter_id,
                "message": inv.message,
                "created_at": inv.created_at.isoformat()
            }
            for inv, name in result.all()
        ]
    
    async def accept_invitation(
        self,
        invitation_id: str,
        user_id: str
    ) -> GroupMember:
        invitation = await self.db.get(GroupInvitation, invitation_id)
        
        if not invitation or invitation.invitee_id != user_id:
            raise ValueError("邀请不存在")
        
        if invitation.status != "pending":
            raise ValueError("邀请已处理")
        
        if invitation.expires_at and invitation.expires_at < datetime.utcnow():
            invitation.status = "expired"
            await self.db.commit()
            raise ValueError("邀请已过期")
        
        invitation.status = "accepted"
        invitation.responded_at = datetime.utcnow()
        
        member = GroupMember(
            group_id=invitation.group_id,
            user_id=user_id,
            tenant_id=invitation.tenant_id,
            role=GroupRole.MEMBER.value,
            status=GroupMemberStatus.ACTIVE.value,
            invited_by=invitation.inviter_id
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        
        logger.info(f"User {user_id} accepted invitation {invitation_id}")
        return member
    
    async def decline_invitation(
        self,
        invitation_id: str,
        user_id: str
    ) -> None:
        invitation = await self.db.get(GroupInvitation, invitation_id)
        
        if not invitation or invitation.invitee_id != user_id:
            raise ValueError("邀请不存在")
        
        if invitation.status != "pending":
            raise ValueError("邀请已处理")
        
        invitation.status = "declined"
        invitation.responded_at = datetime.utcnow()
        await self.db.commit()
        
        logger.info(f"User {user_id} declined invitation {invitation_id}")
    
    async def send_message(
        self,
        group_id: str,
        sender_id: str,
        tenant_id: str,
        content: str,
        content_type: str = "text"
    ) -> GroupMessage:
        if not await self.is_group_member(group_id, sender_id):
            raise ValueError("不是群组成员")
        
        message = GroupMessage(
            group_id=group_id,
            sender_id=sender_id,
            tenant_id=tenant_id,
            content=content,
            content_type=content_type
        )
        
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        
        logger.debug(f"User {sender_id} sent message {message.id} to group {group_id}")
        return message
    
    async def get_group_messages(
        self,
        group_id: str,
        limit: int = 50,
        before: Optional[datetime] = None
    ) -> List[GroupMessage]:
        query = select(GroupMessage).where(
            and_(
                GroupMessage.group_id == group_id,
                GroupMessage.is_deleted == False
            )
        )
        
        if before:
            query = query.where(GroupMessage.created_at < before)
        
        query = query.order_by(GroupMessage.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        return list(reversed(messages))
    
    async def get_group_members(
        self,
        group_id: str
    ) -> List[GroupMember]:
        result = await self.db.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id == group_id,
                    GroupMember.status == GroupMemberStatus.ACTIVE.value
                )
            )
        )
        return list(result.scalars().all())
    
    async def leave_group(
        self,
        group_id: str,
        user_id: str
    ) -> None:
        result = await self.db.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id
                )
            )
        )
        
        member = result.scalar_one_or_none()
        
        if not member:
            raise ValueError("不是群组成员")
        
        if member.role == GroupRole.OWNER.value:
            raise ValueError("群主不能离开群组，请先转让群主权限或解散群组")
        
        member.status = GroupMemberStatus.LEFT.value
        member.left_at = datetime.utcnow()
        await self.db.commit()
        
        logger.info(f"User {user_id} left group {group_id}")
    
    async def get_online_members(self, group_id: str) -> List[str]:
        if self.redis:
            key = f"group:online:{group_id}"
            members = await self.redis.redis_client.smembers(key)
            return list(members)
        return []
    
    async def set_member_online(self, group_id: str, user_id: str):
        if self.redis:
            key = f"group:online:{group_id}"
            await self.redis.redis_client.sadd(key, user_id)
            await self.redis.redis_client.expire(key, 3600)
    
    async def set_member_offline(self, group_id: str, user_id: str):
        if self.redis:
            key = f"group:online:{group_id}"
            await self.redis.redis_client.srem(key, user_id)


class GroupChatWebSocketManager:
    def __init__(self, redis_service: Optional[RedisService] = None):
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.redis = redis_service
    
    async def connect_group(
        self,
        group_id: str,
        user_id: str,
        websocket: Any
    ):
        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}
        
        self.active_connections[group_id][user_id] = websocket
        
        if self.redis:
            await self.redis.redis_client.sadd(f"group:online:{group_id}", user_id)
            await self.redis.redis_client.expire(f"group:online:{group_id}", 3600)
    
    async def disconnect_group(self, group_id: str, user_id: str):
        if group_id in self.active_connections:
            self.active_connections[group_id].pop(user_id, None)
            if not self.active_connections[group_id]:
                del self.active_connections[group_id]
        
        if self.redis:
            await self.redis.redis_client.srem(f"group:online:{group_id}", user_id)
    
    async def broadcast_to_group(
        self,
        group_id: str,
        message: dict,
        exclude_user: Optional[str] = None
    ):
        if group_id in self.active_connections:
            disconnected = []
            
            for uid, ws in self.active_connections[group_id].items():
                if exclude_user and uid == exclude_user:
                    continue
                    
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(uid)
            
            for uid in disconnected:
                await self.disconnect_group(group_id, uid)
        
        if self.redis:
            await self.redis.redis_client.publish(
                f"group:chat:{group_id}",
                json.dumps(message)
            )
    
    async def send_personal_notification(
        self,
        user_id: str,
        message: dict
    ):
        if self.redis:
            notification_key = f"notification:user:{user_id}"
            await self.redis.redis_client.lpush(
                notification_key,
                json.dumps({
                    **message,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
            await self.redis.redis_client.expire(notification_key, 604800)


group_chat_ws_manager = GroupChatWebSocketManager()


def get_group_chat_service(db: AsyncSession) -> GroupChatService:
    return GroupChatService(db)
