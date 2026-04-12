"""
管理员通知服务

当用户操作涉及高风险AI行为时，自动通知管理员
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from app.services.group_chat_service import group_chat_ws_manager
from app.db.session import get_db_context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """通知类型"""
    IN_APP = "in_app"  # 应用内通知
    EMAIL = "email"  # 邮件通知
    SMS = "sms"  # 短信通知
    WEBHOOK = "webhook"  # Webhook通知
    TAX_REMINDER = "tax_reminder"  # 税务提醒
    POLICY_UPDATE = "policy_update"  # 政策更新
    ANOMALY_ALERT = "anomaly_alert"  # 异常预警
    SYSTEM_ALERT = "system_alert"  # 系统告警


class NotificationPriority(str, Enum):
    """通知优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RiskLevel(str, Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(str, Enum):
    """风险类别"""
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"  # 敏感数据访问
    FINANCIAL_OPERATION = "financial_operation"  # 财务操作
    BULK_OPERATION = "bulk_operation"  # 批量操作
    SYSTEM_CONFIG = "system_config"  # 系统配置
    EXPENSE_APPROVAL = "expense_approval"  # 费用审批
    TAX_OPERATION = "tax_operation"  # 税务操作
    LEGAL_RISK = "legal_risk"  # 法律风险
    SECURITY_ALERT = "security_alert"  # 安全警报


class HighRiskBehavior(str, Enum):
    """高风险行为定义"""
    BULK_DELETE = "bulk_delete"  # 批量删除
    SENSITIVE_DATA_EXPORT = "sensitive_data_export"  # 敏感数据导出
    SYSTEM_CONFIG_CHANGE = "system_config_change"  # 系统配置修改
    LARGE_EXPENSE_APPROVAL = "large_expense_approval"  # 大额费用审批
    TAX_DECLARATION = "tax_declaration"  # 税务申报
    CONTRACT_GENERATION = "contract_generation"  # 合同生成
    AUDIT_REQUEST = "audit_request"  # 审计请求
    USER_PERMISSION_CHANGE = "user_permission_change"  # 用户权限变更
    BULK_DATA_MODIFICATION = "bulk_data_modification"  # 批量数据修改
    EXTERNAL_DATA_SHARING = "external_data_sharing"  # 外部数据共享


RISK_KEYWORDS = {
    HighRiskBehavior.BULK_DELETE: ["批量删除", "删除全部", "清空", "删除所有"],
    HighRiskBehavior.SENSITIVE_DATA_EXPORT: ["导出敏感数据", "导出全部数据", "下载敏感信息"],
    HighRiskBehavior.SYSTEM_CONFIG_CHANGE: ["修改系统配置", "系统设置", "配置变更"],
    HighRiskBehavior.LARGE_EXPENSE_APPROVAL: ["大额审批", "高额费用", "巨额支出"],
    HighRiskBehavior.TAX_DECLARATION: ["税务申报", "纳税申报", "报税"],
    HighRiskBehavior.CONTRACT_GENERATION: ["生成合同", "创建合同", "合同模板"],
    HighRiskBehavior.AUDIT_REQUEST: ["审计请求", "合规检查", "合规审计"],
    HighRiskBehavior.USER_PERMISSION_CHANGE: ["修改权限", "变更角色", "用户权限"],
    HighRiskBehavior.BULK_DATA_MODIFICATION: ["批量修改", "批量更新", "批量编辑"],
    HighRiskBehavior.EXTERNAL_DATA_SHARING: ["外部共享", "数据外发", "导出到外部"],
}

RISK_THRESHOLDS = {
    RiskLevel.LOW: 0.0,
    RiskLevel.MEDIUM: 0.3,
    RiskLevel.HIGH: 0.6,
    RiskLevel.CRITICAL: 0.8,
}


class AdminNotificationService:
    """
    管理员通知服务
    
    功能：
    1. 检测高风险AI操作
    2. 创建HITL审批请求
    3. 发送通知给管理员
    4. 记录审计日志
    """

    def __init__(self):
        """初始化服务"""
        self.redis = None
        try:
            from app.services.redis_service import get_redis_service
            self.redis = get_redis_service()
        except (ValueError, KeyError) as e:
            logger.warning(f"Redis未初始化，数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"Redis未初始化，IO错误: {e}")
        except Exception as e:
            logger.warning(f"Redis未初始化，通知功能可能受限: {e}")

    async def detect_risk_level(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[RiskLevel, List[HighRiskBehavior]]:
        """
        检测用户查询的风险级别
        
        Args:
            user_query: 用户查询内容
            context: 附加上下文
            
        Returns:
            (风险级别, 检测到的高风险行为列表)
        """
        detected_behaviors = []
        
        user_query_lower = user_query.lower()
        
        for behavior, keywords in RISK_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in user_query_lower:
                    detected_behaviors.append(behavior)
                    break
        
        if context:
            confidence = context.get("confidence", 0.5)
            if confidence < 0.5:
                detected_behaviors.append(HighRiskBehavior.AUDIT_REQUEST)
            
            entity_count = len(context.get("entities", []))
            if entity_count > 10:
                detected_behaviors.append(HighRiskBehavior.BULK_OPERATION)
        
        risk_score = len(detected_behaviors) / 10.0
        
        if risk_score >= RISK_THRESHOLDS[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL, detected_behaviors
        elif risk_score >= RISK_THRESHOLDS[RiskLevel.HIGH]:
            return RiskLevel.HIGH, detected_behaviors
        elif risk_score >= RISK_THRESHOLDS[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM, detected_behaviors
        else:
            return RiskLevel.LOW, detected_behaviors

    async def create_hitl_request(
        self,
        user_id: str,
        tenant_id: str,
        session_id: str,
        user_query: str,
        risk_level: RiskLevel,
        detected_behaviors: List[HighRiskBehavior],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建HITL审批请求
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            session_id: 会话ID
            user_query: 用户查询
            risk_level: 风险级别
            detected_behaviors: 检测到的行为
            context: 附加上下文
            
        Returns:
            审批请求详情
        """
        from app.api.v1.endpoints.multi_agent import hitl_approvals_storage
        import uuid
        
        approval_id = str(uuid.uuid4())
        now = datetime.now()
        
        approval_details = {
            "approval_id": approval_id,
            "task_id": f"task_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "operation": "ai_high_risk_operation",
            "query": user_query,
            "risk_level": risk_level.value,
            "detected_behaviors": [b.value for b in detected_behaviors],
            "context": context or {},
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=24)).isoformat()
        }
        
        hitl_approvals_storage[approval_id] = type('Approval', (), approval_details)()
        
        logger.info(f"🔔 创建HITL审批请求: {approval_id}")
        logger.info(f"   用户: {user_id}, 风险级别: {risk_level.value}")
        logger.info(f"   检测行为: {[b.value for b in detected_behaviors]}")
        
        return approval_details

    async def notify_admins(
        self,
        tenant_id: str,
        notification_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        通知所有管理员
        
        Args:
            tenant_id: 租户ID
            notification_type: 通知类型
            title: 通知标题
            message: 通知消息
            metadata: 附加元数据
        """
        admin_user_ids = await self._get_admin_users(tenant_id)
        
        if not admin_user_ids:
            logger.warning(f"未找到租户 {tenant_id} 的管理员用户")
            return
        
        notification_payload = {
            "type": notification_type,
            "title": title,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        
        for admin_id in admin_user_ids:
            try:
                await group_chat_ws_manager.send_personal_notification(
                    admin_id,
                    notification_payload
                )
                logger.info(f"✅ 通知已发送给管理员: {admin_id}")
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 通知发送给管理员数据错误: {admin_id}, 错误: {e}")
            except (OSError, IOError) as e:
                logger.error(f"❌ 通知发送给管理员IO错误: {admin_id}, 错误: {e}")
            except Exception as e:
                logger.error(f"❌ 通知发送给管理员失败: {admin_id}, 错误: {e}")
        
        if self.redis:
            notification_key = f"notification:admin:{tenant_id}"
            self.redis.client.lpush(
                notification_key,
                json.dumps(notification_payload)
            )
            self.redis.client.expire(notification_key, 604800)

    async def _get_admin_users(self, tenant_id: str) -> List[str]:
        """
        获取租户的所有管理员用户ID
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            管理员用户ID列表
        """
        try:
            async with get_db_context() as db:
                from app.models.user import User
                from app.models.group_chat import GroupMember, GroupRole
                
                result = await db.execute(
                    select(User.id).join(
                        GroupMember,
                        User.id == GroupMember.user_id
                    ).where(
                        GroupMember.tenant_id == tenant_id,
                        GroupMember.role == GroupRole.ADMIN.value
                    )
                )
                admin_ids = [row[0] for row in result.fetchall()]
                return admin_ids
        except (ValueError, KeyError) as e:
            logger.error(f"获取管理员列表数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            logger.error(f"获取管理员列表IO错误: {e}")
            return []
        except Exception as e:
            logger.error(f"获取管理员列表失败: {e}")
            return []

    async def log_security_event(
        self,
        tenant_id: str,
        user_id: str,
        event_type: str,
        severity: str,
        details: Dict[str, Any]
    ):
        """
        记录安全事件到审计日志
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID
            event_type: 事件类型
            severity: 严重程度
            details: 详细信息
        """
        try:
            async with get_db_context() as db:
                from app.models.system_log import SystemLog
                
                log_entry = SystemLog(
                    id=f"sec_{uuid.uuid4().hex[:12]}",
                    tenant_id=tenant_id,
                    level=severity,
                    source="hitl_system",
                    message=f"HITL安全事件: {event_type}",
                    details={
                        "event_type": event_type,
                        "user_id": user_id,
                        "details": details
                    }
                )
                db.add(log_entry)
                await db.commit()
                
                logger.info(f"📝 安全事件已记录: {event_type} by user {user_id}")
        except (ValueError, KeyError) as e:
            logger.error(f"记录安全事件数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"记录安全事件IO错误: {e}")
        except Exception as e:
            logger.error(f"记录安全事件失败: {e}")

    async def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.IN_APP,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        webhook_url: Optional[str] = None
    ):
        """
        发送通知（支持多种渠道）
        
        Args:
            user_id: 用户ID
            title: 通知标题
            message: 通知内容
            notification_type: 通知类型
            priority: 优先级
            metadata: 附加元数据
            email: 邮箱地址（邮件通知用）
            phone: 手机号（短信通知用）
            webhook_url: Webhook地址
        """
        try:
            notification_payload = {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type.value,
                "priority": priority.value,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }
            
            if notification_type == NotificationType.IN_APP or notification_type == NotificationType.TAX_REMINDER or notification_type == NotificationType.POLICY_UPDATE or notification_type == NotificationType.ANOMALY_ALERT:
                await self._send_in_app_notification(user_id, notification_payload)
            
            if notification_type == NotificationType.EMAIL and email:
                await self._send_email_notification(email, title, message, metadata)
            
            if notification_type == NotificationType.SMS and phone:
                await self._send_sms_notification(phone, message)
            
            if notification_type == NotificationType.WEBHOOK and webhook_url:
                await self._send_webhook_notification(webhook_url, notification_payload)
            
            await self._save_notification_record(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type.value,
                priority=priority.value,
                metadata=metadata
            )
            
            logger.info(f"✅ 通知已发送: {user_id}, 类型: {notification_type.value}, 标题: {title}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 发送通知数据错误: {e}", exc_info=True)
        except (OSError, IOError) as e:
            logger.error(f"❌ 发送通知IO错误: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ 发送通知失败: {e}", exc_info=True)

    async def _send_in_app_notification(self, user_id: str, payload: Dict[str, Any]):
        """发送应用内通知"""
        try:
            await group_chat_ws_manager.send_personal_notification(
                user_id,
                payload
            )
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 应用内通知发送数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 应用内通知发送IO错误: {e}")
        except Exception as e:
            logger.error(f"❌ 应用内通知发送失败: {e}")

    async def _send_email_notification(
        self,
        email: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """发送邮件通知"""
        try:
            from app.services.email_service import email_service
            
            html_content = f"""
            <html>
            <body>
                <h2>{title}</h2>
                <p>{message}</p>
                {self._format_metadata_html(metadata)}
                <hr>
                <p style="color: #666; font-size: 12px;">
                    此邮件由智能税务系统自动发送，请勿回复。<br>
                    发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </body>
            </html>
            """
            
            await email_service.send_email(
                to_email=email,
                subject=title,
                html_content=html_content
            )
            
            logger.info(f"✅ 邮件通知已发送: {email}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 邮件通知发送数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 邮件通知发送IO错误: {e}")
        except Exception as e:
            logger.error(f"❌ 邮件通知发送失败: {e}")

    async def _send_sms_notification(self, phone: str, message: str):
        """发送短信通知"""
        try:
            from app.services.sms_service import sms_service
            
            await sms_service.send_sms(
                phone_number=phone,
                message=message[:200]
            )
            
            logger.info(f"✅ 短信通知已发送: {phone}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 短信通知发送数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 短信通知发送IO错误: {e}")
        except Exception as e:
            logger.error(f"❌ 短信通知发送失败: {e}")

    async def _send_webhook_notification(self, webhook_url: str, payload: Dict[str, Any]):
        """发送Webhook通知"""
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                
            logger.info(f"✅ Webhook通知已发送: {webhook_url}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Webhook通知发送数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ Webhook通知发送IO错误: {e}")
        except Exception as e:
            logger.error(f"❌ Webhook通知发送失败: {e}")

    def _format_metadata_html(self, metadata: Optional[Dict[str, Any]]) -> str:
        """格式化元数据为HTML"""
        if not metadata:
            return ""
        
        html = "<h3>详细信息</h3><ul>"
        for key, value in metadata.items():
            html += f"<li><strong>{key}:</strong> {value}</li>"
        html += "</ul>"
        
        return html

    async def _save_notification_record(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str,
        priority: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """保存通知记录到数据库"""
        try:
            if not self.redis:
                return
            
            notification_key = f"notification:user:{user_id}"
            notification_record = {
                "title": title,
                "message": message,
                "type": notification_type,
                "priority": priority,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat(),
                "read": False
            }
            
            self.redis.client.lpush(
                notification_key,
                json.dumps(notification_record)
            )
            self.redis.client.expire(notification_key, 604800)
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 保存通知记录数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 保存通知记录IO错误: {e}")
        except Exception as e:
            logger.error(f"❌ 保存通知记录失败: {e}")

    async def handle_high_risk_operation(
        self,
        user_id: str,
        tenant_id: str,
        session_id: str,
        user_query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理高风险操作的主要入口
        
        检测风险 -> 创建审批 -> 通知管理员 -> 记录日志
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            session_id: 会话ID
            user_query: 用户查询
            context: 附加上下文
            
        Returns:
            处理结果
        """
        risk_level, detected_behaviors = await self.detect_risk_level(
            user_query, context
        )
        
        if risk_level == RiskLevel.LOW:
            return {
                "status": "approved",
                "risk_level": risk_level.value,
                "message": "风险级别低，无需审批"
            }
        
        hitl_request = await self.create_hitl_request(
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            user_query=user_query,
            risk_level=risk_level,
            detected_behaviors=detected_behaviors,
            context=context
        )
        
        behavior_names = [b.value for b in detected_behaviors]
        title = f"⚠️ 高风险操作需要审批"
        message = f"用户 {user_id} 触发了高风险操作: {', '.join(behavior_names)}"
        
        await self.notify_admins(
            tenant_id=tenant_id,
            notification_type="hitl_approval_required",
            title=title,
            message=message,
            metadata={
                "approval_id": hitl_request["approval_id"],
                "risk_level": risk_level.value,
                "behaviors": behavior_names,
                "user_query": user_query[:200]
            }
        )
        
        await self.log_security_event(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type="high_risk_operation_request",
            severity=risk_level.value,
            details={
                "query": user_query,
                "risk_level": risk_level.value,
                "behaviors": behavior_names,
                "approval_id": hitl_request["approval_id"]
            }
        )
        
        return {
            "status": "pending_approval",
            "approval_id": hitl_request["approval_id"],
            "risk_level": risk_level.value,
            "detected_behaviors": behavior_names,
            "message": f"操作已挂起，等待管理员审批"
        }


admin_notification_service = AdminNotificationService()
