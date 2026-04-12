"""
操作日志服务

提供全面的操作日志记录功能，记录用户在系统中的各种操作
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from app.api.v1.endpoints.multi_agent import (
    record_security_event,
    SecurityEventType,
    SecurityEventSeverity
)

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """操作类型枚举"""
    LOGIN = "login"
    LOGOUT = "logout"
    QUERY = "query"
    SEARCH = "search"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE = "delete"
    UPDATE = "update"
    CREATE = "create"
    APPROVE = "approve"
    REJECT = "reject"
    INTENT_CLASSIFY = "intent_classify"
    SPECIALIST_QUERY = "specialist_query"
    REPORT_GENERATE = "report_generate"
    SESSION_CREATE = "session_create"
    SESSION_END = "session_end"
    KB_CREATE = "kb_create"
    KB_UPDATE = "kb_update"
    KB_DELETE = "kb_delete"
    DOC_UPLOAD = "doc_upload"
    DOC_DELETE = "doc_delete"
    PERMISSION_CHANGE = "permission_change"
    ADMIN_ACTION = "admin_action"
    FINANCIAL_DOC_UPLOAD = "financial_doc_upload"
    TAX_REPORT_UPLOAD = "tax_report_upload"


class OperationLogger:
    """操作日志记录器"""

    def __init__(self):
        self._operation_storage: List[Dict[str, Any]] = []
        self._max_storage_size = 5000

    def log_operation(
        self,
        operation_type: OperationType,
        user_id: str,
        tenant_id: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        risk_level: str = "low"
    ) -> Dict[str, Any]:
        """记录操作日志"""
        timestamp = datetime.now()
        operation_id = f"op_{timestamp.strftime('%Y%m%d%H%M%S')}_{user_id[:8]}"

        log_entry = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "resource": resource,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": timestamp.isoformat(),
            "risk_level": risk_level
        }

        self._operation_storage.append(log_entry)

        if len(self._operation_storage) > self._max_storage_size:
            self._operation_storage.pop(0)

        logger.info(
            f"[操作日志] {operation_type.value} - "
            f"user_id: {user_id}, "
            f"resource: {resource}, "
            f"details: {json.dumps(details or {}, ensure_ascii=False)[:200]}"
        )

        severity_map = {
            "low": SecurityEventSeverity.LOW,
            "medium": SecurityEventSeverity.MEDIUM,
            "high": SecurityEventSeverity.HIGH,
            "critical": SecurityEventSeverity.CRITICAL
        }

        security_event_map = {
            OperationType.LOGIN: SecurityEventType.LOGIN_SUCCESS,
            OperationType.LOGOUT: SecurityEventType.LOGOUT,
            OperationType.DELETE: SecurityEventType.HIGH_RISK_OPERATION,
            OperationType.PERMISSION_CHANGE: SecurityEventType.ROLE_CHANGE,
            OperationType.APPROVE: SecurityEventType.APPROVAL_COMPLETED,
            OperationType.REJECT: SecurityEventType.APPROVAL_COMPLETED,
        }

        security_event_type = security_event_map.get(
            operation_type, SecurityEventType.HIGH_RISK_OPERATION
        )

        try:
            record_security_event(
                event_type=security_event_type,
                user_id=user_id,
                tenant_id=tenant_id,
                target_resource=resource,
                severity=severity_map.get(risk_level, SecurityEventSeverity.LOW),
                details={
                    "operation_id": operation_id,
                    "operation_type": operation_type.value,
                    "details": details or {}
                },
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            logger.warning(f"记录安全事件失败: {str(e)}")

        return log_entry

    def get_user_operations(
        self,
        user_id: str,
        limit: int = 100,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """获取用户操作日志"""
        filtered_ops = [
            op for op in self._operation_storage
            if op["user_id"] == user_id
        ]

        if operation_type:
            filtered_ops = [
                op for op in filtered_ops
                if op["operation_type"] == operation_type
            ]

        if start_date:
            filtered_ops = [
                op for op in filtered_ops
                if datetime.fromisoformat(op["timestamp"]) >= start_date
            ]

        if end_date:
            filtered_ops = [
                op for op in filtered_ops
                if datetime.fromisoformat(op["timestamp"]) <= end_date
            ]

        filtered_ops.sort(key=lambda x: x["timestamp"], reverse=True)
        return filtered_ops[:limit]

    def get_tenant_operations(
        self,
        tenant_id: str,
        limit: int = 100,
        operation_type: Optional[str] = None,
        risk_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取租户操作日志"""
        filtered_ops = [
            op for op in self._operation_storage
            if op.get("tenant_id") == tenant_id
        ]

        if operation_type:
            filtered_ops = [
                op for op in filtered_ops
                if op["operation_type"] == operation_type
            ]

        if risk_level:
            filtered_ops = [
                op for op in filtered_ops
                if op.get("risk_level") == risk_level
            ]

        filtered_ops.sort(key=lambda x: x["timestamp"], reverse=True)
        return filtered_ops[:limit]

    def get_statistics(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取操作统计"""
        start_date = datetime.now() - timedelta(days=days)

        filtered_ops = [
            op for op in self._operation_storage
            if datetime.fromisoformat(op["timestamp"]) >= start_date
        ]

        if user_id:
            filtered_ops = [op for op in filtered_ops if op["user_id"] == user_id]

        if tenant_id:
            filtered_ops = [op for op in filtered_ops if op.get("tenant_id") == tenant_id]

        by_type: Dict[str, int] = {}
        by_day: Dict[str, int] = {}
        risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for op in filtered_ops:
            op_type = op["operation_type"]
            by_type[op_type] = by_type.get(op_type, 0) + 1

            day = op["timestamp"][:10]
            by_day[day] = by_day.get(day, 0) + 1

            risk = op.get("risk_level", "low")
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        return {
            "total_operations": len(filtered_ops),
            "by_type": by_type,
            "by_day": by_day,
            "risk_distribution": risk_counts,
            "period_days": days
        }

    def search_operations(
        self,
        keyword: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """搜索操作日志"""
        results = []

        for op in self._operation_storage:
            if user_id and op["user_id"] != user_id:
                continue
            if tenant_id and op.get("tenant_id") != tenant_id:
                continue

            search_text = json.dumps(op, ensure_ascii=False)
            if keyword.lower() in search_text.lower():
                results.append(op)

        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results[:limit]


operation_logger = OperationLogger()


def log_user_query(
    user_id: str,
    query: str,
    tenant_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    session_id: Optional[str] = None,
    response_time_ms: Optional[float] = None,
    result_count: Optional[int] = None
):
    """记录用户查询操作"""
    operation_logger.log_operation(
        operation_type=OperationType.QUERY,
        user_id=user_id,
        tenant_id=tenant_id,
        resource=f"session/{session_id}" if session_id else None,
        details={
            "query": query[:500],
            "session_id": session_id,
            "response_time_ms": response_time_ms,
            "result_count": result_count
        },
        ip_address=ip_address,
        risk_level="low"
    )


def log_user_search(
    user_id: str,
    search_query: str,
    tenant_id: Optional[str] = None,
    kb_id: Optional[str] = None,
    result_count: int = 0,
    ip_address: Optional[str] = None
):
    """记录用户搜索操作"""
    operation_logger.log_operation(
        operation_type=OperationType.SEARCH,
        user_id=user_id,
        tenant_id=tenant_id,
        resource=f"knowledge_base/{kb_id}" if kb_id else None,
        details={
            "search_query": search_query[:500],
            "kb_id": kb_id,
            "result_count": result_count
        },
        ip_address=ip_address,
        risk_level="low"
    )


def log_document_upload(
    user_id: str,
    document_name: str,
    kb_id: str,
    tenant_id: Optional[str] = None,
    file_size: int = 0,
    ip_address: Optional[str] = None
):
    """记录文档上传"""
    operation_logger.log_operation(
        operation_type=OperationType.DOC_UPLOAD,
        user_id=user_id,
        tenant_id=tenant_id,
        resource=f"knowledge_base/{kb_id}/document/{document_name}",
        details={
            "document_name": document_name,
            "kb_id": kb_id,
            "file_size": file_size
        },
        ip_address=ip_address,
        risk_level="medium"
    )


def log_document_delete(
    user_id: str,
    document_id: str,
    document_name: str,
    kb_id: str,
    tenant_id: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """记录文档删除"""
    operation_logger.log_operation(
        operation_type=OperationType.DOC_DELETE,
        user_id=user_id,
        tenant_id=tenant_id,
        resource=f"knowledge_base/{kb_id}/document/{document_id}",
        details={
            "document_id": document_id,
            "document_name": document_name,
            "kb_id": kb_id
        },
        ip_address=ip_address,
        risk_level="high"
    )


def log_specialist_query(
    user_id: str,
    specialist_type: str,
    query: str,
    tenant_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    session_id: Optional[str] = None,
    execution_time_ms: Optional[float] = None
):
    """记录专家查询"""
    operation_logger.log_operation(
        operation_type=OperationType.SPECIALIST_QUERY,
        user_id=user_id,
        tenant_id=tenant_id,
        resource=f"specialist/{specialist_type}",
        details={
            "specialist_type": specialist_type,
            "query": query[:500],
            "session_id": session_id,
            "execution_time_ms": execution_time_ms
        },
        ip_address=ip_address,
        risk_level="low"
    )


def log_intent_classification(
    user_id: str,
    message: str,
    intent: str,
    confidence: float,
    tenant_id: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """记录意图分类"""
    operation_logger.log_operation(
        operation_type=OperationType.INTENT_CLASSIFY,
        user_id=user_id,
        tenant_id=tenant_id,
        details={
            "message": message[:500],
            "intent": intent,
            "confidence": confidence
        },
        ip_address=ip_address,
        risk_level="low"
    )


def log_knowledge_base_operation(
    operation_type: OperationType,
    user_id: str,
    kb_id: str,
    kb_name: str,
    tenant_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    risk_level: str = "medium"
):
    """记录知识库操作"""
    operation_logger.log_operation(
        operation_type=operation_type,
        user_id=user_id,
        tenant_id=tenant_id,
        resource=f"knowledge_base/{kb_id}",
        details={
            "kb_id": kb_id,
            "kb_name": kb_name,
            **(details or {})
        },
        ip_address=ip_address,
        risk_level=risk_level
    )


def log_admin_action(
    admin_id: str,
    action: str,
    target_user_id: Optional[str] = None,
    target_resource: Optional[str] = None,
    tenant_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
):
    """记录管理员操作"""
    operation_logger.log_operation(
        operation_type=OperationType.ADMIN_ACTION,
        user_id=admin_id,
        tenant_id=tenant_id,
        resource=target_resource,
        details={
            "action": action,
            "target_user_id": target_user_id,
            **(details or {})
        },
        ip_address=ip_address,
        risk_level="high"
    )
