"""
MCP 业务工具

提供 Agent 可调用的业务工具
包含通知发送、用户行为分析等功能

工具类型：本地 STDIO
"""

import logging
from typing import Dict, Any, Optional, List

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)


@local_tool(
    description="发送通知消息给指定用户，支持 in_app/email/sms 等渠道"
)
async def send_notification(
    user_id: str,
    title: str,
    message: str,
    channel: str = "in_app"
) -> Dict[str, Any]:
    """
    发送通知消息给指定用户
    
    当 Agent 需要向用户推送重要信息、提醒或结果时使用此工具。
    
    Args:
        user_id: 用户ID，必填
        title: 通知标题，必填
        message: 通知内容，必填
        channel: 通知渠道，默认 in_app，可选: in_app/email/sms
    
    Returns:
        发送结果字典
    
    Example:
        send_notification(user_id="user123", title="报告生成完成", message="您的报告已生成")
    """
    logger.info(f"发送通知: {title} -> {user_id}")
    
    try:
        from app.services.notification_service import NotificationService
        
        service = NotificationService()
        result = await service.send(
            user_id=user_id,
            title=title,
            message=message,
            channel=channel
        )
        
        return {
            "status": "success",
            "notification_id": result.get("id"),
            "channel": channel,
            "user_id": user_id,
            "message": f"通知已通过 {channel} 发送给用户 {user_id}"
        }
        
    except Exception as e:
        logger.error(f"发送通知失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"发送通知失败: {str(e)}"
        }


@local_tool(
    description="批量发送通知，向多个用户发送相同内容"
)
async def batch_send_notification(
    user_ids: List[str],
    title: str,
    message: str,
    channel: str = "in_app"
) -> Dict[str, Any]:
    """
    批量发送通知
    
    向多个用户发送相同内容的通知。
    
    Args:
        user_ids: 用户ID列表，必填
        title: 通知标题，必填
        message: 通知内容，必填
        channel: 通知渠道，默认 in_app
    
    Returns:
        批量发送结果
    
    Example:
        batch_send_notification(user_ids=["user1", "user2"], title="系统通知", message="系统维护")
    """
    logger.info(f"批量发送通知: {title} -> {len(user_ids)} 用户")
    
    success_count = 0
    failed_users = []
    
    try:
        from app.services.notification_service import NotificationService
        
        service = NotificationService()
        
        for user_id in user_ids:
            try:
                await service.send(
                    user_id=user_id,
                    title=title,
                    message=message,
                    channel=channel
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"发送通知给 {user_id} 失败: {e}")
                failed_users.append(user_id)
        
        return {
            "status": "success",
            "total": len(user_ids),
            "success_count": success_count,
            "failed_count": len(failed_users),
            "failed_users": failed_users,
            "message": f"批量发送完成: {success_count}/{len(user_ids)} 成功"
        }
        
    except Exception as e:
        logger.error(f"批量发送通知失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"批量发送通知失败: {str(e)}"
        }


@local_tool(
    description="分析用户在特定时间段内的行为数据，包括登录次数、使用功能等"
)
async def analyze_user_behavior(
    tenant_id: str,
    user_id: str,
    time_range: str = "7d"
) -> Dict[str, Any]:
    """
    分析用户行为数据
    
    查询用户在特定时间段内的行为数据。
    
    Args:
        tenant_id: 租户ID，必填
        user_id: 用户ID，必填
        time_range: 时间范围，默认 7d，可选: 1d/7d/30d/90d
    
    Returns:
        用户行为分析结果
    
    Example:
        analyze_user_behavior(tenant_id="xxx", user_id="user123", time_range="7d")
    """
    try:
        from app.core.database import async_session_maker
        
        days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        days = days_map.get(time_range, 7)
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            sql = text("""
                SELECT DATE(created_at) as date, COUNT(*) as action_count, action_type
                FROM user_actions
                WHERE user_id = :user_id AND tenant_id = :tenant_id
                AND created_at >= NOW() - INTERVAL ':days days'
                GROUP BY DATE(created_at), action_type
                ORDER BY date DESC
            """)
            
            result = await session.execute(sql, {"user_id": user_id, "tenant_id": tenant_id, "days": days})
            rows = result.fetchall()
            
            if not rows:
                return {
                    "status": "success",
                    "data": [],
                    "message": f"用户 {user_id} 在最近 {days} 天内无行为记录"
                }
            
            data = [{"date": str(row[0]), "action_count": row[1], "action_type": row[2]} for row in rows]
            total_actions = sum(row["action_count"] for row in data)
            
            return {
                "status": "success",
                "user_id": user_id,
                "time_range": time_range,
                "total_actions": total_actions,
                "daily_average": round(total_actions / days, 2),
                "data": data,
                "message": f"用户在 {days} 天内共 {total_actions} 次操作，日均 {total_actions / days:.2f} 次"
            }
            
    except Exception as e:
        logger.error(f"分析用户行为失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"分析用户行为失败: {str(e)}"
        }


@local_tool(
    description="获取租户下所有用户的统计数据，包括总用户数、活跃用户数、活跃率"
)
async def get_user_statistics(
    tenant_id: str,
    include_inactive: bool = False
) -> Dict[str, Any]:
    """
    获取用户统计数据
    
    获取租户下所有用户的统计信息。
    
    Args:
        tenant_id: 租户ID，必填
        include_inactive: 是否包含不活跃用户，默认 False
    
    Returns:
        用户统计数据
    
    Example:
        get_user_statistics(tenant_id="xxx")
    """
    try:
        from app.core.database import async_session_maker
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            if include_inactive:
                sql = text("""
                    SELECT COUNT(*) as total_users,
                           COUNT(CASE WHEN last_login_at >= NOW() - INTERVAL '30 days' THEN 1 END) as active_users
                    FROM users WHERE tenant_id = :tenant_id
                """)
            else:
                sql = text("""
                    SELECT COUNT(*) as total_users,
                           COUNT(CASE WHEN last_login_at >= NOW() - INTERVAL '30 days' THEN 1 END) as active_users
                    FROM users WHERE tenant_id = :tenant_id AND last_login_at >= NOW() - INTERVAL '30 days'
                """)
            
            result = await session.execute(sql, {"tenant_id": tenant_id})
            row = result.fetchone()
            
            if not row:
                return {"status": "success", "total_users": 0, "active_users": 0, "message": "未找到用户数据"}
            
            return {
                "status": "success",
                "tenant_id": tenant_id,
                "total_users": row[0],
                "active_users": row[1],
                "active_rate": round(row[1] / row[0] * 100, 2) if row[0] > 0 else 0,
                "message": f"用户统计：共 {row[0]} 用户，{row[1]} 活跃（{row[1] / row[0] * 100:.1f}%）"
            }
            
    except Exception as e:
        logger.error(f"获取用户统计失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"获取用户统计失败: {str(e)}"
        }


def create_business_tools():
    """创建业务工具列表"""
    return [
        send_notification,
        batch_send_notification,
        analyze_user_behavior,
        get_user_statistics,
    ]
