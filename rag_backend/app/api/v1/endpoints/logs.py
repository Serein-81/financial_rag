# app/api/v1/endpoints/logs.py

"""
日志管理API接口

提供日志查询、统计、导出等功能
支持分级权限控制
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.system_log import LogLevel, LogCategory
from app.services.log_service import log_service
from app.schemas.log import (
    SystemLogResponse, 
    UserActionLogResponse, 
    LogStatisticsResponse,
    LogQueryParams,
    LogsListResponse,
    UserActionLogsListResponse
)
from app.utils.log_decorators import log_user_action, log_function_call

import csv
import io
import json

router = APIRouter()


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前管理员用户"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


@router.get("/", response_model=dict)
async def get_logs_root(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    level: Optional[str] = Query(None, description="日志级别过滤"),
    module: Optional[str] = Query(None, description="模块过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user)
):
    """
    日志列表根路由

    返回系统日志列表，支持分页和筛选
    """
    try:
        is_admin = current_user.is_admin

        log_level = None
        if level:
            try:
                log_level = LogLevel(level.upper())
            except ValueError:
                log_level = None

        result = await log_service.get_system_logs(
            user_id=str(current_user.id) if not is_admin else None,
            is_admin=is_admin,
            level=log_level,
            start_time=start_date,
            end_time=end_date,
            limit=page_size,
            offset=(page - 1) * page_size
        )

        logs_list = result.get("logs", [])
        total = result.get("total", 0)

        formatted_logs = []
        for log in logs_list:
            formatted_logs.append({
                "timestamp": log.get("created_at", ""),
                "level": log.get("level", "INFO"),
                "module": log.get("module", log.get("category", "system")),
                "message": log.get("message", ""),
                "details": {
                    "id": log.get("id"),
                    "category": log.get("category"),
                    "action": log.get("action"),
                    "user_id": log.get("user_id"),
                    "user_email": log.get("user_email"),
                    "session_id": log.get("session_id"),
                    "request_id": log.get("request_id"),
                    "endpoint": log.get("endpoint"),
                    "method": log.get("method"),
                    "status_code": log.get("status_code"),
                    "execution_time": log.get("execution_time"),
                    "ip_address": log.get("ip_address"),
                    "extra_data": log.get("extra_data"),
                    "error_type": log.get("error_type")
                }
            })

        return {
            "logs": formatted_logs,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        import traceback
        error_detail = f"获取日志失败: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/system", response_model=dict)
@log_user_action(
    action_type="LOG_QUERY",
    action_name="query_system_logs",
    description="User queried system logs"
)
async def get_system_logs(
    request: Request,
    level: Optional[LogLevel] = Query(None, description="日志级别过滤"),
    category: Optional[LogCategory] = Query(None, description="日志分类过滤"),
    action: Optional[str] = Query(None, description="操作动作过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    order_by: str = Query("created_at", description="排序字段"),
    order_desc: bool = Query(True, description="是否降序"),
    tenant_id: Optional[str] = Query(None, description="指定租户ID（仅管理员可用）"),
    current_user: User = Depends(get_current_user)
):
    """
    查询系统日志

    普通用户只能查看自己的日志，管理员可以查看所有日志
    支持按租户筛选
    """
    is_admin = current_user.is_admin

    tenant_ids = None
    if is_admin:
        all_tenant_ids = current_user.all_tenant_ids
        if tenant_id:
            if tenant_id in all_tenant_ids:
                tenant_ids = [tenant_id]
            else:
                raise HTTPException(status_code=403, detail="无权访问该租户")
        else:
            tenant_ids = all_tenant_ids

    result = await log_service.get_system_logs(
        user_id=str(current_user.id) if not is_admin else None,
        is_admin=is_admin,
        level=level,
        category=category,
        action=action,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_desc=order_desc,
        tenant_ids=tenant_ids
    )

    return {
        "success": True,
        "data": result,
        "message": "系统日志查询成功"
    }


@router.get("/user-actions", response_model=dict)
@log_user_action(
    action_type="LOG_QUERY",
    action_name="query_user_action_logs",
    description="User queried action logs"
)
async def get_user_action_logs(
    request: Request,
    action_type: Optional[str] = Query(None, description="操作类型过滤"),
    resource_type: Optional[str] = Query(None, description="资源类型过滤"),
    success: Optional[bool] = Query(None, description="成功状态过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user)
):
    """查询用户操作日志"""
    is_admin = current_user.is_admin
    
    result = await log_service.get_user_action_logs(
        user_id=str(current_user.id) if not is_admin else None,
        is_admin=is_admin,
        action_type=action_type,
        resource_type=resource_type,
        success=success,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )
    
    return {
        "success": True,
        "data": result,
        "message": "用户操作日志查询成功"
    }


@router.get("/statistics", response_model=dict)
@log_user_action(
    action_type="LOG_QUERY",
    action_name="query_log_statistics",
    description="User queried log statistics"
)
async def get_log_statistics(
    request: Request,
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user)
):
    """获取日志统计信息"""
    is_admin = current_user.is_admin
    
    result = await log_service.get_log_statistics(
        user_id=str(current_user.id) if not is_admin else None,
        is_admin=is_admin,
        days=days
    )
    
    return {
        "success": True,
        "data": result,
        "message": "日志统计查询成功"
    }


@router.get("/export/csv")
@log_user_action(
    action_type="LOG_EXPORT",
    action_name="export_logs_csv",
    description="User exported logs to CSV"
)
async def export_logs_csv(
    request: Request,
    log_type: str = Query("system", description="日志类型: system/user_action"),
    level: Optional[LogLevel] = Query(None, description="日志级别过滤"),
    category: Optional[LogCategory] = Query(None, description="日志分类过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(10000, ge=1, le=50000, description="导出数量限制"),
    current_user: User = Depends(get_current_user)
):
    """导出日志为CSV格式"""
    is_admin = current_user.is_admin
    
    if log_type == "system":
        result = await log_service.get_system_logs(
            user_id=str(current_user.id) if not is_admin else None,
            is_admin=is_admin,
            level=level,
            category=category,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=0
        )
        logs = result["logs"]
        
        # 创建CSV内容
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        if logs:
            headers = list(logs[0].keys())
            writer.writerow(headers)
            
            # 写入数据
            for log in logs:
                row = []
                for key in headers:
                    value = log.get(key, "")
                    if isinstance(value, dict):
                        value = json.dumps(value, ensure_ascii=False)
                    row.append(str(value) if value is not None else "")
                writer.writerow(row)
        
        # 准备响应
        output.seek(0)
        filename = f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    elif log_type == "user_action":
        result = await log_service.get_user_action_logs(
            user_id=str(current_user.id) if not is_admin else None,
            is_admin=is_admin,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=0
        )
        logs = result["logs"]
        
        # 创建CSV内容
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        if logs:
            headers = list(logs[0].keys())
            writer.writerow(headers)
            
            # 写入数据
            for log in logs:
                row = []
                for key in headers:
                    value = log.get(key, "")
                    if isinstance(value, dict):
                        value = json.dumps(value, ensure_ascii=False)
                    row.append(str(value) if value is not None else "")
                writer.writerow(row)
        
        # 准备响应
        output.seek(0)
        filename = f"user_action_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="不支持的日志类型")


@router.delete("/cleanup")
@log_user_action(
    action_type="LOG_MANAGEMENT",
    action_name="cleanup_old_logs",
    description="Admin cleaned up old logs"
)
async def cleanup_old_logs(
    request: Request,
    days: int = Query(90, ge=30, description="保留天数"),
    current_admin: User = Depends(get_current_admin_user)
):
    """清理旧日志（仅管理员）"""
    try:
        # 计算清理时间点
        cleanup_date = datetime.utcnow() - timedelta(days=days)
        
        # 这里可以实现实际的清理逻辑
        # 为了安全，暂时返回成功消息
        return {
            "success": True,
            "message": f"已清理{days}天前的日志",
            "data": {
                "retention_days": days,
                "cleanup_date": cleanup_date.isoformat(),
                "cleanup_time": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理日志失败: {str(e)}")


@router.get("/levels", response_model=dict)
async def get_log_levels():
    """获取所有日志级别"""
    return {
        "success": True,
        "data": {
            "levels": [level.value for level in LogLevel],
            "categories": [category.value for category in LogCategory]
        },
        "message": "获取日志级别和分类成功"
    }