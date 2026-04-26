"""群聊 API 端点"""
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
from app.utils.json_compat import json
import logging

from app.api.deps import get_current_user, get_db, User
from app.models.user import User as UserModel
from app.services.group_chat_service import (
    GroupChatService,
    group_chat_ws_manager,
    get_group_chat_service
)
from app.services.redis_service import get_redis_service, RedisService
from app.models.group_chat import GroupInvitation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["群聊"])


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    avatar_url: Optional[str] = Field(None, max_length=500)


class MessageResponse(BaseModel):
    id: str
    group_id: str
    sender_id: str
    tenant_id: str
    content: str
    content_type: str
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None
    metadata: Optional[dict]
    is_deleted: bool
    is_edited: bool
    edited_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
    
    @field_serializer('created_at', 'edited_at')
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        return v.isoformat()


class GroupResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    avatar_url: Optional[str]
    status: str
    created_by: str
    created_at: datetime
    member_count: int = 0
    last_message: Optional[MessageResponse] = None

    class Config:
        from_attributes = True
    
    @field_serializer('created_at')
    def serialize_datetime(self, v: datetime) -> str:
        return v.isoformat()


class InviteMemberRequest(BaseModel):
    user_ids: List[str] = Field(..., min_length=1, max_length=20)
    message: Optional[str] = Field(None, max_length=200)


class InvitationResponse(BaseModel):
    invitation_id: str
    group_id: str
    group_name: str
    inviter_id: str
    message: Optional[str]
    created_at: str


