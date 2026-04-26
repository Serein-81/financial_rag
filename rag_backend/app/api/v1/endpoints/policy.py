"""
政策管理 API 接口
提供政策检索、采集、调度和通知管理功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.services.policy_retrieval_service import policy_retrieval_service
from app.services.policy_notification_service import policy_notification_service
from app.services.policy_service import policy_service, SchedulerConfig, UpdateFrequency
from app.services.policy_collector import policy_collector

router = APIRouter()


class PolicySearchRequest(BaseModel):
    """政策搜索请求"""
    query: str = Field(..., description="搜索查询")
    top_k: int = Field(10, ge=1, le=100, description="返回数量")
    filters: Optional[dict] = Field(None, description="筛选条件")


class PolicyListRequest(BaseModel):
    """政策列表请求"""
    query: Optional[str] = Field(None, description="搜索查询（可选）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    filters: Optional[dict] = Field(None, description="筛选条件")


class PolicySearchResponse(BaseModel):
    """政策搜索响应"""
    results: List[dict]
    total: int
    query: str


class PolicyDetailRequest(BaseModel):
    """政策详情请求"""
    policy_id: str = Field(..., description="政策ID")


class PolicyNotificationRequest(BaseModel):
    """政策通知请求"""
    enterprise_id: str = Field(..., description="企业ID")
    status: Optional[str] = Field(None, description="状态筛选")
    limit: int = Field(20, ge=1, le=100)


class SchedulerConfigRequest(BaseModel):
    """调度器配置请求"""
    frequency: str = Field("daily", description="更新频率")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    enabled_sources: Optional[List[str]] = Field(None, description="启用的来源")
    time_of_day: str = Field("03:00", description="执行时间")


class SchedulerStatusResponse(BaseModel):
    """调度器状态响应"""
    running: bool
    last_run: Optional[str]
    config: dict
    history_count: int


@router.post("/search", response_model=PolicySearchResponse)
async def search_policies(
    request: PolicySearchRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    搜索政策
    
    支持语义检索和关键词搜索
    🔐 租户隔离：自动从当前用户获取 tenant_id
    """
    try:
        results = await policy_retrieval_service.semantic_search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            tenant_id=str(current_user.tenant_id)
        )
        
        return PolicySearchResponse(
            results=results,
            total=len(results),
            query=request.query
        )
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"搜索数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"搜索IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/list")
async def list_policies(
    request: Optional[PolicyListRequest] = None,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取政策列表
    支持分页和筛选
    """
    try:
        from app.services.policy_retrieval_service import PolicyRetrievalService
        
        service = PolicyRetrievalService()
        policies = await service.list_policies(
            query=request.query if request else None,
            industries=request.filters.get("industries") if request and request.filters else None,
            regions=request.filters.get("regions") if request and request.filters else None,
            tax_types=request.filters.get("tax_types") if request and request.filters else None,
            scales=request.filters.get("scales") if request and request.filters else None,
            page=request.page if request else 1,
            page_size=request.page_size if request else 20,
            tenant_id=str(current_user.tenant_id)
        )
        
        return policies
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"获取列表数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"获取列表IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.post("/sync")
async def sync_policies(
    current_user: User = Depends(deps.get_current_user)
):
    """
    手动触发政策同步

    从官方渠道采集最新政策入库
    """
    try:
        result = await policy_service.sync_now()
        return result

    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"同步数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"同步IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/match", response_model=PolicySearchResponse)
async def match_enterprise_policies(
    enterprise_profile: dict,
    top_k: int = Query(10, ge=1, le=50),
    current_user: User = Depends(deps.get_current_user)
):
    """
    企业政策匹配
    
    根据企业画像推荐相关政策
    """
    try:
        results = await policy_retrieval_service.match_enterprise_policies(
            enterprise_profile=enterprise_profile,
            top_k=top_k
        )
        
        return PolicySearchResponse(
            results=results,
            total=len(results),
            query="企业匹配"
        )
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"匹配数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"匹配IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"匹配失败: {str(e)}")


@router.get("/detail/{policy_id}")
async def get_policy_detail(
    policy_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取政策详情
    """
    try:
        from uuid import UUID
        policy = await policy_retrieval_service.get_policy_by_id(UUID(policy_id))
        
        if not policy:
            raise HTTPException(status_code=404, detail="政策不存在")
        
        return policy
        
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的政策ID")
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"获取详情数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"获取详情IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.get("/recent")
async def get_recent_policies(
    days: int = Query(7, ge=1, le=90),
    top_k: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取最近更新的政策
    """
    try:
        results = await policy_retrieval_service.get_recent_policies(
            days=days,
            top_k=top_k
        )
        
        return {
            "results": results,
            "total": len(results),
            "days": days
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/collect")
async def trigger_policy_collection(
    keywords: Optional[List[str]] = None,
    current_user: User = Depends(deps.get_current_user)
):
    """
    手动触发政策采集
    
    ⚠️ 需要管理员权限
    """
    try:
        result = await policy_service.trigger_manual_update(keywords)
        
        return {
            "status": "completed",
            "result": result
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"采集数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"采集IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采集失败: {str(e)}")


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取调度器状态
    """
    try:
        status = policy_service.get_scheduler_status()
        return SchedulerStatusResponse(**status)
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"获取状态数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"获取状态IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/scheduler/config")
async def configure_scheduler(
    config: SchedulerConfigRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    配置调度器
    
    ⚠️ 需要管理员权限
    """
    try:
        scheduler_config = SchedulerConfig(
            frequency=UpdateFrequency(config.frequency),
            keywords=config.keywords,
            enabled_sources=config.enabled_sources,
            time_of_day=config.time_of_day
        )
        
        policy_service.configure_scheduler(scheduler_config)
        
        return {
            "status": "configured",
            "config": {
                "frequency": scheduler_config.frequency.value,
                "keywords": scheduler_config.keywords,
                "enabled_sources": scheduler_config.enabled_sources,
                "time_of_day": scheduler_config.time_of_day
            }
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"配置数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"配置IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置失败: {str(e)}")


@router.post("/scheduler/start")
async def start_scheduler(
    current_user: User = Depends(deps.get_current_user)
):
    """
    启动调度器
    
    ⚠️ 需要管理员权限
    """
    try:
        await policy_service.start_scheduler()
        
        return {
            "status": "started",
            "message": "调度器已启动"
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"启动数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"启动IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.post("/scheduler/stop")
async def stop_scheduler(
    current_user: User = Depends(deps.get_current_user)
):
    """
    停止调度器
    
    ⚠️ 需要管理员权限
    """
    try:
        await policy_service.stop_scheduler()
        
        return {
            "status": "stopped",
            "message": "调度器已停止"
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"停止数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"停止IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


@router.get("/notifications/{enterprise_id}")
async def get_enterprise_notifications(
    enterprise_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取企业通知列表
    """
    try:
        from app.models.enterprise_policy_match import NotificationStatus
        
        status_enum = None
        if status:
            try:
                status_enum = NotificationStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的状态")
        
        notifications = await policy_notification_service.get_enterprise_notifications(
            enterprise_id=enterprise_id,
            status=status_enum,
            limit=limit
        )
        
        return {
            "enterprise_id": enterprise_id,
            "notifications": notifications,
            "total": len(notifications)
        }
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        import traceback
        import logging
        logging.getLogger(__name__).error(f"获取通知失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取通知失败: {str(e)}")


@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_notification(
    notification_id: str,
    feedback: Optional[dict] = None,
    current_user: User = Depends(deps.get_current_user)
):
    """
    确认通知
    """
    try:
        from uuid import UUID
        from app.services.policy_notification_service import policy_notification_service
        
        success = await policy_notification_service.acknowledge_notification(
            UUID(notification_id),
            feedback
        )
        
        if success:
            return {"status": "acknowledged", "notification_id": notification_id}
        else:
            raise HTTPException(status_code=404, detail="通知不存在")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的通知ID")
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"确认数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"确认IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认失败: {str(e)}")


@router.post("/notifications/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(deps.get_current_user)
):
    """
    忽略通知
    """
    try:
        from uuid import UUID
        
        success = await policy_notification_service.dismiss_notification(
            UUID(notification_id),
            reason
        )
        
        if success:
            return {"status": "dismissed", "notification_id": notification_id}
        else:
            raise HTTPException(status_code=404, detail="通知不存在")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的通知ID")
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"忽略数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"忽略IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"忽略失败: {str(e)}")


@router.get("/sources")
async def get_policy_sources(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取配置的政策来源
    """
    try:
        sources = []
        for source in policy_collector.sources:
            sources.append({
                "name": source.name,
                "base_url": source.base_url,
                "enabled": source.enabled,
                "priority": source.priority
            })
        
        return {
            "sources": sources,
            "total": len(sources)
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"获取来源数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"获取来源IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取来源失败: {str(e)}")


@router.get("/report/export")
async def export_policy_report_pdf(
    policy_ids: Optional[str] = Query(None, description="政策ID列表，逗号分隔"),
    query: Optional[str] = Query(None, description="搜索查询"),
    top_k: int = Query(20, ge=1, le=100, description="导出数量"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    导出政策报告为 PDF
    
    根据指定条件导出政策报告 PDF
    可以指定政策ID列表或搜索查询
    
    Args:
        policy_ids: 政策ID列表（逗号分隔）
        query: 搜索查询
        top_k: 导出数量
        
    Returns:
        PDF 文件的流式响应
    """
    try:
        from fastapi.responses import StreamingResponse
        from io import BytesIO
        import logging
        
        logger = logging.getLogger(__name__)
        
        policies_data = []
        
        if policy_ids:
            policy_id_list = [pid.strip() for pid in policy_ids.split(",")]
            for pid in policy_id_list:
                try:
                    policy = await policy_retrieval_service.get_policy_by_id(pid)
                    if policy:
                        policies_data.append(policy)
                except (ValueError, KeyError) as e:
                    logger.warning(f"获取政策 {pid} 数据错误: {e}")
                except (OSError, IOError) as e:
                    logger.warning(f"获取政策 {pid} IO错误: {e}")
                except (OSError, IOError) as e:
                    raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
                except Exception as e:
                    logger.warning(f"获取政策 {pid} 失败: {e}")
        
        if query and len(policies_data) < top_k:
            results = await policy_retrieval_service.search_policies(
                query=query,
                top_k=top_k - len(policies_data),
                filters=None
            )
            for result in results:
                if result.get("policy_id") and not any(p.get("policy_id") == result.get("policy_id") for p in policies_data):
                    policies_data.append(result)
        
        if not policies_data:
            policies_data = await policy_retrieval_service.search_policies(
                query="",
                top_k=top_k,
                filters=None
            )
        
        report_data = {
            "policies": policies_data,
            "export_time": datetime.now().isoformat(),
            "total_count": len(policies_data),
            "query": query or "所有政策",
            "enterprise_id": str(current_user.tenant_id) if current_user.tenant_id else None
        }
        
        from app.services.pdf_export_service import pdf_export_service
        pdf_bytes = pdf_export_service.export_policy_report(report_data)
        
        filename = f"policy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 政策报告PDF导出数据错误: {e}", exc_info=True)
    except (OSError, IOError) as e:
        logger.error(f"❌ 政策报告PDF导出IO错误: {e}", exc_info=True)
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 政策报告PDF导出失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策报告PDF导出失败: {str(e)}")
