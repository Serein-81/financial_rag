"""
政策推送工作流监控集成模块

将政策推送工作流与第一阶段创建的WorkflowMonitor集成：
1. 自动追踪政策推送工作流执行
2. 政策匹配追踪
3. 通知发送追踪
4. 订阅管理追踪
5. 错误追踪和告警
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime
from enum import Enum

from app.workflow import (
    WorkflowMonitor,
    WorkflowConfig,
    NodeType,
)
from app.workflow.human_review_tracker import (
    HumanReviewTracker,
    ReviewAction,
    ReviewPriority,
)

logger = logging.getLogger(__name__)


class PolicyMatchLevel(str, Enum):
    """政策匹配等级"""
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NotificationChannel(str, Enum):
    """通知渠道"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    SSE = "sse"
    PUSH = "push"


class PolicyWorkflowMonitor:
    """
    政策推送工作流监控器
    
    集成WorkflowMonitor和HumanReviewTracker，提供政策推送工作流的完整监控能力。
    
    工作流节点：
    1. policy_collection - 政策采集
    2. policy_parsing - 政策解析
    3. enterprise_matching - 企业匹配
    4. match_scoring - 匹配评分
    5. notification_preparation - 通知准备
    6. notification_sending - 通知发送
    7. subscription_management - 订阅管理
    8. policy_update_detection - 政策更新检测
    
    支持功能：
    - 工作流级别追踪
    - 节点级别追踪
    - 政策匹配追踪
    - 通知发送追踪
    - 订阅管理追踪
    - 人工审核追踪
    - 错误追踪
    - Token使用统计
    """
    
    def __init__(self, db_session):
        """
        初始化政策工作流监控器
        
        Args:
            db_session: 数据库会话
        """
        self.db_session = db_session
        self.workflow_monitor = WorkflowMonitor(db_session)
        self.human_review_tracker = HumanReviewTracker(db_session)
        
        self.current_workflow_trace_id: Optional[str] = None
        self.current_policy_id: Optional[str] = None
        self.current_enterprise_id: Optional[str] = None
        
        logger.info("✅ 政策推送工作流监控器初始化完成")
    
    def start_workflow(
        self,
        policy_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        total_nodes: int = 8,
        workflow_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        启动政策推送工作流追踪
        
        Args:
            policy_id: 政策ID
            tenant_id: 租户ID
            user_id: 用户ID
            total_nodes: 总节点数
            workflow_metadata: 额外元数据
            
        Returns:
            str: 工作流追踪ID
        """
        self.current_policy_id = policy_id
        
        metadata = workflow_metadata or {}
        metadata["policy_id"] = policy_id
        
        config = WorkflowConfig(
            workflow_type="policy_notification",
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=metadata
        )
        
        self.current_workflow_trace_id = self.workflow_monitor.start_workflow(
            config=config,
            total_nodes=total_nodes
        )
        
        logger.info(f"📋 启动政策推送工作流追踪: {self.current_workflow_trace_id}")
        
        return self.current_workflow_trace_id
    
    def start_node(
        self,
        node_name: str,
        node_type: NodeType = NodeType.NORMAL,
        policy_id: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        启动节点追踪
        
        Args:
            node_name: 节点名称
            node_type: 节点类型
            policy_id: 政策ID
            enterprise_id: 企业ID
            input_data: 输入数据
            
        Returns:
            Optional[str]: 节点执行ID
        """
        if not self.current_workflow_trace_id:
            logger.warning("⚠️ 未启动工作流追踪，忽略节点追踪")
            return None
        
        if policy_id:
            self.current_policy_id = policy_id
        if enterprise_id:
            self.current_enterprise_id = enterprise_id
        
        node_type_str = node_type.value if hasattr(node_type, 'value') else str(node_type)
        
        node_execution_id = self.workflow_monitor.start_node(
            workflow_trace_id=self.current_workflow_trace_id,
            node_name=node_name,
            node_type=node_type_str,
            execution_order=self._get_node_order(node_name),
            input_data=input_data
        )
        
        logger.debug(f"🔄 启动节点追踪: {node_name} - {node_execution_id}")
        
        return node_execution_id
    
    def complete_node(
        self,
        node_name: str,
        output_data: Optional[Dict[str, Any]] = None,
        token_usage: Optional[Dict[str, Any]] = None
    ):
        """
        完成节点追踪
        
        Args:
            node_name: 节点名称
            output_data: 输出数据
            token_usage: Token使用统计
        """
        if not self.current_workflow_trace_id:
            logger.warning("⚠️ 未启动工作流追踪，忽略节点完成")
            return
        
        try:
            self.workflow_monitor.complete_node(
                workflow_trace_id=self.current_workflow_trace_id,
                node_name=node_name,
                output_data=output_data,
                token_usage=token_usage
            )
            logger.debug(f"✅ 完成节点追踪: {node_name}")
        except Exception as e:
            logger.error(f"❌ 完成节点追踪失败: {e}", exc_info=True)
    
    def record_policy_collection(
        self,
        policy_id: str,
        source: str,
        collection_count: int = 1,
        is_update: bool = False
    ):
        """
        记录政策采集
        
        Args:
            policy_id: 政策ID
            source: 采集来源
            collection_count: 采集数量
            is_update: 是否为更新
        """
        node_name = "policy_collection"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.AGENT,
            input_data={
                "policy_id": policy_id,
                "source": source,
                "is_update": is_update
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "collected": collection_count,
                "source": source,
                "is_update": is_update
            }
        )
        
        logger.info(f"📥 政策采集记录: {policy_id} (来源: {source})")
    
    def record_policy_parsing(
        self,
        policy_id: str,
        parsed_fields: List[str],
        extraction_success: bool = True
    ):
        """
        记录政策解析
        
        Args:
            policy_id: 政策ID
            parsed_fields: 解析的字段列表
            extraction_success: 提取是否成功
        """
        node_name = "policy_parsing"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.AGENT,
            policy_id=policy_id,
            input_data={
                "policy_id": policy_id,
                "fields_to_parse": parsed_fields
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "parsed_fields": parsed_fields,
                "extraction_success": extraction_success,
                "field_count": len(parsed_fields)
            }
        )
        
        logger.info(f"📝 政策解析记录: {policy_id} (解析字段: {len(parsed_fields)})")
    
    def record_enterprise_matching(
        self,
        policy_id: str,
        enterprise_id: str,
        match_score: float,
        match_level: PolicyMatchLevel,
        match_criteria: Dict[str, Any],
        match_reasons: List[str]
    ):
        """
        记录企业匹配
        
        Args:
            policy_id: 政策ID
            enterprise_id: 企业ID
            match_score: 匹配分数
            match_level: 匹配等级
            match_criteria: 匹配标准
            match_reasons: 匹配原因
        """
        node_name = "enterprise_matching"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.AGENT,
            policy_id=policy_id,
            enterprise_id=enterprise_id,
            input_data={
                "policy_id": policy_id,
                "enterprise_id": enterprise_id,
                "match_criteria": match_criteria
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "match_score": match_score,
                "match_level": match_level.value,
                "match_reasons": match_reasons,
                "matched": match_score >= 0.6
            }
        )
        
        logger.info(
            f"🎯 企业匹配记录: {enterprise_id} - {policy_id} "
            f"(分数: {match_score:.2f}, 等级: {match_level.value})"
        )
    
    def record_match_scoring(
        self,
        policy_id: str,
        enterprise_id: str,
        industry_score: float,
        region_score: float,
        tax_type_score: float,
        scale_score: float,
        final_score: float
    ):
        """
        记录匹配评分
        
        Args:
            policy_id: 政策ID
            enterprise_id: 企业ID
            industry_score: 行业匹配分
            region_score: 地区匹配分
            tax_type_score: 税种匹配分
            scale_score: 规模匹配分
            final_score: 最终分数
        """
        node_name = "match_scoring"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.NORMAL,
            policy_id=policy_id,
            enterprise_id=enterprise_id
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "industry_score": industry_score,
                "region_score": region_score,
                "tax_type_score": tax_type_score,
                "scale_score": scale_score,
                "final_score": final_score,
                "weights": {
                    "industry": 0.4,
                    "region": 0.2,
                    "tax_type": 0.3,
                    "scale": 0.1
                }
            }
        )
        
        logger.debug(f"📊 匹配评分记录: {final_score:.2f}")
    
    def record_notification_preparation(
        self,
        policy_id: str,
        enterprise_id: str,
        notification_channels: List[NotificationChannel],
        notification_content: Dict[str, Any],
        priority: str = "normal"
    ):
        """
        记录通知准备
        
        Args:
            policy_id: 政策ID
            enterprise_id: 企业ID
            notification_channels: 通知渠道列表
            notification_content: 通知内容
            priority: 优先级
        """
        node_name = "notification_preparation"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.NORMAL,
            policy_id=policy_id,
            enterprise_id=enterprise_id,
            input_data={
                "policy_id": policy_id,
                "channels": [ch.value for ch in notification_channels],
                "priority": priority
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "channels_prepared": [ch.value for ch in notification_channels],
                "content_length": len(str(notification_content)),
                "priority": priority
            }
        )
        
        logger.debug(f"📋 通知准备记录: {len(notification_channels)} 个渠道")
    
    def record_notification_sending(
        self,
        policy_id: str,
        enterprise_id: str,
        channel: NotificationChannel,
        sent: bool,
        sent_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ):
        """
        记录通知发送
        
        Args:
            policy_id: 政策ID
            enterprise_id: 企业ID
            channel: 通知渠道
            sent: 是否发送成功
            sent_at: 发送时间
            error_message: 错误信息
        """
        node_name = "notification_sending"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.NORMAL,
            policy_id=policy_id,
            enterprise_id=enterprise_id,
            input_data={
                "policy_id": policy_id,
                "channel": channel.value
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "channel": channel.value,
                "sent": sent,
                "sent_at": sent_at.isoformat() if sent_at else None,
                "error_message": error_message
            }
        )
        
        if sent:
            logger.info(f"📤 通知发送成功: {enterprise_id} - {channel.value}")
        else:
            logger.warning(f"⚠️ 通知发送失败: {enterprise_id} - {channel.value} - {error_message}")
    
    def record_subscription_management(
        self,
        subscription_id: str,
        action: str,
        tenant_id: str,
        categories: List[str],
        channels: List[str],
        success: bool = True
    ):
        """
        记录订阅管理
        
        Args:
            subscription_id: 订阅ID
            action: 操作类型 (create/update/delete)
            tenant_id: 租户ID
            categories: 订阅类别
            channels: 通知渠道
            success: 是否成功
        """
        node_name = "subscription_management"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.NORMAL,
            input_data={
                "subscription_id": subscription_id,
                "action": action,
                "tenant_id": tenant_id,
                "categories": categories,
                "channels": channels
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "action": action,
                "success": success,
                "categories_count": len(categories),
                "channels_count": len(channels)
            }
        )
        
        logger.info(f"🔧 订阅管理记录: {action} - {subscription_id}")
    
    def record_policy_update_detection(
        self,
        policy_id: str,
        update_type: str,
        affected_enterprises: List[str],
        notification_sent: bool
    ):
        """
        记录政策更新检测
        
        Args:
            policy_id: 政策ID
            update_type: 更新类型
            affected_enterprises: 受影响企业列表
            notification_sent: 是否发送通知
        """
        node_name = "policy_update_detection"
        
        self.start_node(
            node_name=node_name,
            node_type=NodeType.AGENT,
            policy_id=policy_id,
            input_data={
                "policy_id": policy_id,
                "update_type": update_type,
                "affected_count": len(affected_enterprises)
            }
        )
        
        self.complete_node(
            node_name=node_name,
            output_data={
                "update_type": update_type,
                "affected_enterprises_count": len(affected_enterprises),
                "notification_sent": notification_sent
            }
        )
        
        logger.info(
            f"🔔 政策更新检测记录: {policy_id} "
            f"(类型: {update_type}, 影响: {len(affected_enterprises)} 个企业)"
        )
    
    def start_human_review(
        self,
        review_type: str,
        review_reason: str,
        policy_id: Optional[str] = None,
        enterprise_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        priority: ReviewPriority = ReviewPriority.NORMAL
    ) -> Optional[str]:
        """
        启动人工审核追踪
        
        Args:
            review_type: 审核类型
            review_reason: 审核原因
            policy_id: 政策ID
            enterprise_id: 企业ID
            requester_id: 请求者ID
            priority: 优先级
            
        Returns:
            Optional[str]: 追踪ID
        """
        import asyncio
        
        try:
            tracking_id = asyncio.run(
                self.human_review_tracker.create_review_tracking(
                    review_type=review_type,
                    review_reason=review_reason,
                    requester_id=requester_id,
                    priority=priority
                )
            )
            
            logger.info(f"🔍 启动人工审核: {review_type} - {tracking_id}")
            
            return tracking_id
            
        except Exception as e:
            logger.error(f"❌ 启动人工审核追踪失败: {e}", exc_info=True)
            return None
    
    def record_review_action(
        self,
        tracking_id: str,
        action: ReviewAction,
        reviewer_id: Optional[str] = None,
        comment: Optional[str] = None
    ):
        """
        记录审核动作
        
        Args:
            tracking_id: 追踪ID
            action: 审核动作
            reviewer_id: 审核者ID
            comment: 审核意见
        """
        import asyncio
        
        try:
            asyncio.run(
                self.human_review_tracker.record_action(
                    tracking_id=tracking_id,
                    action=action,
                    reviewer_id=reviewer_id,
                    comment=comment
                )
            )
            
            logger.debug(f"✅ 记录审核动作: {action.value} by {reviewer_id}")
            
        except Exception as e:
            logger.error(f"❌ 记录审核动作失败: {e}", exc_info=True)
    
    def record_error(
        self,
        node_name: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """
        记录错误
        
        Args:
            node_name: 节点名称
            error_message: 错误信息
            error_details: 错误详情
        """
        if not self.current_workflow_trace_id:
            logger.warning("⚠️ 未启动工作流追踪，忽略错误记录")
            return
        
        try:
            self.workflow_monitor.record_node_error(
                workflow_trace_id=self.current_workflow_trace_id,
                node_name=node_name,
                error_message=error_message,
                error_details=error_details
            )
            
            logger.error(f"❌ 记录工作流错误: {node_name} - {error_message}")
            
        except Exception as e:
            logger.error(f"❌ 记录错误失败: {e}", exc_info=True)
    
    def complete_workflow(
        self,
        status: str = "completed",
        error_message: Optional[str] = None,
        matched_count: int = 0,
        notified_count: int = 0
    ):
        """
        完成工作流追踪
        
        Args:
            status: 工作流状态
            error_message: 错误信息
            matched_count: 匹配企业数
            notified_count: 通知发送数
        """
        if not self.current_workflow_trace_id:
            logger.warning("⚠️ 未启动工作流追踪，忽略工作流完成")
            return
        
        try:
            workflow_metadata = {
                "matched_enterprises": matched_count,
                "notified_enterprises": notified_count,
                "policy_id": self.current_policy_id
            }
            
            self.workflow_monitor.complete_workflow(
                workflow_trace_id=self.current_workflow_trace_id,
                status=status,
                error_message=error_message,
                workflow_metadata=workflow_metadata
            )
            
            logger.info(
                f"🏁 完成政策推送工作流: {self.current_workflow_trace_id} "
                f"(状态: {status}, 匹配: {matched_count}, 通知: {notified_count})"
            )
            
            self.current_workflow_trace_id = None
            self.current_policy_id = None
            self.current_enterprise_id = None
            
        except Exception as e:
            logger.error(f"❌ 完成工作流追踪失败: {e}", exc_info=True)
    
    def get_execution_summary(
        self,
        workflow_trace_id: str
    ) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Args:
            workflow_trace_id: 工作流追踪ID
            
        Returns:
            Dict: 执行摘要
        """
        try:
            trace = self.workflow_monitor.get_workflow_execution_trace(
                workflow_trace_id
            )
            
            if not trace:
                return {}
            
            total_time = 0.0
            node_stats = {}
            
            for node in trace.node_executions:
                if node.execution_time_ms:
                    total_time += node.execution_time_ms
                
                node_stats[node.node_name] = {
                    "status": node.status,
                    "execution_time_ms": node.execution_time_ms,
                    "token_usage": node.token_usage
                }
            
            return {
                "workflow_trace_id": str(trace.id),
                "workflow_type": trace.workflow_type,
                "status": trace.status,
                "created_at": trace.created_at.isoformat() if trace.created_at else None,
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                "total_execution_time_ms": total_time,
                "matched_enterprises": trace.workflow_metadata.get("matched_enterprises", 0) if trace.workflow_metadata else 0,
                "notified_enterprises": trace.workflow_metadata.get("notified_enterprises", 0) if trace.workflow_metadata else 0,
                "node_count": len(trace.node_executions),
                "node_stats": node_stats
            }
            
        except Exception as e:
            logger.error(f"❌ 获取执行摘要失败: {e}", exc_info=True)
            return {}
    
    def _get_node_order(self, node_name: str) -> int:
        """
        获取节点执行顺序
        
        Args:
            node_name: 节点名称
            
        Returns:
            int: 节点顺序
        """
        node_order_map = {
            "policy_collection": 1,
            "policy_parsing": 2,
            "enterprise_matching": 3,
            "match_scoring": 4,
            "notification_preparation": 5,
            "notification_sending": 6,
            "subscription_management": 7,
            "policy_update_detection": 8
        }
        return node_order_map.get(node_name, 0)


def create_policy_workflow_monitor(db_session) -> PolicyWorkflowMonitor:
    """
    创建政策推送工作流监控器实例
    
    由于监控器需要数据库会话，不提供全局单例。
    使用此工厂函数为每个请求创建新的实例。
    
    Args:
        db_session: 数据库会话
    
    Returns:
        PolicyWorkflowMonitor: 新的监控器实例
    """
    return PolicyWorkflowMonitor(db_session)
