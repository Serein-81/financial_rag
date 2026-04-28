"""
对话日志服务

提供对话日志的查询和统计等功能
支持用户级权限控制和企业管理员权限
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.chat import ChatSession, ChatMessage
from app.models.user import User
from app.models.tenant_settings import TenantSettings
from app.models.system_log import UserActionLog
from app.services.log_service import log_service

import logging

logger = logging.getLogger(__name__)


class ChatLogService:
    """
    对话日志服务

    提供对话日志的查询和统计
    支持权限控制：普通用户只能查看自己的日志，企业管理员可以查看整个企业的日志
    """

    async def get_user_id_by_email(self, email: str) -> Optional[str]:
        """根据邮箱获取用户ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.id).where(User.email == email)
            )
            user_id = result.scalar_one_or_none()
            return str(user_id) if user_id else None

    async def get_tenant_id_by_user_id(self, user_id: str) -> Optional[str]:
        """根据用户ID获取租户ID"""
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return None
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.tenant_id).where(User.id == user_uuid)
            )
            return result.scalar_one_or_none()

    async def is_tenant_admin(self, user_id: str) -> bool:
        """检查用户是否为租户管理员"""
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return False
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.is_admin).where(User.id == user_uuid)
            )
            return result.scalar_one_or_none() is True

    async def is_same_tenant(self, user_id_1: str, user_id_2: str) -> bool:
        """
        检查两个用户是否属于同一个租户
        
        Args:
            user_id_1: 用户1的ID
            user_id_2: 用户2的ID
            
        Returns:
            bool: 是否属于同一租户
        """
        if user_id_1 == user_id_2:
            return True
            
        try:
            user1_uuid = uuid.UUID(user_id_1)
            user2_uuid = uuid.UUID(user_id_2)
        except (ValueError, TypeError):
            return False
            
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.tenant_id).where(User.id == user1_uuid)
            )
            tenant1 = result.scalar_one_or_none()
            
            if not tenant1:
                return False
                
            result = await session.execute(
                select(User.tenant_id).where(User.id == user2_uuid)
            )
            tenant2 = result.scalar_one_or_none()
            
            return tenant1 == tenant2 and tenant1 is not None

    async def get_user_with_managed_tenants(self, user_id: str) -> Optional[User]:
        """获取用户对象（包含管理的租户列表）"""
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return None
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == user_uuid)
            )
            return result.scalar_one_or_none()

    async def get_tenant_info(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """获取租户信息（ID、名称等）"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TenantSettings.company_name).where(TenantSettings.tenant_id == tenant_id)
            )
            company_name = result.scalar_one_or_none()
            if not company_name:
                result = await session.execute(
                    select(User.company_name).where(User.tenant_id == tenant_id).limit(1)
                )
                company_name = result.scalar_one_or_none()
            return {
                "tenant_id": tenant_id,
                "company_name": company_name or tenant_id
            }

    async def get_all_managed_tenants(self, user_id: str) -> List[Dict[str, Any]]:
        """获取管理员管理的所有租户信息"""
        user = await self.get_user_with_managed_tenants(user_id)
        if not user:
            return []

        tenants = []
        for tid in user.all_tenant_ids:
            info = await self.get_tenant_info(tid)
            if info:
                info["is_primary"] = (tid == user.tenant_id)
                tenants.append(info)

        return tenants

    async def get_sessions(
        self,
        current_user_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        获取会话列表（支持权限控制）

        Args:
            current_user_id: 当前用户ID
            page: 页码
            page_size: 每页数量
            user_id: 指定用户ID（仅管理员可用）
            keyword: 搜索关键词
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            分页后的会话列表
        """
        try:
            async with AsyncSessionLocal() as session:
                base_query = select(ChatSession)

                base_query = base_query.where(ChatSession.user_id == current_user_id)

                if keyword:
                    base_query = base_query.where(ChatSession.title.ilike(f"%{keyword}%"))

                if start_date:
                    base_query = base_query.where(ChatSession.created_at >= start_date)
                if end_date:
                    base_query = base_query.where(ChatSession.created_at <= end_date)

                count_query = select(func.count()).select_from(base_query.subquery())
                count_result = await session.execute(count_query)
                total = count_result.scalar()

                sessions_query = (
                    base_query
                    .order_by(desc(ChatSession.updated_at))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                result = await session.execute(sessions_query)
                sessions = result.scalars().all()

                if not sessions:
                    return {
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "sessions": [],
                    }

                session_ids = [s.id for s in sessions]
                user_ids_in_sessions = list(set(s.user_id for s in sessions if s.user_id))

                user_names_query = select(User.id, User.full_name).where(User.id.in_(user_ids_in_sessions))
                user_names_result = await session.execute(user_names_query)
                user_names_dict = {str(row[0]): row[1] or "未知用户" for row in user_names_result.all()}

                messages_query = select(
                    ChatMessage.session_id,
                    func.count(ChatMessage.id).label('message_count'),
                    func.sum(ChatMessage.prompt_tokens).label('total_prompt_tokens'),
                    func.sum(ChatMessage.completion_tokens).label('total_completion_tokens'),
                    func.sum(ChatMessage.total_tokens).label('total_tokens')
                ).where(
                    ChatMessage.session_id.in_(session_ids),
                    ChatMessage.role == "assistant"
                ).group_by(ChatMessage.session_id)
                messages_stats_result = await session.execute(messages_query)
                messages_stats = {str(row[0]): {
                    'message_count': row[1] or 0,
                    'total_prompt_tokens': row[2] or 0,
                    'total_completion_tokens': row[3] or 0,
                    'total_tokens': row[4] or 0
                } for row in messages_stats_result.all()}

                last_message_query = select(
                    ChatMessage.session_id,
                    ChatMessage.content
                ).where(
                    ChatMessage.session_id.in_(session_ids)
                ).order_by(
                    ChatMessage.session_id,
                    desc(ChatMessage.created_at)
                )
                last_messages_result = await session.execute(last_message_query)
                last_messages_by_session = {}
                for row in last_messages_result.all():
                    session_id_str = str(row[0])
                    if session_id_str not in last_messages_by_session:
                        last_messages_by_session[session_id_str] = row[1][:100] if row[1] else None

                sessions_list = []
                for s in sessions:
                    try:
                        session_id_str = str(s.id)
                        stats = messages_stats.get(session_id_str, {
                            'message_count': 0,
                            'total_prompt_tokens': 0,
                            'total_completion_tokens': 0,
                            'total_tokens': 0
                        })
                        sessions_list.append({
                            "id": session_id_str,
                            "user_id": str(s.user_id) if s.user_id else "",
                            "user_name": user_names_dict.get(str(s.user_id), "未知用户") if s.user_id else "未知用户",
                            "title": s.title or "无标题",
                            "created_at": s.created_at.isoformat() if s.created_at else None,
                            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                            "message_count": stats.get('message_count', 0),
                            "last_message_preview": last_messages_by_session.get(session_id_str),
                            "total_prompt_tokens": stats.get('total_prompt_tokens', 0),
                            "total_completion_tokens": stats.get('total_completion_tokens', 0),
                            "total_tokens": stats.get('total_tokens', 0),
                        })
                    except Exception as e:
                        logger.error(f"Error converting session {s.id}: {e}", exc_info=True)
                        sessions_list.append({
                            "id": str(s.id),
                            "user_id": str(s.user_id) if s.user_id else "",
                            "user_name": "未知用户",
                            "title": s.title or "无标题",
                            "created_at": s.created_at.isoformat() if s.created_at else None,
                            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                            "message_count": 0,
                            "last_message_preview": None,
                            "total_prompt_tokens": 0,
                            "total_completion_tokens": 0,
                            "total_tokens": 0,
                        })

                return {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "sessions": sessions_list,
                }
        except Exception as e:
            logger.error(f"Error in get_sessions: {e}", exc_info=True)
            raise

    async def get_session_messages(
        self,
        session_id: str,
        current_user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        获取会话的所有消息

        Args:
            session_id: 会话ID
            current_user_id: 当前用户ID

        Returns:
            消息列表
        """
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            return []

        async with AsyncSessionLocal() as session:
            session_query = select(ChatSession).where(ChatSession.id == session_uuid)
            session_result = await session.execute(session_query)
            session_obj = session_result.scalar_one_or_none()

            if not session_obj:
                return []

            if str(session_obj.user_id) != current_user_id:
                return []

            messages_query = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_uuid)
                .order_by(ChatMessage.created_at)
            )
            messages_result = await session.execute(messages_query)
            messages = messages_result.scalars().all()

            return [m.to_log_dict() for m in messages]

    async def get_session_statistics(
        self,
        session_id: str,
        current_user_id: str,
    ) -> Dict[str, Any]:
        """
        获取会话的统计信息

        Args:
            session_id: 会话ID
            current_user_id: 当前用户ID

        Returns:
            统计信息
        """
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            return {}

        async with AsyncSessionLocal() as session:
            session_query = select(ChatSession).where(ChatSession.id == session_uuid)
            session_result = await session.execute(session_query)
            session_obj = session_result.scalar_one_or_none()

            if not session_obj:
                return {}

            if str(session_obj.user_id) != current_user_id:
                return {}

            messages_query = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_uuid)
            )
            messages_result = await session.execute(messages_query)
            messages = messages_result.scalars().all()

            assistant_messages = [m for m in messages if m.role == "assistant"]

            total_prompt_tokens = sum(
                m.prompt_tokens or 0 for m in assistant_messages
            )
            total_completion_tokens = sum(
                m.completion_tokens or 0 for m in assistant_messages
            )
            total_tokens = sum(m.total_tokens or 0 for m in assistant_messages)

            assistant_message_count = len(assistant_messages)

            user_result = await session.execute(
                select(User.full_name).where(User.id == session_obj.user_id)
            )
            user_name = user_result.scalar_one_or_none() or "未知用户"

            return {
                "session_id": str(session_id),
                "title": session_obj.title,
                "user_id": str(session_obj.user_id),
                "user_name": user_name,
                "created_at": session_obj.created_at.isoformat() if session_obj.created_at else None,
                "message_count": len(messages),
                "total_turns": assistant_message_count,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
            }

    async def get_user_statistics(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        获取用户的对话统计和操作日志统计

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含AI对话统计和用户操作日志统计的完整统计信息
        """
        try:
            async with AsyncSessionLocal() as session:
                user_uuid = None
                try:
                    user_uuid = uuid.UUID(user_id)
                except (ValueError, TypeError):
                    logger.error(f"Invalid user_id format: {user_id}")
                    return {
                        "user_id": str(user_id),
                        "user_name": "未知用户",
                        "chat_statistics": {
                            "total_sessions": 0,
                            "total_messages": 0,
                            "total_turns": 0,
                            "total_prompt_tokens": 0,
                            "total_completion_tokens": 0,
                            "total_tokens": 0,
                        },
                        "action_statistics": {
                            "total_actions": 0,
                            "level_stats": {
                                "INFO": 0,
                                "ERROR": 0,
                                "WARNING": 0,
                                "DEBUG": 0
                            },
                            "success_count": 0,
                            "failure_count": 0,
                            "success_rate": 0
                        }
                    }

                # 查询当前用户的AI消息（通过ChatSession关联）
                base_query = select(ChatMessage).join(
                    ChatSession, ChatMessage.session_id == ChatSession.id
                ).where(
                    ChatSession.user_id == user_uuid,
                    ChatMessage.role == "assistant"
                )

                if start_date:
                    base_query = base_query.where(ChatMessage.created_at >= start_date)
                if end_date:
                    base_query = base_query.where(ChatMessage.created_at <= end_date)

                result = await session.execute(base_query)
                messages = result.scalars().all()
                
                logger.info(f"[AI对话统计] user_uuid: {user_uuid}, 消息数: {len(messages)}, 会话数: {len(set(str(m.session_id) for m in messages))}")

                total_prompt_tokens = sum(m.prompt_tokens or 0 for m in messages)
                total_completion_tokens = sum(m.completion_tokens or 0 for m in messages)
                total_tokens = sum(m.total_tokens or 0 for m in messages)

                session_ids = set(str(m.session_id) for m in messages)

                user_result = await session.execute(
                    select(User.full_name).where(User.id == user_uuid)
                )
                user_name = user_result.scalar_one_or_none() or "未知用户"

                # 获取用户操作日志统计
                action_stats = await log_service.get_user_action_statistics(
                    user_id=str(user_id),
                    days=30
                )

                return {
                    "user_id": str(user_id),
                    "user_name": user_name,
                    "chat_statistics": {
                        "total_sessions": len(session_ids),
                        "total_messages": len(messages),
                        "total_turns": len(messages),
                        "total_prompt_tokens": total_prompt_tokens,
                        "total_completion_tokens": total_completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "action_statistics": {
                        "total_actions": action_stats.get("total_actions", 0),
                        "level_stats": action_stats.get("level_stats", {
                            "INFO": 0,
                            "ERROR": 0,
                            "WARNING": 0,
                            "DEBUG": 0
                        }),
                        "success_count": action_stats.get("success_count", 0),
                        "failure_count": action_stats.get("failure_count", 0),
                        "success_rate": action_stats.get("success_rate", 0),
                        "action_type_stats": action_stats.get("action_type_stats", {}),
                        "top_actions": action_stats.get("top_actions", [])
                    }
                }
        except Exception as e:
            logger.error(f"Error in get_user_statistics: {str(e)}", exc_info=True)
            raise

    async def get_tenant_statistics(
        self,
        current_user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取租户的对话统计（仅管理员可用）

        Args:
            current_user_id: 当前管理员用户ID
            start_date: 开始日期
            end_date: 结束日期
            tenant_id: 指定租户ID（可选，默认查询所有可管理的租户）

        Returns:
            统计信息
        """
        is_admin = await self.is_tenant_admin(current_user_id)
        if not is_admin:
            return {"error": "Permission denied"}

        user = await self.get_user_with_managed_tenants(current_user_id)
        if not user:
            return {"error": "User not found"}

        all_tenant_ids = user.all_tenant_ids
        if not all_tenant_ids:
            return {"error": "No tenant found"}

        if tenant_id:
            if tenant_id not in all_tenant_ids:
                return {"error": "Access denied to this tenant"}
            query_tenant_ids = [tenant_id]
        else:
            query_tenant_ids = all_tenant_ids

        async with AsyncSessionLocal() as session:
            user_ids_result = await session.execute(
                select(User.id).where(User.tenant_id.in_(query_tenant_ids))
            )
            user_ids = list(user_ids_result.scalars().all())

            if not user_ids:
                return {
                    "total_users": len(user_ids),
                    "active_users": 0,
                    "total_sessions": 0,
                    "total_messages": 0,
                    "total_turns": 0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "total_tokens": 0,
                    "tenant_id": tenant_id or "all",
                    "tenant_ids": query_tenant_ids,
                }

            base_query = (
                select(ChatMessage)
                .options(selectinload(ChatMessage.session))
                .where(ChatMessage.role == "assistant")
                .where(ChatMessage.session_id.in_(
                    select(ChatSession.id).where(ChatSession.user_id.in_(user_ids))
                ))
            )

            if start_date:
                base_query = base_query.where(ChatMessage.created_at >= start_date)
            if end_date:
                base_query = base_query.where(ChatMessage.created_at <= end_date)

            result = await session.execute(base_query)
            messages = result.scalars().all()

            total_prompt_tokens = sum(m.prompt_tokens or 0 for m in messages)
            total_completion_tokens = sum(m.completion_tokens or 0 for m in messages)
            total_tokens = sum(m.total_tokens or 0 for m in messages)

            session_ids = set(str(m.session_id) for m in messages)

            active_user_ids = set()
            for m in messages:
                if m.session and m.session.user_id:
                    active_user_ids.add(str(m.session.user_id))

            return {
                "total_users": len(user_ids),
                "active_users": len(active_user_ids),
                "total_sessions": len(session_ids),
                "total_messages": len(messages),
                "total_turns": len(messages),
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "tenant_id": tenant_id or "all",
                "tenant_ids": query_tenant_ids,
            }

    async def _session_to_dict(self, session: ChatSession) -> Dict[str, Any]:
        """将会话对象转换为字典"""
        try:
            async with AsyncSessionLocal() as db:
                user_name = "未知用户"
                if session.user_id:
                    user_result = await db.execute(
                        select(User.full_name).where(User.id == session.user_id)
                    )
                    user_name = user_result.scalar_one_or_none() or "未知用户"

                messages_result = await db.execute(
                    select(ChatMessage).where(ChatMessage.session_id == session.id)
                )
                messages = list(messages_result.scalars().all())

                message_count = len(messages)
                last_message = messages[-1] if messages else None
                last_message_preview = None
                if last_message and last_message.content:
                    last_message_preview = last_message.content[:100]

                assistant_messages = [m for m in messages if m.role == "assistant"]
                total_prompt_tokens = sum(m.prompt_tokens or 0 for m in assistant_messages)
                total_completion_tokens = sum(m.completion_tokens or 0 for m in assistant_messages)
                total_tokens = sum(m.total_tokens or 0 for m in assistant_messages)

            return {
                "id": str(session.id),
                "user_id": str(session.user_id) if session.user_id else "",
                "user_name": user_name,
                "title": session.title or "无标题",
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "message_count": message_count,
                "last_message_preview": last_message_preview,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
            }
        except Exception:
            return {
                "id": str(session.id),
                "user_id": str(session.user_id) if session.user_id else "",
                "user_name": "未知用户",
                "title": session.title or "无标题",
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "message_count": 0,
                "last_message_preview": None,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
            }

    async def get_messages_missing_embedding(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取缺少 embedding 的消息（用于数据修复）

        Args:
            user_id: 可选，指定用户ID
            limit: 返回数量限制

        Returns:
            缺少 embedding 的消息列表
        """
        async with AsyncSessionLocal() as session:
            query = select(ChatMessage)
            if user_id:
                user_uuid = uuid.UUID(user_id)
                query = query.join(
                    ChatSession, ChatMessage.session_id == ChatSession.id
                ).where(ChatSession.user_id == user_uuid)
            query = query.where(ChatMessage.embedding.is_(None)).limit(limit)
            result = await session.execute(query)
            messages = result.scalars().all()
            return [{
                "id": str(m.id),
                "session_id": str(m.session_id),
                "role": m.role,
                "content": m.content[:100] if m.content else "",
                "created_at": m.created_at.isoformat() if m.created_at else None
            } for m in messages]

    async def get_data_integrity_report(
        self,
        current_user_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取数据完整性报告

        Args:
            current_user_id: 当前用户ID
            user_id: 可选，指定用户ID（仅管理员可用）

        Returns:
            数据完整性报告
        """
        is_admin = await self.is_tenant_admin(current_user_id)
        if user_id and not is_admin:
            user_id = current_user_id
        elif user_id and is_admin:
            pass
        else:
            user_id = current_user_id

        async with AsyncSessionLocal() as session:
            query = select(ChatMessage)
            if user_id:
                user_uuid = uuid.UUID(user_id)
                query = query.join(
                    ChatSession, ChatMessage.session_id == ChatSession.id
                ).where(ChatSession.user_id == user_uuid)

            result = await session.execute(query)
            total_messages = len(result.scalars().all())

            result = await session.execute(
                query.where(ChatMessage.embedding.is_(None))
            )
            missing_embedding = len(result.scalars().all())

            result = await session.execute(
                query.where(ChatMessage.importance.is_(None))
            )
            missing_importance = len(result.scalars().all())

            result = await session.execute(
                query.where(ChatMessage.embedding.is_(None))
            )
            missing_embedding_ids = [str(m.id) for m in result.scalars().all()]

            total_size_bytes = 0
            result = await session.execute(query.limit(1000))
            for m in result.scalars().all():
                total_size_bytes += ChatMessage.calculate_message_size(m)

            return {
                "user_id": user_id,
                "total_messages": total_messages,
                "missing_embedding_count": missing_embedding,
                "missing_embedding_percentage": round(missing_embedding / total_messages * 100, 2) if total_messages > 0 else 0,
                "missing_importance_count": missing_importance,
                "missing_importance_percentage": round(missing_importance / total_messages * 100, 2) if total_messages > 0 else 0,
                "missing_embedding_sample_ids": missing_embedding_ids[:10],
                "estimated_storage_mb": round(total_size_bytes / 1024 / 1024, 2),
                "needs_repair": missing_embedding > 0
            }

    async def get_user_action_logs(
        self,
        current_user_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        level: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取用户操作日志列表

        Args:
            current_user_id: 当前用户ID（用于权限控制）
            page: 页码
            page_size: 每页数量
            start_date: 开始日期
            end_date: 结束日期
            level: 日志等级
            action_type: 操作类型

        Returns:
            包含日志列表和分页信息的字典
        """
        try:
            async with AsyncSessionLocal() as session:
                current_user_result = await session.execute(
                    select(User).where(User.id == current_user_id)
                )
                current_user = current_user_result.scalar_one_or_none()

                if current_user and current_user.is_admin:
                    accessible_tenant_ids = current_user.all_tenant_ids
                    tenant_user_ids_query = select(User.id).where(User.tenant_id.in_(accessible_tenant_ids))
                    base_query = select(UserActionLog).where(
                        (UserActionLog.tenant_id.in_(accessible_tenant_ids))
                        | (UserActionLog.user_id.in_(tenant_user_ids_query))
                    )
                else:
                    base_query = select(UserActionLog).where(
                        UserActionLog.user_id == current_user_id
                    )

                if start_date:
                    base_query = base_query.where(UserActionLog.created_at >= start_date)
                if end_date:
                    base_query = base_query.where(UserActionLog.created_at <= end_date)
                if level:
                    base_query = base_query.where(UserActionLog.level == level)
                if action_type:
                    base_query = base_query.where(UserActionLog.action_type == action_type)

                count_query = select(func.count()).select_from(base_query.subquery())
                count_result = await session.execute(count_query)
                total = count_result.scalar_one()

                offset = (page - 1) * page_size
                query = (
                    base_query
                    .order_by(desc(UserActionLog.created_at))
                    .offset(offset)
                    .limit(page_size)
                )

                result = await session.execute(query)
                logs = result.scalars().all()

                log_items = []
                for log in logs:
                    log_items.append({
                        "id": str(log.id),
                        "user_id": str(log.user_id),
                        "user_email": log.user_email,
                        "tenant_id": log.tenant_id,
                        "action_type": log.action_type,
                        "action_name": log.action_name,
                        "description": log.description,
                        "resource_type": log.resource_type,
                        "resource_id": log.resource_id,
                        "resource_name": log.resource_name,
                        "success": log.success,
                        "result_message": log.result_message,
                        "ip_address": log.ip_address,
                        "user_agent": log.user_agent,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                        "level": log.level,
                        "risk_level": log.risk_level,
                    })

                return {
                    "logs": log_items,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                }

        except Exception as e:
            logger.error(f"获取用户操作日志列表失败: {e}")
            return {
                "logs": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            }


chat_log_service = ChatLogService()