class MemberResponse(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    status: str
    joined_at: datetime
    notification_settings: Optional[dict] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True
    
    @field_serializer('joined_at', 'last_seen')
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        return v.isoformat()


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    content_type: str = Field(default="text")


@router.get("/", response_model=List[GroupResponse])
async def list_user_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[GroupResponse]:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    groups = await service.get_user_groups(
        user_id=user_id_str,
        tenant_id=current_user.tenant_id
    )
    
    response = []
    for group in groups:
        members = await service.get_group_members(group.id)
        last_msg = await service.get_last_message(group.id)
        
        last_message_resp = None
        if last_msg:
            sender_result = await db.execute(
                select(UserModel.full_name, UserModel.avatar_url)
                .where(cast(UserModel.id, String) == str(last_msg.sender_id))
            )
            sender_row = sender_result.first()
            sender_name = sender_row[0] if sender_row else None
            sender_avatar = sender_row[1] if sender_row else None
            
            last_message_resp = MessageResponse(
                id=last_msg.id,
                group_id=last_msg.group_id,
                sender_id=last_msg.sender_id,
                tenant_id=last_msg.tenant_id,
                content=last_msg.content,
                content_type=last_msg.content_type,
                sender_name=sender_name,
                sender_avatar=sender_avatar,
                metadata=last_msg.extra_metadata,
                is_deleted=last_msg.is_deleted,
                is_edited=last_msg.is_edited,
                edited_at=last_msg.edited_at,
                created_at=last_msg.created_at
            )
        
        response.append(GroupResponse(
            id=group.id,
            tenant_id=group.tenant_id,
            name=group.name,
            description=group.description,
            avatar_url=group.avatar_url,
            status=group.status,
            created_by=group.created_by,
            created_at=group.created_at,
            member_count=len(members),
            last_message=last_message_resp
        ))
    
    return response


@router.post("/", response_model=GroupResponse)
async def create_group(
    request: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> GroupResponse:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    group = await service.create_group(
        tenant_id=current_user.tenant_id,
        user_id=user_id_str,
        name=request.name,
        description=request.description,
        avatar_url=request.avatar_url
    )
    
    return GroupResponse(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        description=group.description,
        avatar_url=group.avatar_url,
        status=group.status,
        created_by=group.created_by,
        created_at=group.created_at,
        member_count=1
    )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group_info(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> GroupResponse:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    if not await service.is_group_member(group_id, user_id_str):
        raise HTTPException(status_code=403, detail="不是群组成员")
    
    group = await service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    
    members = await service.get_group_members(group_id)
    online_members = await service.get_online_members(group_id)
    
    response = GroupResponse(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        description=group.description,
        avatar_url=group.avatar_url,
        status=group.status,
        created_by=group.created_by,
        created_at=group.created_at,
        member_count=len(members)
    )
    
    return response


@router.post("/{group_id}/invite", response_model=List[InvitationResponse])
async def invite_members(
    group_id: str,
    request: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[InvitationResponse]:
    service = get_group_chat_service(db)
    redis = get_redis_service()
    service.set_redis(redis)
    user_id_str = str(current_user.id)
    
    if not await service.is_group_member(group_id, user_id_str):
        raise HTTPException(status_code=403, detail="不是群组成员")
    
    if not await service.can_invite(group_id, user_id_str):
        raise HTTPException(status_code=403, detail="没有邀请权限")
    
    try:
        invitations = await service.invite_members(
            group_id=group_id,
            inviter_id=user_id_str,
            tenant_id=current_user.tenant_id,
            invitee_ids=request.user_ids,
            message=request.message
        )
        
        group = await service.get_group(group_id)
        return [
            InvitationResponse(
                invitation_id=inv.id,
                group_id=inv.group_id,
                group_name=group.name,
                inviter_id=inv.inviter_id,
                message=inv.message,
                created_at=inv.created_at.isoformat()
            )
            for inv in invitations
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}/members", response_model=List[MemberResponse])
async def list_group_members(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[MemberResponse]:
    service = get_group_chat_service(db)
    redis = get_redis_service()
    service.set_redis(redis)
    user_id_str = str(current_user.id)
    
    if not await service.is_group_member(group_id, user_id_str):
        raise HTTPException(status_code=403, detail="不是群组成员")
    
    members = await service.get_group_members(group_id)
    online_members = await service.get_online_members(group_id)
    online_set = set(online_members)
    
    member_responses = []
    for m in members:
        last_seen = await service.get_member_last_seen(group_id, m.user_id)
        user_name, avatar_url = await service.get_user_info(m.user_id)
        member_responses.append(MemberResponse(
            user_id=m.user_id,
            user_name=user_name,
            avatar_url=avatar_url,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
            notification_settings=m.notification_settings,
            is_online=m.user_id in online_set,
            last_seen=last_seen
        ))
    
    return member_responses


@router.post("/{group_id}/leave")
async def leave_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    try:
        await service.leave_group(group_id, user_id_str)
        return {"message": "已离开群组"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}/messages", response_model=List[MessageResponse])
async def get_group_messages(
    group_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[MessageResponse]:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    try:
        is_member = await service.is_group_member(group_id, user_id_str)
        if not is_member:
            raise HTTPException(status_code=403, detail="不是群组成员")
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"检查群组成员数据错误: {e}")
        raise HTTPException(status_code=400, detail=f"检查群组成员数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"检查群组成员IO错误: {e}")
        raise HTTPException(status_code=500, detail=f"检查群组成员IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking group membership: {e}")
        raise HTTPException(status_code=500, detail=f"检查群组成员失败: {str(e)}")
    
    before_dt = None
    if before:
        try:
            before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的时间格式")
    
    try:
        messages = await service.get_group_messages(group_id, limit, before_dt)
    except (ValueError, KeyError) as e:
        logger.error(f"获取消息数据错误: {e}")
        raise HTTPException(status_code=400, detail=f"获取消息数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"获取消息IO错误: {e}")
        raise HTTPException(status_code=500, detail=f"获取消息IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")
    
    sender_map = {}
    if messages:
        sender_ids = list(set(str(m.sender_id) for m in messages))
        logger.info(f"[DEBUG] sender_ids collected: {sender_ids}")
        if sender_ids:
            try:
                from sqlalchemy import select, cast, String
                for sid in sender_ids:
                    user_result = await db.execute(
                        select(User.full_name, User.avatar_url)
                        .where(cast(User.id, String) == sid)
                    )
                    user_row = user_result.first()
                    if user_row:
                        sender_map[sid] = {"name": user_row[0], "avatar": user_row[1]}
                logger.info(f"[DEBUG] sender_map built: {sender_map}")
            except (ValueError, KeyError) as e:
                logger.error(f"获取发送者信息数据错误: {e}")
                sender_map = {}
            except (OSError, IOError) as e:
                logger.error(f"获取发送者信息IO错误: {e}")
                sender_map = {}
            except (OSError, IOError) as e:
                raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
            except Exception as e:
                logger.error(f"Error fetching sender info: {e}")
                sender_map = {}
    
    return [
        MessageResponse(
            id=m.id,
            group_id=m.group_id,
            sender_id=m.sender_id,
            tenant_id=m.tenant_id,
            content=m.content,
            content_type=m.content_type,
            sender_name=sender_map.get(str(m.sender_id), {}).get("name"),
            sender_avatar=sender_map.get(str(m.sender_id), {}).get("avatar"),
            metadata=m.extra_metadata,
            is_deleted=m.is_deleted,
            is_edited=m.is_edited,
            edited_at=m.edited_at,
            created_at=m.created_at
        )
        for m in messages
    ]


@router.post("/{group_id}/messages", response_model=MessageResponse)
async def send_group_message(
    group_id: str,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    try:
        message = await service.send_message(
            group_id=group_id,
            sender_id=user_id_str,
            tenant_id=current_user.tenant_id,
            content=request.content,
            content_type=request.content_type
        )
        
        ws_message = {
            "event": "group_message",
            "data": {
                "id": message.id,
                "group_id": message.group_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "content_type": message.content_type,
                "sender_name": current_user.full_name,
                "sender_avatar": current_user.avatar_url,
                "created_at": message.created_at.isoformat()
            }
        }
        
        await group_chat_ws_manager.broadcast_to_group(group_id, ws_message)
        
        return MessageResponse(
            id=message.id,
            group_id=message.group_id,
            sender_id=message.sender_id,
            tenant_id=message.tenant_id,
            content=message.content,
            content_type=message.content_type,
            sender_name=current_user.full_name,
            sender_avatar=current_user.avatar_url,
            metadata=message.extra_metadata,
            is_deleted=message.is_deleted,
            is_edited=message.is_edited,
            edited_at=message.edited_at,
            created_at=message.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


invitation_router = APIRouter(tags=["群聊邀请"])


@invitation_router.get("/pending", response_model=List[InvitationResponse])
async def get_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[InvitationResponse]:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    invitations = await service.get_pending_invitations(
        user_id=user_id_str,
        tenant_id=current_user.tenant_id
    )
    return [InvitationResponse(**inv) for inv in invitations]


@invitation_router.get("/sent", response_model=List[InvitationResponse])
async def get_sent_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[InvitationResponse]:
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    invitations = await service.get_sent_invitations(
        inviter_id=user_id_str,
        tenant_id=current_user.tenant_id
    )
    return [InvitationResponse(**inv) for inv in invitations]


@invitation_router.post("/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    try:
        member = await service.accept_invitation(invitation_id, user_id_str)
        
        group = await service.get_group(member.group_id)
        
        notification = {
            "event": "member_joined",
            "data": {
                "group_id": member.group_id,
                "group_name": group.name if group else "",
                "user_id": member.user_id,
                "role": member.role
            }
        }
        await group_chat_ws_manager.broadcast_to_group(
            member.group_id,
            notification,
            exclude_user=user_id_str
        )
        
        return {
            "message": "已加入群组",
            "group_id": member.group_id,
            "role": member.role
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@invitation_router.post("/{invitation_id}/decline")
async def decline_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = get_group_chat_service(db)
    user_id_str = str(current_user.id)
    
    try:
        await service.decline_invitation(invitation_id, user_id_str)
        return {"message": "已拒绝邀请"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


notification_router = APIRouter(tags=["通知"])


@notification_router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    
    try:
        if redis.client:
            notifications = redis.client.lrange(key, 0, 19) or []
            if isinstance(notifications, list):
                return [json.loads(n) for n in notifications]
            else:
                logger.error(f"❌ Redis lrange 返回类型错误: {type(notifications)}, value: {notifications}")
                return []
        else:
            logger.warning("⚠️ Redis 不可用，返回空通知列表")
            return []
    except Exception as e:
        logger.error(f"❌ 获取通知失败: {e}")
        return []


@notification_router.get("/list")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    notification_type: Optional[str] = None,
    is_read: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    all_notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    
    notifications = [json.loads(n) for n in all_notifications]
    
    if notification_type:
        notifications = [n for n in notifications if n.get("type") == notification_type]
    
    if is_read is not None:
        notifications = [n for n in notifications if n.get("is_read") == is_read]
    
    total = len(notifications)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_notifications = notifications[start_idx:end_idx]
    
    return {
        "notifications": paginated_notifications,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@notification_router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    all_notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    
    count = 0
    for n in all_notifications:
        notif = json.loads(n)
        if not notif.get("is_read", False):
            count += 1
    
    return {"count": count}


@notification_router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    all_notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    
    updated_count = 0
    for notif_json in all_notifications:
        notif = json.loads(notif_json)
        if not notif.get("is_read", False):
            notif["is_read"] = True
            if redis.client:
                redis.client.lrem(key, 1, notif_json)
                redis.client.lpush(key, json.dumps(notif))
            updated_count += 1
    
    return {"message": "已全部标记为已读", "updated_count": updated_count}


@notification_router.get("/statistics")
async def get_notification_statistics(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    all_notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    
    total = len(all_notifications)
    unread = 0
    today = 0
    by_type: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    
    from datetime import datetime, timezone
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    for n in all_notifications:
        notif = json.loads(n)
        if not notif.get("is_read", False):
            unread += 1
        
        created_at = notif.get("created_at", "")
        if created_at.startswith(today_str):
            today += 1
        
        notif_type = notif.get("type", "other")
        by_type[notif_type] = by_type.get(notif_type, 0) + 1
        
        priority = notif.get("priority", "low")
        by_priority[priority] = by_priority.get(priority, 0) + 1
    
    return {
        "total": total,
        "unread": unread,
        "today": today,
        "by_type": by_type,
        "by_priority": by_priority
    }


@notification_router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    
    for notif_json in notifications:
        notif = json.loads(notif_json)
        if notif.get("id") == notification_id:
            if not notif.get("is_read", False):
                notif["is_read"] = True
                if redis.client:
                    redis.client.lrem(key, 1, notif_json)
                    redis.client.lpush(key, json.dumps(notif))
            return {"message": "已标记为已读"}
    
    raise HTTPException(status_code=404, detail="通知不存在")


@notification_router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service),
    db: AsyncSession = Depends(get_db)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    
    for notif_json in notifications:
        notif = json.loads(notif_json)
        if notif.get("id") == notification_id:
            invitation_id = notif.get("invitation_id")
            if invitation_id and notif.get("type") == "invitation":
                invitation = await db.get(GroupInvitation, invitation_id)
                if invitation and invitation.invitee_id == user_id_str and invitation.status == "pending":
                    raise HTTPException(
                        status_code=400,
                        detail="请先处理该邀请（接受或拒绝）后再删除"
                    )
            
            if redis.client:
                redis.client.lrem(key, 1, notif_json)
            return {"message": "通知已删除"}
    
    return {"error": "通知不存在"}, 404


@notification_router.post("/clear-all")
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service),
    db: AsyncSession = Depends(get_db)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    deleted_count = 0
    pending_invitations = []
    
    for notif_json in notifications:
        notif = json.loads(notif_json)
        invitation_id = notif.get("invitation_id")
        if invitation_id and notif.get("type") == "invitation":
            invitation = await db.get(GroupInvitation, invitation_id)
            if invitation and invitation.invitee_id == user_id_str and invitation.status == "pending":
                pending_invitations.append(notif)
                continue
        
        if redis.client:
            redis.client.lrem(key, 1, notif_json)
        deleted_count += 1
    
    for notif in pending_invitations:
        redis.client.lpush(key, json.dumps(notif)) if redis.client else None
    
    if pending_invitations:
        return {"message": f"已清除 {deleted_count} 条通知，{len(pending_invitations)} 条邀请通知因未处理而保留"}
    return {"message": f"已清除 {deleted_count} 条通知"}


@notification_router.post("/resend-invitation/{invitation_id}")
async def resend_invitation_notification(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service),
    db: AsyncSession = Depends(get_db)
):
    service = get_group_chat_service(db)
    service.set_redis(redis)
    
    invitation = await db.get(GroupInvitation, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")
    
    if invitation.inviter_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权限操作此邀请")
    
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="只能重新发送待处理的邀请")
    
    group = await service.get_group(invitation.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    
    await service._send_invitation_notification(
        invitation.invitee_id,
        invitation.group_id,
        group.name,
        invitation.inviter_id,
        invitation.message,
        invitation.id
    )
    
    return {"message": "邀请通知已重新发送"}


@notification_router.post("/delete-batch")
async def delete_notifications_batch(
    notification_ids: List[str],
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service),
    db: AsyncSession = Depends(get_db)
):
    user_id_str = str(current_user.id)
    key = f"notification:user:{user_id_str}"
    notifications = redis.client.lrange(key, 0, -1) if redis.client else []
    deleted_count = 0
    blocked_count = 0
    
    for notif_json in notifications:
        notif = json.loads(notif_json)
        if notif.get("id") in notification_ids:
            invitation_id = notif.get("invitation_id")
            if invitation_id and notif.get("type") == "invitation":
                invitation = await db.get(GroupInvitation, invitation_id)
                if invitation and invitation.invitee_id == user_id_str and invitation.status == "pending":
                    blocked_count += 1
                    continue
            
            if redis.client:
                redis.client.lrem(key, 1, notif_json)
            deleted_count += 1
    
    if blocked_count > 0:
        return {"message": f"已删除 {deleted_count} 条通知，{blocked_count} 条邀请通知因未处理而无法删除", "deleted_count": deleted_count, "blocked_count": blocked_count}
    return {"message": f"已删除 {deleted_count} 条通知", "deleted_count": deleted_count}


ws_router = APIRouter(tags=["群聊 WebSocket"])

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 35


@ws_router.websocket("/{group_id}")
async def group_websocket(
    websocket: WebSocket,
    group_id: str,
    token: str = Query(...)
):
    import asyncio
    
    await websocket.accept()
    
    user_id = None
    current_user_name = None
    current_user_avatar = None
    try:
        from app.core.security import verify_token
        from sqlalchemy import select
        from app.db.session import get_db_context
        
        payload = verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        async with get_db_context() as db_session:
            user_result = await db_session.execute(select(User).where(User.id == user_id))
            current_user_obj = user_result.scalar_one_or_none()
            if current_user_obj:
                current_user_name = current_user_obj.full_name
                current_user_avatar = current_user_obj.avatar_url
            
            service = GroupChatService(db_session)
            
            if not await service.is_group_member(group_id, user_id):
                await websocket.close(code=4003, reason="Not a group member")
                return
            
            redis = get_redis_service()
            service.set_redis(redis)
            
            await group_chat_ws_manager.connect_group(group_id, user_id, websocket)
            
            await service.set_member_online(group_id, user_id, {"device": "web"})
            
            await websocket.send_json({
                "event": "connected",
                "data": {"group_id": group_id, "heartbeat_interval": HEARTBEAT_INTERVAL}
            })
            
            members = await service.get_group_members(group_id)
            online_members = await service.get_online_members(group_id)
            
            members_with_info = []
            for m in members:
                user_name, avatar_url = await service.get_user_info(m.user_id)
                members_with_info.append({
                    "id": m.id,
                    "user_id": m.user_id,
                    "user_name": user_name,
                    "avatar_url": avatar_url,
                    "role": m.role
                })
            
            await websocket.send_json({
                "event": "members_sync",
                "data": {
                    "members": members_with_info,
                    "online": list(online_members)
                }
            })
            
            await group_chat_ws_manager.broadcast_to_group(
                group_id,
                {
                    "event": "member_online",
                    "data": {
                        "user_id": user_id,
                        "user_name": current_user_name,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                exclude_user=user_id
            )
            
            last_pong_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_json(),
                            timeout=HEARTBEAT_TIMEOUT
                        )
                        last_pong_time = asyncio.get_event_loop().time()
                        event = data.get("event")
                        
                        if event == "message":
                            content = data.get("data", {}).get("content", "")
                            if content:
                                message = await service.send_message(
                                    group_id=group_id,
                                    sender_id=user_id,
                                    tenant_id=db_session.get("tenant_id", ""),
                                    content=content
                                )
                                
                                await group_chat_ws_manager.broadcast_to_group(
                                    group_id,
                                    {
                                        "event": "group_message",
                                        "data": {
                                            "id": message.id,
                                            "sender_id": message.sender_id,
                                            "content": message.content,
                                            "sender_name": current_user_name,
                                            "sender_avatar": current_user_avatar,
                                            "created_at": message.created_at.isoformat()
                                        }
                                    }
                                )
                        
                        elif event == "typing":
                            await group_chat_ws_manager.broadcast_to_group(
                                group_id,
                                {
                                    "event": "user_typing",
                                    "data": {"user_id": user_id}
                                },
                                exclude_user=user_id
                            )
                        
                        elif event == "pong":
                            last_pong_time = asyncio.get_event_loop().time()
                            await group_chat_ws_manager.refresh_heartbeat(group_id, user_id)
                        
                        elif event == "ping":
                            await websocket.send_json({"event": "pong"})
                        
                        elif event == "mark_read":
                            message_ids = data.get("data", {}).get("message_ids", [])
                            if message_ids:
                                await service.mark_messages_read(group_id, user_id, message_ids)
                                await group_chat_ws_manager.broadcast_to_group(
                                    group_id,
                                    {
                                        "event": "messages_read",
                                        "data": {
                                            "user_id": user_id,
                                            "message_ids": message_ids
                                        }
                                    }
                                )
                    
                    except asyncio.TimeoutError:
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_pong_time > HEARTBEAT_TIMEOUT:
                            logger.warning(f"WebSocket heartbeat timeout for user {user_id}")
                            break
                
                except WebSocketDisconnect:
                    break
                except (ValueError, KeyError) as e:
                    logger.error(f"WebSocket数据错误: {e}")
                    break
                except (OSError, IOError) as e:
                    logger.error(f"WebSocket IO错误: {e}")
                    break
                except (ValueError, KeyError) as e:
                    raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
                except (OSError, IOError) as e:
                    raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    break
            
            if user_id:
                await group_chat_ws_manager.disconnect_group(group_id, user_id)
                
                service = GroupChatService(db_session)
                redis = get_redis_service()
                service.set_redis(redis)
                
                try:
                    await group_chat_ws_manager.broadcast_to_group(
                        group_id,
                        {
                            "event": "member_offline",
                            "data": {
                                "user_id": user_id,
                                "user_name": current_user_name,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to broadcast offline event: {e}")
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
