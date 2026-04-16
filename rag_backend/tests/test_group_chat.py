"""群聊功能单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from enum import Enum
from datetime import datetime
from typing import Optional


class GroupMemberStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"


class GroupRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class GroupWSEventType(str, Enum):
    NEW_MESSAGE = "new_message"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    MEMBER_REMOVED = "member_removed"
    GROUP_UPDATED = "group_updated"
    TYPING = "typing"
    ONLINE_STATUS = "online_status"
    INVITATION_RECEIVED = "invitation_received"


class MockChatGroup:
    def __init__(
        self,
        id: str,
        tenant_id: str,
        name: str,
        created_by: str,
        description: str = "",
        avatar_url: str = None,
        status: str = "active"
    ):
        self.id = id
        self.tenant_id = tenant_id
        self.name = name
        self.description = description
        self.avatar_url = avatar_url
        self.status = status
        self.created_by = created_by
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.members = []
        self.messages = []
        self.invitations = []


class MockGroupMember:
    def __init__(
        self,
        id: str,
        group_id: str,
        user_id: str,
        tenant_id: str,
        role: GroupRole = GroupRole.MEMBER,
        status: GroupMemberStatus = GroupMemberStatus.ACTIVE
    ):
        self.id = id
        self.group_id = group_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role
        self.status = status
        self.joined_at = datetime.now()
        self.notification_settings = {"enabled": True}


class MockGroupInvitation:
    def __init__(
        self,
        id: str,
        group_id: str,
        invitee_id: str,
        inviter_id: str,
        tenant_id: str,
        status: str = "pending",
        message: str = ""
    ):
        self.id = id
        self.group_id = group_id
        self.invitee_id = invitee_id
        self.inviter_id = inviter_id
        self.tenant_id = tenant_id
        self.status = status
        self.message = message
        self.created_at = datetime.now()
        self.expires_at = None


class MockGroupMessage:
    def __init__(
        self,
        id: str,
        group_id: str,
        sender_id: str,
        tenant_id: str,
        content: str,
        content_type: str = "text"
    ):
        self.id = id
        self.group_id = group_id
        self.sender_id = sender_id
        self.tenant_id = tenant_id
        self.content = content
        self.content_type = content_type
        self.metadata_ = {}
        self.created_at = datetime.now()
        self.is_deleted = False
    
    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "sender_id": self.sender_id,
            "content": self.content,
            "content_type": self.content_type,
            "created_at": self.created_at.isoformat()
        }


class MockWebSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []
        self.closed = False
    
    async def accept(self):
        self.accepted = True
    
    async def send_json(self, data):
        self.messages.append(data)
    
    async def close(self):
        self.closed = True


class GroupChatService:
    def __init__(self):
        self.groups = {}
        self.members = {}
        self.invitations = {}
        self.messages = {}
        self.group_members = {}
        self.group_messages = {}
        self.group_invitations = {}
    
    async def create_group(self, tenant_id: str, user_id: str, name: str, description: str = "") -> MockChatGroup:
        group_id = f"group_{len(self.groups) + 1}"
        group = MockChatGroup(
            id=group_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by=user_id
        )
        self.groups[group_id] = group
        
        member_id = f"member_{group_id}_{user_id}"
        member = MockGroupMember(
            id=member_id,
            group_id=group_id,
            user_id=user_id,
            tenant_id=tenant_id,
            role=GroupRole.OWNER,
            status=GroupMemberStatus.ACTIVE
        )
        self.members[member_id] = member
        self.group_members[group_id] = [member]
        
        return group
    
    async def get_group(self, group_id: str) -> Optional[MockChatGroup]:
        return self.groups.get(group_id)
    
    async def is_group_member(self, group_id: str, user_id: str) -> bool:
        members = self.group_members.get(group_id, [])
        return any(
            m.user_id == user_id and m.status == GroupMemberStatus.ACTIVE
            for m in members
        )
    
    async def get_member_role(self, group_id: str, user_id: str) -> Optional[GroupRole]:
        members = self.group_members.get(group_id, [])
        for member in members:
            if member.user_id == user_id and member.status == GroupMemberStatus.ACTIVE:
                return member.role
        return None
    
    async def can_invite(self, group_id: str, user_id: str) -> bool:
        role = await self.get_member_role(group_id, user_id)
        if not role:
            return False
        return role in [GroupRole.OWNER, GroupRole.ADMIN]
    
    async def invite_members(
        self,
        group_id: str,
        inviter_id: str,
        tenant_id: str,
        invitee_ids: list,
        message: str = ""
    ) -> list[MockGroupInvitation]:
        invitations = []
        for invitee_id in invitee_ids:
            inv_id = f"inv_{group_id}_{invitee_id}"
            inv = MockGroupInvitation(
                id=inv_id,
                group_id=group_id,
                invitee_id=invitee_id,
                inviter_id=inviter_id,
                tenant_id=tenant_id,
                message=message
            )
            invitations.append(inv)
            self.invitations[inv_id] = inv
        
        group = self.groups.get(group_id)
        if group:
            group.invitations.extend(invitations)
        
        return invitations
    
    async def accept_invitation(self, invitation_id: str, user_id: str) -> Optional[MockGroupMember]:
        inv = self.invitations.get(invitation_id)
        if not inv or inv.status != "pending" or inv.invitee_id != user_id:
            return None
        
        inv.status = "accepted"
        
        member_id = f"member_{inv.group_id}_{user_id}"
        member = MockGroupMember(
            id=member_id,
            group_id=inv.group_id,
            user_id=user_id,
            tenant_id=inv.tenant_id,
            role=GroupRole.MEMBER,
            status=GroupMemberStatus.ACTIVE
        )
        self.members[member_id] = member
        
        if inv.group_id not in self.group_members:
            self.group_members[inv.group_id] = []
        self.group_members[inv.group_id].append(member)
        
        return member
    
    async def send_message(
        self,
        group_id: str,
        sender_id: str,
        tenant_id: str,
        content: str,
        content_type: str = "text"
    ) -> Optional[MockGroupMessage]:
        is_member = await self.is_group_member(group_id, sender_id)
        if not is_member:
            return None
        
        msg_id = f"msg_{group_id}_{len(self.group_messages.get(group_id, [])) + 1}"
        msg = MockGroupMessage(
            id=msg_id,
            group_id=group_id,
            sender_id=sender_id,
            tenant_id=tenant_id,
            content=content,
            content_type=content_type
        )
        
        self.messages[msg_id] = msg
        if group_id not in self.group_messages:
            self.group_messages[group_id] = []
        self.group_messages[group_id].append(msg)
        
        return msg
    
    async def get_group_messages(self, group_id: str, limit: int = 50, before: str = None) -> list[MockGroupMessage]:
        messages = self.group_messages.get(group_id, [])
        messages.sort(key=lambda m: m.created_at, reverse=True)
        
        if before:
            before_msg = next((m for m in messages if m.id == before), None)
            if before_msg:
                messages = [m for m in messages if m.created_at < before_msg.created_at]
        
        return messages[:limit]


class GroupChatWebSocketManager:
    def __init__(self):
        self.active_connections = {}
        self.user_groups = {}
    
    async def connect_group(self, group_id: str, user_id: str, websocket: MockWebSocket):
        await websocket.accept()
        
        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}
        self.active_connections[group_id][user_id] = websocket
        
        if user_id not in self.user_groups:
            self.user_groups[user_id] = set()
        self.user_groups[user_id].add(group_id)
    
    async def disconnect_group(self, group_id: str, user_id: str):
        if group_id in self.active_connections:
            self.active_connections[group_id].pop(user_id, None)
        
        if user_id in self.user_groups:
            self.user_groups[user_id].discard(group_id)
    
    async def broadcast_to_group(self, group_id: str, message: dict, exclude_user: str = None):
        if group_id not in self.active_connections:
            return
        
        for user_id, ws in self.active_connections[group_id].items():
            if exclude_user and user_id == exclude_user:
                continue
            await ws.send_json(message)
    
    async def send_personal_notification(self, user_id: str, message: dict):
        if user_id in self.user_groups:
            for group_id in self.user_groups[user_id]:
                if group_id in self.active_connections:
                    for ws in self.active_connections[group_id].values():
                        await ws.send_json(message)


class TestGroupMemberStatus:
    
    def test_invited_status(self):
        assert GroupMemberStatus.INVITED.value == "invited"
    
    def test_active_status(self):
        assert GroupMemberStatus.ACTIVE.value == "active"
    
    def test_left_status(self):
        assert GroupMemberStatus.LEFT.value == "left"
    
    def test_removed_status(self):
        assert GroupMemberStatus.REMOVED.value == "removed"


class TestGroupRole:
    
    def test_owner_role(self):
        assert GroupRole.OWNER.value == "owner"
    
    def test_admin_role(self):
        assert GroupRole.ADMIN.value == "admin"
    
    def test_member_role(self):
        assert GroupRole.MEMBER.value == "member"
    
    def test_owner_can_manage(self):
        owner = GroupRole.OWNER
        assert owner in [GroupRole.OWNER, GroupRole.ADMIN]


class TestGroupChatService:
    
    @pytest.mark.asyncio
    async def test_create_group(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group",
            description="A test group"
        )
        
        assert group is not None
        assert group.name == "Test Group"
        assert group.tenant_id == "tenant_001"
        assert group.created_by == "user_001"
        assert group.status == "active"
    
    @pytest.mark.asyncio
    async def test_get_group(self):
        service = GroupChatService()
        
        created_group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        retrieved_group = await service.get_group(created_group.id)
        
        assert retrieved_group is not None
        assert retrieved_group.id == created_group.id
        assert retrieved_group.name == "Test Group"
    
    @pytest.mark.asyncio
    async def test_is_group_member(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        is_member = await service.is_group_member(group.id, "user_001")
        assert is_member is True
        
        is_member = await service.is_group_member(group.id, "user_002")
        assert is_member is False
    
    @pytest.mark.asyncio
    async def test_get_member_role_owner(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        role = await service.get_member_role(group.id, "user_001")
        
        assert role == GroupRole.OWNER
    
    @pytest.mark.asyncio
    async def test_can_invite_owner(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        can_invite = await service.can_invite(group.id, "user_001")
        
        assert can_invite is True
    
    @pytest.mark.asyncio
    async def test_can_invite_non_member(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        can_invite = await service.can_invite(group.id, "user_002")
        
        assert can_invite is False
    
    @pytest.mark.asyncio
    async def test_invite_members(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        invitations = await service.invite_members(
            group_id=group.id,
            inviter_id="user_001",
            tenant_id="tenant_001",
            invitee_ids=["user_002", "user_003"],
            message="Join our group!"
        )
        
        assert len(invitations) == 2
        assert invitations[0].invitee_id == "user_002"
        assert invitations[1].invitee_id == "user_003"
        assert invitations[0].status == "pending"
    
    @pytest.mark.asyncio
    async def test_accept_invitation(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        invitations = await service.invite_members(
            group_id=group.id,
            inviter_id="user_001",
            tenant_id="tenant_001",
            invitee_ids=["user_002"]
        )
        
        invitation = invitations[0]
        member = await service.accept_invitation(invitation.id, "user_002")
        
        assert member is not None
        assert member.user_id == "user_002"
        assert member.role == GroupRole.MEMBER
        assert member.status == GroupMemberStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_send_message_as_member(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        message = await service.send_message(
            group_id=group.id,
            sender_id="user_001",
            tenant_id="tenant_001",
            content="Hello, group!",
            content_type="text"
        )
        
        assert message is not None
        assert message.content == "Hello, group!"
        assert message.sender_id == "user_001"
    
    @pytest.mark.asyncio
    async def test_send_message_non_member(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        message = await service.send_message(
            group_id=group.id,
            sender_id="user_002",
            tenant_id="tenant_001",
            content="Hello!"
        )
        
        assert message is None
    
    @pytest.mark.asyncio
    async def test_get_group_messages(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        await service.send_message(group.id, "user_001", "tenant_001", "Message 1")
        await service.send_message(group.id, "user_001", "tenant_001", "Message 2")
        await service.send_message(group.id, "user_001", "tenant_001", "Message 3")
        
        messages = await service.get_group_messages(group.id, limit=10)
        
        assert len(messages) == 3


class TestGroupChatWebSocketManager:
    
    @pytest.mark.asyncio
    async def test_connect_group(self):
        manager = GroupChatWebSocketManager()
        websocket = MockWebSocket()
        
        await manager.connect_group("group_001", "user_001", websocket)
        
        assert websocket.accepted is True
        assert "group_001" in manager.active_connections
        assert "user_001" in manager.active_connections["group_001"]
    
    @pytest.mark.asyncio
    async def test_disconnect_group(self):
        manager = GroupChatWebSocketManager()
        websocket = MockWebSocket()
        
        await manager.connect_group("group_001", "user_001", websocket)
        await manager.disconnect_group("group_001", "user_001")
        
        assert "user_001" not in manager.active_connections.get("group_001", {})
    
    @pytest.mark.asyncio
    async def test_broadcast_to_group(self):
        manager = GroupChatWebSocketManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await manager.connect_group("group_001", "user_001", ws1)
        await manager.connect_group("group_001", "user_002", ws2)
        
        await manager.broadcast_to_group(
            "group_001",
            {"type": "new_message", "content": "Hello!"}
        )
        
        assert len(ws1.messages) == 1
        assert len(ws2.messages) == 1
        assert ws1.messages[0]["content"] == "Hello!"
    
    @pytest.mark.asyncio
    async def test_broadcast_exclude_user(self):
        manager = GroupChatWebSocketManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await manager.connect_group("group_001", "user_001", ws1)
        await manager.connect_group("group_001", "user_002", ws2)
        
        await manager.broadcast_to_group(
            "group_001",
            {"type": "new_message", "content": "Hello!"},
            exclude_user="user_001"
        )
        
        assert len(ws1.messages) == 0
        assert len(ws2.messages) == 1
    
    @pytest.mark.asyncio
    async def test_send_personal_notification(self):
        manager = GroupChatWebSocketManager()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await manager.connect_group("group_001", "user_001", ws1)
        await manager.connect_group("group_002", "user_001", ws2)
        
        await manager.send_personal_notification(
            "user_001",
            {"type": "notification", "content": "You have a new invitation!"}
        )
        
        assert len(ws1.messages) == 1
        assert len(ws2.messages) == 1


class TestGroupMessage:
    
    def test_message_to_dict(self):
        msg = MockGroupMessage(
            id="msg_001",
            group_id="group_001",
            sender_id="user_001",
            tenant_id="tenant_001",
            content="Hello, world!",
            content_type="text"
        )
        
        result = msg.to_dict()
        
        assert result["id"] == "msg_001"
        assert result["content"] == "Hello, world!"
        assert result["content_type"] == "text"
        assert "created_at" in result
    
    def test_message_default_content_type(self):
        msg = MockGroupMessage(
            id="msg_001",
            group_id="group_001",
            sender_id="user_001",
            tenant_id="tenant_001",
            content="Hello!"
        )
        
        assert msg.content_type == "text"


class TestGroupWSEventType:
    
    def test_all_event_types_defined(self):
        assert GroupWSEventType.NEW_MESSAGE.value == "new_message"
        assert GroupWSEventType.MEMBER_JOINED.value == "member_joined"
        assert GroupWSEventType.MEMBER_LEFT.value == "member_left"
        assert GroupWSEventType.MEMBER_REMOVED.value == "member_removed"
        assert GroupWSEventType.GROUP_UPDATED.value == "group_updated"
        assert GroupWSEventType.TYPING.value == "typing"
        assert GroupWSEventType.ONLINE_STATUS.value == "online_status"
        assert GroupWSEventType.INVITATION_RECEIVED.value == "invitation_received"


class TestEdgeCases:
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_group(self):
        service = GroupChatService()
        
        group = await service.get_group("nonexistent")
        
        assert group is None
    
    @pytest.mark.asyncio
    async def test_accept_invalid_invitation(self):
        service = GroupChatService()
        
        member = await service.accept_invitation("invalid_id", "user_001")
        
        assert member is None
    
    @pytest.mark.asyncio
    async def test_invite_empty_list(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        invitations = await service.invite_members(
            group_id=group.id,
            inviter_id="user_001",
            tenant_id="tenant_001",
            invitee_ids=[]
        )
        
        assert len(invitations) == 0
    
    @pytest.mark.asyncio
    async def test_get_messages_empty_group(self):
        service = GroupChatService()
        
        group = await service.create_group(
            tenant_id="tenant_001",
            user_id="user_001",
            name="Test Group"
        )
        
        messages = await service.get_group_messages(group.id)
        
        assert len(messages) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
