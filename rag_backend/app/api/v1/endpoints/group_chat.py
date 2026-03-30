"""群聊 API 端点"""
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import json
import logging

from app.api.deps import get_current_user, get_db, User
from app.services.group_chat_service import (
    GroupChatService,
    group_chat_ws_manager,
    get_group_chat_service
)
from app.services.redis_service import get_redis_service, RedisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/groups", tags=["群聊"])


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)


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

    class Config:
        from_attributes = True


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
    role: str
    status: str
    joined_at: datetime
    notification_settings: Optional[dict] = None

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    content_type: str = Field(default="text")


class MessageResponse(BaseModel):
    id: str
    group_id: str
    sender_id: str
    tenant_id: str
    content: str
    content_type: str
    metadata: Optional[dict]
    is_deleted: bool
    is_edited: bool
    edited_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[GroupResponse])
async def list_user_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[GroupResponse]:
    service = get_group_chat_service(db)
    groups = await service.get_user_groups(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )
    
    response = []
    for group in groups:
        members = await service.get_group_members(group.id)
        response.append(GroupResponse(
            id=group.id,
            tenant_id=group.tenant_id,
            name=group.name,
            description=group.description,
            avatar_url=group.avatar_url,
            status=group.status,
            created_by=group.created_by,
            created_at=group.created_at,
            member_count=len(members)
        ))
    
    return response


@router.post("/", response_model=GroupResponse)
async def create_group(
    request: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> GroupResponse:
    service = get_group_chat_service(db)
    
    group = await service.create_group(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description
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
    
    if not await service.is_group_member(group_id, current_user.id):
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
    redis = await get_redis_service()
    service.set_redis(redis)
    
    if not await service.is_group_member(group_id, current_user.id):
        raise HTTPException(status_code=403, detail="不是群组成员")
    
    if not await service.can_invite(group_id, current_user.id):
        raise HTTPException(status_code=403, detail="没有邀请权限")
    
    try:
        invitations = await service.invite_members(
            group_id=group_id,
            inviter_id=current_user.id,
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
    
    if not await service.is_group_member(group_id, current_user.id):
        raise HTTPException(status_code=403, detail="不是群组成员")
    
    members = await service.get_group_members(group_id)
    online_members = await service.get_online_members(group_id)
    
    return [
        MemberResponse(
            user_id=m.user_id,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
            notification_settings=m.notification_settings
        )
        for m in members
    ]


@router.post("/{group_id}/leave")
async def leave_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = get_group_chat_service(db)
    
    try:
        await service.leave_group(group_id, current_user.id)
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
    
    if not await service.is_group_member(group_id, current_user.id):
        raise HTTPException(status_code=403, detail="不是群组成员")
    
    before_dt = None
    if before:
        try:
            before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的时间格式")
    
    messages = await service.get_group_messages(group_id, limit, before_dt)
    
    return [
        MessageResponse(
            id=m.id,
            group_id=m.group_id,
            sender_id=m.sender_id,
            tenant_id=m.tenant_id,
            content=m.content,
            content_type=m.content_type,
            metadata=m.metadata_,
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
    
    try:
        message = await service.send_message(
            group_id=group_id,
            sender_id=current_user.id,
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
            metadata=message.metadata_,
            is_deleted=message.is_deleted,
            is_edited=message.is_edited,
            edited_at=message.edited_at,
            created_at=message.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


invitation_router = APIRouter(prefix="/invitations", tags=["群聊邀请"])


@invitation_router.get("/pending", response_model=List[InvitationResponse])
async def get_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[InvitationResponse]:
    service = get_group_chat_service(db)
    invitations = await service.get_pending_invitations(
        user_id=current_user.id,
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
    
    try:
        member = await service.accept_invitation(invitation_id, current_user.id)
        
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
            exclude_user=current_user.id
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
    
    try:
        await service.decline_invitation(invitation_id, current_user.id)
        return {"message": "已拒绝邀请"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


notification_router = APIRouter(prefix="/notifications", tags=["通知"])


@notification_router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    key = f"notification:user:{current_user.id}"
    notifications = await redis.redis_client.lrange(key, 0, 19)
    
    return {
        "notifications": [json.loads(n) for n in notifications]
    }


@notification_router.delete("/")
async def clear_notifications(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    key = f"notification:user:{current_user.id}"
    await redis.redis_client.delete(key)
    return {"message": "通知已清除"}


@notification_router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    key = f"notification:user:{current_user.id}"
    notifications = await redis.redis_client.lrange(key, 0, -1)
    
    for i, notif_json in enumerate(notifications):
        notif = json.loads(notif_json)
        if notif.get("id") == notification_id:
            await redis.redis_client.lrem(key, 1, notif_json)
            return {"message": "通知已删除"}
    
    return {"error": "通知不存在"}, 404


@notification_router.post("/delete-batch")
async def delete_notifications_batch(
    notification_ids: List[str],
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service)
):
    key = f"notification:user:{current_user.id}"
    notifications = await redis.redis_client.lrange(key, 0, -1)
    deleted_count = 0
    
    for notif_json in notifications:
        notif = json.loads(notif_json)
        if notif.get("id") in notification_ids:
            await redis.redis_client.lrem(key, 1, notif_json)
            deleted_count += 1
    
    return {"message": f"已删除 {deleted_count} 条通知", "deleted_count": deleted_count}


ws_router = APIRouter(prefix="/ws/groups", tags=["群聊 WebSocket"])


@ws_router.websocket("/{group_id}")
async def group_websocket(
    websocket: WebSocket,
    group_id: str,
    token: str = Query(...)
):
    await websocket.accept()
    
    user_id = None
    try:
        from app.services.auth_service import AuthService
        payload = AuthService.verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        service = GroupChatService(db_session)
        db_session = await get_db().__anext__()
        
        if not await service.is_group_member(group_id, user_id):
            await websocket.close(code=4003, reason="Not a group member")
            return
        
        redis = await get_redis_service()
        service.set_redis(redis)
        
        await group_chat_ws_manager.connect_group(group_id, user_id, websocket)
        
        await websocket.send_json({
            "event": "connected",
            "data": {"group_id": group_id}
        })
        
        members = await service.get_group_members(group_id)
        online_members = await service.get_online_members(group_id)
        
        await websocket.send_json({
            "event": "members_sync",
            "data": {
                "members": [
                    {"user_id": m.user_id, "role": m.role}
                    for m in members
                ],
                "online": list(online_members)
            }
        })
        
        while True:
            try:
                data = await websocket.receive_json()
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
                
                elif event == "ping":
                    await websocket.send_json({"event": "pong"})
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    
    finally:
        if user_id:
            await group_chat_ws_manager.disconnect_group(group_id, user_id)
            
            service = GroupChatService(db_session)
            redis = await get_redis_service()
            service.set_redis(redis)
            
            online_members = await service.get_online_members(group_id)
            
            await group_chat_ws_manager.broadcast_to_group(
                group_id,
                {
                    "event": "member_offline",
                    "data": {"user_id": user_id}
                }
            )
