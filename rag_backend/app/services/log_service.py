# app/services/log_service.py

"""
日志服务

提供系统日志记录、查询、分析等功能
支持分级权限控制和多维度查询
"""

import inspect
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.system_log import SystemLog, UserActionLog, LogLevel, LogCategory
from app.models.user import User

import logging
import uuid

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from app.utils.time_utils import now_beijing, format_iso


class LogService:
    """
    日志服务类
    
    提供日志记录、查询、统计等功能
    """
    
    def __init__(self):
        """初始化日志服务"""
        self.logger = logging.getLogger(__name__)
        
    async def create_system_log(
        self,
        level: LogLevel,
        category: LogCategory,
        action: str,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs
    ) -> SystemLog:
        """
        创建系统日志
        
        Args:
            level: 日志级别
            category: 日志分类
            action: 操作动作
            message: 日志消息
            user_id: 用户ID
            session_id: 会话ID
            request_id: 请求ID
            **kwargs: 其他参数
        """
        async with AsyncSessionLocal() as session:
            # 获取调用栈信息
            frame = inspect.currentframe()
            caller_frame = frame.f_back.f_back if frame and frame.f_back else None
            
            log_data = {
                "level": level.value,
                "category": category.value,
                "action": action,
                "message": message,
                "user_id": user_id,
                "session_id": session_id,
                "request_id": request_id,
            }
            
            # 添加调用信息
            if caller_frame:
                log_data.update({
                    "module": caller_frame.f_globals.get("__name__"),
                    "function": caller_frame.f_code.co_name,
                    "line_number": caller_frame.f_lineno,
                })
            
            # 添加其他参数
            for key, value in kwargs.items():
                if hasattr(SystemLog, key):
                    log_data[key] = value
            
            # 创建日志记录
            system_log = SystemLog(**log_data)
            session.add(system_log)
            await session.commit()
            await session.refresh(system_log)
            
            return system_log
    
    async def create_user_action_log(
        self,
        user_id: Optional[str],
        action_type: str,
        action_name: str,
        description: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        success: bool = True,
        result_message: Optional[str] = None,
        **kwargs
    ) -> Optional[UserActionLog]:
        """
        创建用户操作日志
        
        Args:
            user_id: 用户ID（可以为None）
            action_type: 操作类型
            action_name: 操作名称
            description: 操作描述
            resource_type: 资源类型
            resource_id: 资源ID
            resource_name: 资源名称
            success: 是否成功
            result_message: 结果消息
            **kwargs: 其他参数
        """
        async with AsyncSessionLocal() as session:
            # 转换user_id为UUID对象
            user_uuid = None
            user_email = None
            
            if user_id:
                try:
                    user_uuid = uuid.UUID(str(user_id))
                    # 获取用户邮箱
                    user_result = await session.execute(
                        select(User.email).where(User.id == user_uuid)
                    )
                    user_email = user_result.scalar_one_or_none()
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"user_id格式无效: {user_id}, 错误: {e}")
                    user_uuid = None
            
            # 使用北京时间记录日志
            log_timestamp = now_beijing()
            
            log_data = {
                "user_id": user_uuid,
                "user_email": user_email,
                "action_type": action_type,
                "action_name": action_name,
                "description": description,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "resource_name": resource_name,
                "success": success,
                "result_message": result_message,
            }
            
            self.logger.info(
                f"[用户操作日志] 时间: {format_iso(log_timestamp)}, "
                f"用户: {user_email or 'Unknown'}, "
                f"操作: {action_type}/{action_name}, "
                f"结果: {'成功' if success else '失败'}"
            )
            
            # 添加其他参数
            for key, value in kwargs.items():
                if hasattr(UserActionLog, key):
                    log_data[key] = value
            
            # 创建用户操作日志
            action_log = UserActionLog(**log_data)
            session.add(action_log)
            await session.commit()
            await session.refresh(action_log)
            
            return action_log
    
    async def get_system_logs(
        self,
        user_id: Optional[str] = None,
        is_admin: bool = False,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None,
        action: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
        tenant_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        查询系统日志

        Args:
            user_id: 用户ID（普通用户只能查看自己的日志）
            is_admin: 是否管理员
            level: 日志级别过滤
            category: 日志分类过滤
            action: 操作动作过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            offset: 偏移量
            order_by: 排序字段
            order_desc: 是否降序
            tenant_ids: 租户ID列表（用于管理员多租户筛选）
        """
        async with AsyncSessionLocal() as session:
            from app.models.user import User
            conditions = []

            if not is_admin and user_id:
                conditions.append(SystemLog.user_id == user_id)

            if tenant_ids:
                user_query = select(User.id).where(User.tenant_id.in_(tenant_ids))
                conditions.append(SystemLog.user_id.in_(user_query))
            
            # 过滤条件
            if level:
                conditions.append(SystemLog.level == level.value)
            if category:
                conditions.append(SystemLog.category == category.value)
            if action:
                conditions.append(SystemLog.action.ilike(f"%{action}%"))
            if start_time:
                conditions.append(SystemLog.created_at >= start_time)
            if end_time:
                conditions.append(SystemLog.created_at <= end_time)
            
            # 构建查询
            query = select(SystemLog).options(selectinload(SystemLog.user))
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # 排序
            order_column = getattr(SystemLog, order_by, SystemLog.created_at)
            if order_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
            
            # 分页
            query = query.offset(offset).limit(limit)
            
            # 执行查询
            result = await session.execute(query)
            logs = result.scalars().all()
            
            # 获取总数
            count_query = select(func.count(SystemLog.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            count_result = await session.execute(count_query)
            total = count_result.scalar()
            
            # 🔧 优化：收集所有需要的 tenant_id，一次性查询，避免 N+1 问题
            tenant_ids_needed = set()
            for log in logs:
                if log.user and log.user.tenant_id:
                    tenant_ids_needed.add(log.user.tenant_id)
            
            # 一次性查询所有需要的租户信息
            tenants_dict = {}
            if tenant_ids_needed:
                from app.models.tenant import Tenant
                tenants_query = select(Tenant).where(Tenant.id.in_(tenant_ids_needed))
                tenants_result = await session.execute(tenants_query)
                tenants = tenants_result.scalars().all()
                for tenant in tenants:
                    tenants_dict[str(tenant.id)] = tenant
            
            # 转换为字典格式
            log_list = []
            for log in logs:
                log_dict = log.to_dict(include_sensitive=is_admin)
                if log.user:
                    log_dict["user_email"] = log.user.email
                    log_dict["user_name"] = log.user.full_name
                    # 添加租户信息 - 使用字典查找，避免 N+1 查询
                    if log.user.tenant_id:
                        log_dict["tenant_id"] = log.user.tenant_id
                        tenant = tenants_dict.get(log.user.tenant_id)
                        if tenant:
                            log_dict["tenant_name"] = tenant.company_name
                            log_dict["tenant_invite_code"] = tenant.invite_code
                log_list.append(log_dict)
            
            return {
                "logs": log_list,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(logs) < total
            }
    
    async def get_user_action_logs(
        self,
        user_id: Optional[str] = None,
        is_admin: bool = False,
        action_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        success: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        查询用户操作日志
        
        Args:
            user_id: 用户ID
            is_admin: 是否管理员
            action_type: 操作类型过滤
            resource_type: 资源类型过滤
            success: 成功状态过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            offset: 偏移量
        """
        async with AsyncSessionLocal() as session:
            # 构建查询条件
            conditions = []
            
            # 权限控制
            if not is_admin and user_id:
                conditions.append(UserActionLog.user_id == user_id)
            
            # 过滤条件
            if action_type:
                conditions.append(UserActionLog.action_type == action_type)
            if resource_type:
                conditions.append(UserActionLog.resource_type == resource_type)
            if success is not None:
                conditions.append(UserActionLog.success == success)
            if start_time:
                conditions.append(UserActionLog.created_at >= start_time)
            if end_time:
                conditions.append(UserActionLog.created_at <= end_time)
            
            # 构建查询
            query = select(UserActionLog).options(selectinload(UserActionLog.user))
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.order_by(desc(UserActionLog.created_at))
            query = query.offset(offset).limit(limit)
            
            # 执行查询
            result = await session.execute(query)
            logs = result.scalars().all()
            
            # 获取总数
            count_query = select(func.count(UserActionLog.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            count_result = await session.execute(count_query)
            total = count_result.scalar()
            
            # 转换为字典格式
            log_list = []
            for log in logs:
                log_dict = {
                    "id": str(log.id),
                    "created_at": log.created_at.isoformat(),
                    "user_id": str(log.user_id),
                    "user_email": log.user_email,
                    "action_type": log.action_type,
                    "action_name": log.action_name,
                    "description": log.description,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "resource_name": log.resource_name,
                    "success": log.success,
                    "result_message": log.result_message,
                    "ip_address": log.ip_address,
                    "session_id": log.session_id,
                }
                
                # 管理员可以查看更多信息
                if is_admin:
                    log_dict.update({
                        "user_agent": log.user_agent,
                        "before_data": log.before_data,
                        "after_data": log.after_data,
                        "extra_info": log.extra_info,
                    })
                
                log_list.append(log_dict)
            
            return {
                "logs": log_list,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(logs) < total
            }
    
    async def get_log_statistics(
        self,
        user_id: Optional[str] = None,
        is_admin: bool = False,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        获取日志统计信息
        
        Args:
            user_id: 用户ID
            is_admin: 是否管理员
            days: 统计天数
        """
        async with AsyncSessionLocal() as session:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # 权限控制
            conditions = [SystemLog.created_at >= start_time]
            if not is_admin and user_id:
                conditions.append(SystemLog.user_id == user_id)
            
            # 按级别统计
            level_query = select(
                SystemLog.level,
                func.count(SystemLog.id).label('count')
            ).where(and_(*conditions)).group_by(SystemLog.level)
            
            level_result = await session.execute(level_query)
            level_stats = {row.level: row.count for row in level_result}
            
            # 按分类统计
            category_query = select(
                SystemLog.category,
                func.count(SystemLog.id).label('count')
            ).where(and_(*conditions)).group_by(SystemLog.category)
            
            category_result = await session.execute(category_query)
            category_stats = {row.category: row.count for row in category_result}
            
            # 按天统计
            daily_query = select(
                func.date(SystemLog.created_at).label('date'),
                func.count(SystemLog.id).label('count')
            ).where(and_(*conditions)).group_by(func.date(SystemLog.created_at))
            
            daily_result = await session.execute(daily_query)
            daily_stats = {str(row.date): row.count for row in daily_result}
            
            # 错误统计
            error_conditions = conditions + [SystemLog.level.in_(['ERROR', 'CRITICAL'])]
            error_query = select(func.count(SystemLog.id)).where(and_(*error_conditions))
            error_result = await session.execute(error_query)
            error_count = error_result.scalar()
            
            return {
                "period": f"{days} days",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "level_stats": level_stats,
                "category_stats": category_stats,
                "daily_stats": daily_stats,
                "error_count": error_count,
                "total_logs": sum(level_stats.values())
            }

    async def get_user_action_statistics(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取用户操作日志统计
        
        Args:
            user_id: 用户ID（可选，为None则统计所有用户）
            days: 统计天数，默认30天
        
        Returns:
            包含各级别操作数量的统计信息
        """
        self.logger.info(f"获取用户操作统计 - user_id: {user_id}, 天数: {days}")
        
        async with AsyncSessionLocal() as session:
            end_time = now_beijing()
            start_time = end_time - timedelta(days=days)
            
            # 基础查询条件
            conditions = [UserActionLog.created_at >= start_time]
            
            user_uuid = None
            if user_id:
                # 转换为UUID对象进行查询
                try:
                    user_uuid = uuid.UUID(str(user_id))
                    conditions.append(UserActionLog.user_id == user_uuid)
                    self.logger.info(f"查询条件已添加 - user_uuid: {user_uuid}")
                except (ValueError, TypeError) as e:
                    self.logger.error(f"UUID转换失败 - user_id: {user_id}, 错误: {e}")
                    # 如果转换失败，返回空统计
                    return {
                        "period": f"{days} days",
                        "start_time": format_iso(start_time),
                        "end_time": format_iso(end_time),
                        "total_actions": 0,
                        "level_stats": {
                            "INFO": 0,
                            "ERROR": 0,
                            "WARNING": 0,
                            "DEBUG": 0
                        },
                        "success_count": 0,
                        "failure_count": 0,
                        "action_type_stats": {},
                        "top_actions": [],
                        "success_rate": 0
                    }
            
            self.logger.info(f"开始查询统计 - 查询条件数: {len(conditions)}, user_uuid: {user_uuid}")
            
            # 按操作结果统计（success=True为INFO级别，success=False为ERROR级别）
            success_query = select(
                UserActionLog.success,
                func.count(UserActionLog.id).label('count')
            ).where(and_(*conditions)).group_by(UserActionLog.success)
            
            success_result = await session.execute(success_query)
            success_stats = {row.success: row.count for row in success_result}
            
            # 计算INFO和ERROR级别
            info_count = success_stats.get(True, 0)  # 成功操作 -> INFO
            error_count = success_stats.get(False, 0)  # 失败操作 -> ERROR
            
            # 按操作类型统计
            action_type_query = select(
                UserActionLog.action_type,
                func.count(UserActionLog.id).label('count')
            ).where(and_(*conditions)).group_by(UserActionLog.action_type)
            
            action_type_result = await session.execute(action_type_query)
            action_type_stats = {row.action_type: row.count for row in action_type_result}
            
            # 按操作名称统计（TOP操作）
            action_name_query = select(
                UserActionLog.action_name,
                func.count(UserActionLog.id).label('count')
            ).where(and_(*conditions)).group_by(UserActionLog.action_name).order_by(desc('count')).limit(10)
            
            action_name_result = await session.execute(action_name_query)
            top_actions = [{row.action_name: row.count} for row in action_name_result]
            
            # 总操作数
            total_query = select(func.count(UserActionLog.id)).where(and_(*conditions))
            total_result = await session.execute(total_query)
            total_count = total_result.scalar()
            
            self.logger.info(f"查询完成 - 总操作数: {total_count}, user_uuid: {user_uuid}")
            
            return {
                "period": f"{days} days",
                "start_time": format_iso(start_time),
                "end_time": format_iso(end_time),
                "total_actions": total_count or 0,
                "level_stats": {
                    "INFO": info_count,
                    "ERROR": error_count,
                    "WARNING": 0,
                    "DEBUG": 0
                },
                "success_count": info_count,
                "failure_count": error_count,
                "action_type_stats": action_type_stats,
                "top_actions": top_actions,
                "success_rate": round(info_count / total_count * 100, 2) if total_count > 0 else 0
            }


# 创建全局日志服务实例
log_service = LogService()