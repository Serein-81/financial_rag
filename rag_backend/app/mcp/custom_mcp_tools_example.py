"""
自定义 MCP STDIO 工具示例

展示如何在 MCP STDIO 模式下添加工具
适用于需要访问数据库、文件系统的敏感操作
"""

import logging
from typing import Optional, Dict, Any
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool("analyze_user_behavior", parse_docstring=True)
async def analyze_user_behavior(
    tenant_id: str,
    user_id: str,
    time_range: str = "7d"
) -> Dict[str, Any]:
    """
    分析用户行为数据
    
    查询用户在特定时间段内的行为数据，包括：
    - 登录次数
    - 使用功能
    - 查询记录
    
    Args:
        tenant_id: 租户ID，必填
        user_id: 用户ID，必填
        time_range: 时间范围，默认 7d（7天），可选: 1d/7d/30d/90d
    
    Returns:
        用户行为分析结果
        
    Example:
        # 分析用户最近7天的行为
        analyze_user_behavior(tenant_id="xxx", user_id="user123", time_range="7d")
    """
    try:
        from app.core.database import async_session_maker
        
        days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        days = days_map.get(time_range, 7)
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            sql = text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as action_count,
                    action_type
                FROM user_actions
                WHERE user_id = :user_id
                AND tenant_id = :tenant_id
                AND created_at >= NOW() - INTERVAL ':days days'
                GROUP BY DATE(created_at), action_type
                ORDER BY date DESC
            """)
            
            result = await session.execute(sql, {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "days": days
            })
            
            rows = result.fetchall()
            
            if not rows:
                return {
                    "status": "success",
                    "data": [],
                    "message": f"用户 {user_id} 在最近 {days} 天内无行为记录"
                }
            
            data = [
                {
                    "date": str(row[0]),
                    "action_count": row[1],
                    "action_type": row[2]
                }
                for row in rows
            ]
            
            total_actions = sum(row["action_count"] for row in data)
            
            return {
                "status": "success",
                "user_id": user_id,
                "time_range": time_range,
                "total_actions": total_actions,
                "daily_average": round(total_actions / days, 2),
                "data": data,
                "message": f"用户在 {days} 天内共执行 {total_actions} 次操作"
            }
            
    except Exception as e:
        logger.error(f"分析用户行为失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"分析用户行为失败: {str(e)}"
        }


@tool("get_user_statistics", parse_docstring=True)
async def get_user_statistics(
    tenant_id: str,
    include_inactive: bool = False
) -> Dict[str, Any]:
    """
    获取用户统计数据
    
    获取租户下所有用户的统计信息，包括：
    - 总用户数
    - 活跃用户数
    - 用户分布
    
    Args:
        tenant_id: 租户ID，必填
        include_inactive: 是否包含不活跃用户，默认 False
    
    Returns:
        用户统计数据
        
    Example:
        # 获取活跃用户统计
        get_user_statistics(tenant_id="xxx")
        
        # 获取包含不活跃用户的统计
        get_user_statistics(tenant_id="xxx", include_inactive=True)
    """
    try:
        from app.core.database import async_session_maker
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            if include_inactive:
                sql = text("""
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN last_login_at >= NOW() - INTERVAL '30 days' THEN 1 END) as active_users,
                        COUNT(CASE WHEN last_login_at >= NOW() - INTERVAL '7 days' THEN 1 END) as highly_active_users
                    FROM users
                    WHERE tenant_id = :tenant_id
                """)
            else:
                sql = text("""
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN last_login_at >= NOW() - INTERVAL '30 days' THEN 1 END) as active_users,
                        COUNT(CASE WHEN last_login_at >= NOW() - INTERVAL '7 days' THEN 1 END) as highly_active_users
                    FROM users
                    WHERE tenant_id = :tenant_id
                    AND last_login_at >= NOW() - INTERVAL '30 days'
                """)
            
            result = await session.execute(sql, {"tenant_id": tenant_id})
            row = result.fetchone()
            
            if not row:
                return {
                    "status": "success",
                    "total_users": 0,
                    "active_users": 0,
                    "highly_active_users": 0,
                    "message": "未找到用户数据"
                }
            
            return {
                "status": "success",
                "tenant_id": tenant_id,
                "total_users": row[0],
                "active_users": row[1],
                "highly_active_users": row[2],
                "active_rate": round(row[1] / row[0] * 100, 2) if row[0] > 0 else 0,
                "message": f"用户统计：共 {row[0]} 用户，{row[1]} 活跃"
            }
            
    except Exception as e:
        logger.error(f"获取用户统计失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"获取用户统计失败: {str(e)}"
        }


def create_custom_mcp_tools():
    """
    创建自定义 MCP 工具列表
    
    Returns:
        工具列表
    """
    return [
        analyze_user_behavior,
        get_user_statistics,
    ]
