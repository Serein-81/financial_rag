"""群聊服务层"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.json_compat import json
import logging

from app.models.group_chat import ChatGroup, GroupMember, GroupInvitation, GroupMessage
from app.models.group_chat import GroupMemberStatus, GroupRole, MessageReadReceipt
from app.models.user import User
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
        description: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> ChatGroup:
        group = ChatGroup(
            tenant_id=tenant_id,
            name=name,
            description=description,
            avatar_url=avatar_url,
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
                    cast(GroupMember.user_id, String) == user_id,
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
                    cast(GroupMember.user_id, String) == user_id,
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
                    cast(GroupMember.user_id, String) == user_id,
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
                        cast(GroupMember.user_id, String) == invitee_id,
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
                        cast(GroupInvitation.invitee_id, String) == invitee_id,
                        GroupInvitation.status == "pending"
                    )
                )
            )
            
            old_invitation = pending.scalar_one_or_none()
            if old_invitation:
                old_invitation_id = old_invitation.id
                await self.db.delete(old_invitation)
                if self.redis and self.redis.client:
                    key = f"notification:user:{invitee_id}"
                    notifications = self.redis.client.lrange(key, 0, -1)
                    for notif_json in notifications:
                        notif = json.loads(notif_json)
                        if notif.get("invitation_id") == old_invitation_id:
                            self.redis.client.lrem(key, 1, notif_json)
                            break
            
            invitation = GroupInvitation(
                group_id=group_id,
                invitee_id=invitee_id,
                inviter_id=inviter_id,
                tenant_id=tenant_id,
                message=message,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            self.db.add(invitation)
            await self.db.flush()
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
            inviter_name = "未知用户"
            try:
                result = await self.db.execute(select(User).where(User.id == inviter_id))
                inviter = result.scalar_one_or_none()
                if inviter:
                    inviter_name = inviter.full_name or inviter.nickname or inviter.username or inviter.email
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to get inviter name: data error {e}")
            except (OSError, IOError) as e:
                logger.warning(f"Failed to get inviter name: IO error {e}")
            except Exception as e:
                logger.warning(f"Failed to get inviter name: {e}")
            
            notification = {
                "id": invitation_id,
                "type": "invitation",
                "title": "群聊邀请",
                "content": f"你收到了来自「{inviter_name}」的群聊「{group_name}」邀请" + (f"：{message}" if message else ""),
                "group_id": group_id,
                "group_name": group_name,
                "inviter_id": inviter_id,
                "inviter_name": inviter_name,
                "message": message,
                "invitation_id": invitation_id,
                "is_read": False
            }
            
            key = f"notification:user:{user_id}"
            self.redis.client.lpush(
                key,
                json.dumps({
                    **notification,
                    "created_at": datetime.utcnow().isoformat()
                })
            )
            self.redis.client.expire(key, 604800)
    
    async def _delete_invitation_notification(
        self,
        user_id: str,
        invitation_id: str
    ) -> bool:
        if not self.redis or not self.redis.client:
            return False
        
        try:
            key = f"notification:user:{user_id}"
            notifications = self.redis.client.lrange(key, 0, -1)
            
            for notif_json in notifications:
                notif = json.loads(notif_json)
                if notif.get("invitation_id") == invitation_id:
                    self.redis.client.lrem(key, 1, notif_json)
                    logger.info(f"Deleted notification for invitation {invitation_id}")
                    return True
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to delete invitation notification: data error {e}")
        except (OSError, IOError) as e:
            logger.warning(f"Failed to delete invitation notification: IO error {e}")
        except Exception as e:
            logger.warning(f"Failed to delete invitation notification: {e}")
        
        return False
    
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
                    cast(GroupInvitation.invitee_id, String) == user_id,
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
    
    async def get_sent_invitations(
        self,
        inviter_id: str,
        tenant_id: str
    ) -> List[dict]:
        result = await self.db.execute(
            select(GroupInvitation, ChatGroup.name, User.full_name, User.email)
            .join(ChatGroup, GroupInvitation.group_id == ChatGroup.id)
            .join(User, cast(GroupInvitation.invitee_id, String) == cast(User.id, String))
            .where(
                and_(
                    cast(GroupInvitation.inviter_id, String) == inviter_id,
                    GroupInvitation.tenant_id == tenant_id,
                    GroupInvitation.status == "pending"
                )
            )
            .order_by(GroupInvitation.created_at.desc())
        )
        
        return [
            {
                "id": inv.id,
                "group_id": inv.group_id,
                "group_name": name,
                "invitee_id": inv.invitee_id,
                "invitee_name": full_name or email,
                "message": inv.message,
                "status": inv.status,
                "created_at": inv.created_at.isoformat()
            }
            for inv, name, full_name, email in result.all()
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
        
        await self._delete_invitation_notification(user_id, invitation_id)
        
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
        
        await self._delete_invitation_notification(user_id, invitation_id)
        
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
    
    async def mark_messages_read(
        self,
        group_id: str,
        user_id: str,
        message_ids: List[str]
    ) -> List["MessageReadReceipt"]:
        if not await self.is_group_member(group_id, user_id):
            raise ValueError("不是群组成员")
        
        try:
            read_receipts = []
            for message_id in message_ids:
                existing = await self.db.execute(
                    select(MessageReadReceipt).where(
                        and_(
                            MessageReadReceipt.message_id == message_id,
                            cast(MessageReadReceipt.user_id, String) == user_id
                        )
                    )
                )
                if existing.scalar_one_or_none() is None:
                    receipt = MessageReadReceipt(
                        message_id=message_id,
                        user_id=user_id,
                        group_id=group_id
                    )
                    self.db.add(receipt)
                    read_receipts.append(receipt)
            
            await self.db.commit()
            
            for receipt in read_receipts:
                await self.db.refresh(receipt)
            
            logger.debug(f"User {user_id} marked {len(read_receipts)} messages as read in group {group_id}")
            return read_receipts
        except (ValueError, KeyError) as e:
            logger.warning(f"MessageReadReceipt table not available: data error {e}")
            return []
        except (OSError, IOError) as e:
            logger.warning(f"MessageReadReceipt table not available: IO error {e}")
            return []
        except Exception as e:
            logger.warning(f"MessageReadReceipt table not available: {e}")
            return []
    
    async def get_read_receipts(
        self,
        group_id: str,
        message_ids: List[str]
    ) -> Dict[str, List[str]]:
        try:
            result = await self.db.execute(
                select(MessageReadReceipt).where(
                    and_(
                        MessageReadReceipt.group_id == group_id,
                        MessageReadReceipt.message_id.in_(message_ids)
                    )
                )
            )
            receipts = result.scalars().all()
            
            read_by_user: Dict[str, List[str]] = {}
            for receipt in receipts:
                if receipt.message_id not in read_by_user:
                    read_by_user[receipt.message_id] = []
                read_by_user[receipt.message_id].append(receipt.user_id)
            
            return read_by_user
        except (ValueError, KeyError) as e:
            logger.warning(f"MessageReadReceipt table not available: data error {e}")
            return {}
        except (OSError, IOError) as e:
            logger.warning(f"MessageReadReceipt table not available: IO error {e}")
            return {}
        except Exception as e:
            logger.warning(f"MessageReadReceipt table not available: {e}")
            return {}
    
    async def get_group_messages(
        self,
        group_id: str,
        limit: int = 50,
        before: Optional[datetime] = None
    ) -> List[GroupMessage]:
        query = select(GroupMessage).where(
            and_(
                GroupMessage.group_id == group_id,
                GroupMessage.is_deleted.is_(False)
            )
        )
        
        if before:
            query = query.where(GroupMessage.created_at < before)
        
        query = query.order_by(GroupMessage.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        return list(reversed(messages))
    
    async def get_last_message(self, group_id: str) -> Optional[GroupMessage]:
        from sqlalchemy import desc
        result = await self.db.execute(
            select(GroupMessage)
            .where(
                and_(
                    GroupMessage.group_id == group_id,
                    GroupMessage.is_deleted.is_(False)
                )
            )
            .order_by(desc(GroupMessage.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
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
    
    async def get_user_info(self, user_id: str) -> tuple:
        try:
            result = await self.db.execute(
                select(User.full_name, User.avatar_url).where(
                    cast(User.id, String) == user_id
                )
            )
            row = result.first()
            if row:
                return (row[0], row[1])
        except (ValueError, KeyError) as e:
            logger.error(f"获取用户信息失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"获取用户信息失败: IO error {e}")
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
        return (None, None)
    
    async def leave_group(
        self,
        group_id: str,
        user_id: str
    ) -> None:
        result = await self.db.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id == group_id,
                    cast(GroupMember.user_id, String) == user_id
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
        if not self.redis or not self.redis.client:
            return []
        
        key = f"group:presence:{group_id}"
        now = datetime.utcnow().timestamp()
        online_members = []
        
        try:
            members_data = self.redis.client.hgetall(key)
            for user_id, data_str in members_data.items():
                try:
                    import json
                    data = json.loads(data_str)
                    last_heartbeat = data.get("timestamp", 0)
                    if now - last_heartbeat < 90:
                        online_members.append(user_id)
                    else:
                        self.redis.client.hdel(key, user_id)
                except (ValueError, KeyError):
                    logger.warning("获取在线成员: 数据错误")
                    continue
                except (OSError, IOError):
                    logger.warning("获取在线成员: Redis连接错误")
                    continue
                except RuntimeError as e:
                    logger.warning(f"获取在线成员: 运行时错误, {e}")
                    continue
                except Exception:
                    logger.warning("获取在线成员: 未知错误")
                    continue
        except (ValueError, KeyError) as e:
            logger.error(f"获取在线成员失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"获取在线成员失败: IO error {e}")
        except Exception as e:
            logger.error(f"获取在线成员失败: {e}")
        
        return online_members
    
    async def get_online_members_with_details(self, group_id: str) -> Dict[str, Dict[str, Any]]:
        if not self.redis or not self.redis.client:
            return {}
        
        key = f"group:presence:{group_id}"
        now = datetime.utcnow().timestamp()
        online_members = {}
        
        try:
            members_data = self.redis.client.hgetall(key)
            for user_id, data_str in members_data.items():
                try:
                    import json
                    data = json.loads(data_str)
                    last_heartbeat = data.get("timestamp", 0)
                    if now - last_heartbeat < 90:
                        online_members[user_id] = data
                    else:
                        self.redis.client.hdel(key, user_id)
                except (ValueError, KeyError):
                    logger.warning("获取在线成员详情: 数据错误")
                    continue
                except (OSError, IOError):
                    logger.warning("获取在线成员详情: Redis连接错误")
                    continue
                except RuntimeError as e:
                    logger.warning(f"获取在线成员详情: 运行时错误, {e}")
                    continue
                except Exception:
                    logger.warning("获取在线成员详情: 未知错误")
                    continue
        except (ValueError, KeyError) as e:
            logger.error(f"获取在线成员详情失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"获取在线成员详情失败: IO error {e}")
        except Exception as e:
            logger.error(f"获取在线成员详情失败: {e}")
        
        return online_members
    
    async def set_member_online(
        self,
        group_id: str,
        user_id: str,
        device_info: Optional[Dict[str, str]] = None
    ) -> bool:
        if not self.redis or not self.redis.client:
            return False
        
        key = f"group:presence:{group_id}"
        now = datetime.utcnow()
        timestamp = now.timestamp()
        
        try:
            import json
            data = {
                "timestamp": timestamp,
                "datetime": now.isoformat(),
                "device": device_info or {}
            }
            self.redis.client.hset(key, user_id, json.dumps(data))
            self.redis.client.expire(key, 86400)
            
            logger.debug(f"User {user_id} marked online in group {group_id}")
            return True
        except (ValueError, KeyError) as e:
            logger.error(f"设置用户在线状态失败: data error {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"设置用户在线状态失败: IO error {e}")
            return False
        except Exception as e:
            logger.error(f"设置用户在线状态失败: {e}")
            return False
    
    async def refresh_member_heartbeat(
        self,
        group_id: str,
        user_id: str
    ) -> bool:
        if not self.redis or not self.redis.client:
            return False
        
        key = f"group:presence:{group_id}"
        now = datetime.utcnow()
        timestamp = now.timestamp()
        
        try:
            existing = self.redis.client.hget(key, user_id)
            if existing:
                import json
                data = json.loads(existing)
                data["timestamp"] = timestamp
                data["datetime"] = now.isoformat()
                self.redis.client.hset(key, user_id, json.dumps(data))
                self.redis.client.expire(key, 86400)
                return True
        except (ValueError, KeyError) as e:
            logger.error(f"刷新心跳失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"刷新心跳失败: IO error {e}")
        except Exception as e:
            logger.error(f"刷新心跳失败: {e}")
        
        return False
    
    async def set_member_offline(self, group_id: str, user_id: str) -> bool:
        if not self.redis or not self.redis.client:
            return False
        
        key = f"group:presence:{group_id}"
        
        try:
            self.redis.client.hdel(key, user_id)
            logger.debug(f"User {user_id} marked offline in group {group_id}")
            return True
        except (ValueError, KeyError) as e:
            logger.error(f"设置用户离线状态失败: data error {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"设置用户离线状态失败: IO error {e}")
            return False
        except Exception as e:
            logger.error(f"设置用户离线状态失败: {e}")
            return False
    
    async def is_member_online(self, group_id: str, user_id: str) -> bool:
        if not self.redis or not self.redis.client:
            return False
        
        key = f"group:presence:{group_id}"
        now = datetime.utcnow().timestamp()
        
        try:
            data = self.redis.client.hget(key, user_id)
            if data:
                import json
                parsed = json.loads(data)
                last_heartbeat = parsed.get("timestamp", 0)
                return (now - last_heartbeat) < 90
        except (ValueError, KeyError) as e:
            logger.error(f"检查用户在线状态失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"检查用户在线状态失败: IO error {e}")
        except Exception as e:
            logger.error(f"检查用户在线状态失败: {e}")
        
        return False
    
    async def get_member_last_seen(
        self,
        group_id: str,
        user_id: str
    ) -> Optional[datetime]:
        if not self.redis or not self.redis.client:
            return None
        
        key = f"group:presence:{group_id}"
        
        try:
            data = self.redis.client.hget(key, user_id)
            if data:
                import json
                parsed = json.loads(data)
                return datetime.fromtimestamp(parsed.get("timestamp", 0))
        except json.JSONDecodeError as e:
            logger.error(f"获取用户最后在线时间失败: JSON解析错误 {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"获取用户最后在线时间失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"获取用户最后在线时间失败: IO error {e}")
        except Exception as e:
            logger.error(f"获取用户最后在线时间失败: {e}")
        
        return None
    
    async def cleanup_stale_online_members(self, group_id: str) -> int:
        if not self.redis or not self.redis.client:
            return 0
        
        key = f"group:presence:{group_id}"
        now = datetime.utcnow().timestamp()
        removed_count = 0
        
        try:
            members_data = self.redis.client.hgetall(key)
            for user_id, data_str in members_data.items():
                try:
                    import json
                    data = json.loads(data_str)
                    last_heartbeat = data.get("timestamp", 0)
                    if now - last_heartbeat >= 90:
                        self.redis.client.hdel(key, user_id)
                        removed_count += 1
                except (ValueError, KeyError):
                    logger.warning("清理过期成员: 数据错误")
                    continue
                except (OSError, IOError):
                    logger.warning("清理过期成员: Redis连接错误")
                    continue
                except RuntimeError as e:
                    logger.warning(f"清理过期成员: 运行时错误, {e}")
                    continue
                except Exception:
                    logger.warning("清理过期成员: 未知错误")
                    continue
        except (ValueError, KeyError) as e:
            logger.error(f"清理过期在线成员失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"清理过期在线成员失败: IO error {e}")
        except Exception as e:
            logger.error(f"清理过期在线成员失败: {e}")
        
        return removed_count


class GroupChatWebSocketManager:
    def __init__(self, redis_service: Optional[RedisService] = None):
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.redis = redis_service
    
    async def connect_group(
        self,
        group_id: str,
        user_id: str,
        websocket: Any,
        device_info: Optional[Dict[str, str]] = None
    ):
        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}
        
        self.active_connections[group_id][user_id] = websocket
        
        if self.redis and self.redis.client:
            key = f"group:presence:{group_id}"
            import json
            now = datetime.utcnow()
            data = {
                "timestamp": now.timestamp(),
                "datetime": now.isoformat(),
                "device": device_info or {}
            }
            self.redis.client.hset(key, user_id, json.dumps(data))
            self.redis.client.expire(key, 86400)
    
    async def refresh_heartbeat(self, group_id: str, user_id: str) -> bool:
        if not self.redis or not self.redis.client:
            return False
        
        key = f"group:presence:{group_id}"
        
        try:
            import json
            existing = self.redis.client.hget(key, user_id)
            if existing:
                data = json.loads(existing)
                now = datetime.utcnow()
                data["timestamp"] = now.timestamp()
                data["datetime"] = now.isoformat()
                self.redis.client.hset(key, user_id, json.dumps(data))
                self.redis.client.expire(key, 86400)
                return True
        except (ValueError, KeyError) as e:
            logger.error(f"刷新心跳失败: data error {e}")
        except (OSError, IOError) as e:
            logger.error(f"刷新心跳失败: IO error {e}")
        except Exception as e:
            logger.error(f"刷新心跳失败: {e}")
        
        return False
    
    async def disconnect_group(self, group_id: str, user_id: str):
        if group_id in self.active_connections:
            self.active_connections[group_id].pop(user_id, None)
            if not self.active_connections[group_id]:
                del self.active_connections[group_id]
        
        if self.redis and self.redis.client:
            key = f"group:presence:{group_id}"
            self.redis.client.hdel(key, user_id)
    
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
                except (ValueError, KeyError):
                    logger.warning(f"WebSocket发送失败: 数据错误, uid={uid}")
                    disconnected.append(uid)
                except (OSError, IOError):
                    logger.warning(f"WebSocket发送失败: 连接错误, uid={uid}")
                    disconnected.append(uid)
                except RuntimeError as e:
                    logger.warning(f"WebSocket发送失败: 运行时错误, uid={uid}, {e}")
                    disconnected.append(uid)
                except Exception:
                    logger.warning(f"WebSocket发送失败: 未知错误, uid={uid}")
                    disconnected.append(uid)
            
            for uid in disconnected:
                await self.disconnect_group(group_id, uid)
        
        if self.redis:
            self.redis.client.publish(
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
            self.redis.client.lpush(
                notification_key,
                json.dumps({
                    **message,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
            self.redis.client.expire(notification_key, 604800)


group_chat_ws_manager = GroupChatWebSocketManager()


def get_group_chat_service(db: AsyncSession) -> GroupChatService:
    return GroupChatService(db)
