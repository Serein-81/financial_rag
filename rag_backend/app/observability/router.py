"""
可观测性 API 路由

提供追踪、指标、日志和健康检查的 HTTP API 接口
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.observability.tracing import get_tracer, SpanContext
from app.observability.metrics import get_metrics_collector
from app.observability.logger import get_log_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observability", tags=["Observability"])


def _span_to_dict(span: SpanContext) -> Dict[str, Any]:
    """将 SpanContext 转换为前端兼容的字典格式"""
    return {
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "operation_name": span.operation_name,
        "service_name": span.service_name,
        "start_time": span.start_time.isoformat(),
        "end_time": span.end_time.isoformat() if span.end_time else None,
        "duration_ms": span.duration_ms,
        "status": span.status,
        "error_message": span.error_message,
        "attributes": span.attributes,
        "events": [
            {
                "name": e["name"],
                "timestamp": e["timestamp"],
                "attributes": e.get("attributes", {}),
            }
            for e in span.events
        ],
        "tags": span.tags,
    }


# ==================== 追踪 API ====================


@router.get("/traces")
async def get_traces(
    start_time: Optional[str] = Query(None, description="起始时间 ISO 格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO 格式"),
    service_name: Optional[str] = Query(None, description="服务名称"),
    operation_name: Optional[str] = Query(None, description="操作名称"),
    limit: int = Query(50, ge=1, le=500, description="返回条数上限"),
):
    """获取追踪列表"""
    try:
        tracer = get_tracer()
        all_spans = tracer.get_spans()

        # 按 trace_id 分组
        trace_map: Dict[str, Dict[str, Any]] = {}
        for span in all_spans:
            tid = span.trace_id
            if not tid:
                continue
            if tid not in trace_map:
                trace_map[tid] = {
                    "trace_id": tid,
                    "spans": [],
                    "total_duration_ms": 0,
                    "span_count": 0,
                }
            trace_map[tid]["spans"].append(_span_to_dict(span))
            trace_map[tid]["total_duration_ms"] = max(
                trace_map[tid]["total_duration_ms"], span.duration_ms
            )
            trace_map[tid]["span_count"] += 1

        result = list(trace_map.values())

        # 按时间过滤
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            result = [
                t
                for t in result
                if t["spans"]
                and datetime.fromisoformat(
                    t["spans"][0]["start_time"].replace("Z", "+00:00")
                )
                >= start_dt
            ]

        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            result = [
                t
                for t in result
                if t["spans"]
                and datetime.fromisoformat(
                    t["spans"][0]["start_time"].replace("Z", "+00:00")
                )
                <= end_dt
            ]

        # 按开始时间降序排列
        result.sort(
            key=lambda t: t["spans"][0]["start_time"] if t["spans"] else "",
            reverse=True,
        )

        return result[:limit]

    except Exception as e:
        logger.error(f"获取追踪列表失败: {e}")
        return []


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """获取单个追踪详情"""
    try:
        tracer = get_tracer()
        spans = tracer.get_spans(trace_id)

        if not spans:
            raise HTTPException(status_code=404, detail=f"追踪 {trace_id} 未找到")

        total_duration = max(s.duration_ms for s in spans) if spans else 0
        return {
            "trace_id": trace_id,
            "spans": [_span_to_dict(s) for s in spans],
            "total_duration_ms": total_duration,
            "span_count": len(spans),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取追踪详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}/spans/{span_id}")
async def get_span(trace_id: str, span_id: str):
    """获取单个 Span"""
    try:
        tracer = get_tracer()
        spans = tracer.get_spans(trace_id)

        for span in spans:
            if span.span_id == span_id:
                return _span_to_dict(span)

        raise HTTPException(
            status_code=404,
            detail=f"Span {span_id} 在追踪 {trace_id} 中未找到",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Span 详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 指标 API ====================


@router.get("/metrics")
async def get_metrics(
    service_name: Optional[str] = Query(None),
    metric_type: Optional[str] = Query(None),
):
    """获取指标摘要"""
    try:
        collector = get_metrics_collector()
        all_metrics = collector.collect_all()

        counters = []
        histograms = []
        gauges = []

        for name, points in all_metrics.items():
            if not points:
                continue

            first_point = points[0]
            labels = first_point.labels if hasattr(first_point, "labels") else {}

            if "requests_total" in name or "invocations" in name or "errors" in name:
                counters.append(
                    {
                        "name": name,
                        "description": "",
                        "value": first_point.value,
                        "labels": labels,
                    }
                )
            elif "duration" in name:
                histograms.append(
                    {
                        "name": name,
                        "description": "",
                        "count": len(points),
                        "sum": sum(p.value for p in points),
                        "buckets": {},
                        "labels": labels,
                    }
                )
            else:
                gauges.append(
                    {
                        "name": name,
                        "description": "",
                        "value": first_point.value,
                        "labels": labels,
                    }
                )

        return {
            "counters": counters,
            "histograms": histograms,
            "gauges": gauges,
            "total_metrics": len(counters) + len(histograms) + len(gauges),
        }

    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        return {"counters": [], "histograms": [], "gauges": [], "total_metrics": 0}


@router.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """获取 Prometheus 格式的指标"""
    try:
        collector = get_metrics_collector()
        return collector.export_prometheus()
    except Exception as e:
        logger.error(f"导出 Prometheus 指标失败: {e}")
        return "# Metrics collection not available"


# ==================== 日志 API ====================


@router.get("/logs")
async def get_logs(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    level: Optional[str] = Query(None, description="日志级别过滤"),
    trace_id: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """获取日志列表"""
    try:
        result = list(get_log_store())

        # 过滤
        if level:
            result = [r for r in result if r.get("level", "").upper() == level.upper()]

        if trace_id:
            result = [r for r in result if r.get("trace_id") == trace_id]

        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            result = [
                r
                for r in result
                if r.get("timestamp")
                and datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                >= start_dt
            ]

        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            result = [
                r
                for r in result
                if r.get("timestamp")
                and datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                <= end_dt
            ]

        # 按时间降序
        result.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

        return result[:limit]

    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        return []


@router.get("/logs/search")
async def search_logs(
    query: str = Query(..., description="搜索关键词"),
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """搜索日志"""
    try:
        result = get_log_store()

        if query:
            q = query.lower()
            result = [
                r
                for r in result
                if q in r.get("message", "").lower()
                or q in r.get("logger", "").lower()
            ]

        if level:
            result = [r for r in result if r.get("level", "").upper() == level.upper()]

        result.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return result[:limit]

    except Exception as e:
        logger.error(f"搜索日志失败: {e}")
        return []


# ==================== 健康检查 API ====================


@router.get("/health")
async def get_health():
    """获取系统健康状态"""
    try:
        tracer = get_tracer()
        metrics = get_metrics_collector()

        tracer_stats = tracer.get_stats()

        components = [
            {
                "name": "tracing",
                "status": "healthy" if tracer_stats.get("enabled", False) else "degraded",
                "latency_ms": 0,
            },
            {
                "name": "metrics",
                "status": "healthy",
                "latency_ms": 0,
            },
        ]

        overall = "healthy"

        return {
            "overall_status": overall,
            "components": components,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "overall_status": "degraded",
            "components": [
                {"name": "observability", "status": "degraded", "error": str(e)}
            ],
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 统计 API ====================


@router.get("/statistics")
async def get_statistics():
    """获取可观测性统计信息"""
    try:
        tracer = get_tracer()
        metrics = get_metrics_collector()

        tracer_stats = tracer.get_stats()

        return {
            "total_traces": tracer_stats.get("total_traces", 0),
            "total_spans": tracer_stats.get("total_spans", 0),
            "total_metrics": metrics.get_stats().get("total_metrics", 0),
            "total_logs": len(get_log_store()),
            "active_traces": tracer_stats.get("active_spans", 0),
        }

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return {
            "total_traces": 0,
            "total_spans": 0,
            "total_metrics": 0,
            "total_logs": 0,
            "active_traces": 0,
        }
