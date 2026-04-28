"""
任务分解器 (Task Decomposer)
负责分析文档类型并分解审查任务
"""

import logging
from typing import List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """文档类型"""
    FINANCIAL_STATEMENT = "financial_statement"
    TAX_RETURN = "tax_return"
    CONTRACT = "contract"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    LEGAL_DOCUMENT = "legal_document"
    UNKNOWN = "unknown"


class AuditPriority(str, Enum):
    """审查优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskDecomposer:
    """
    任务分解器
    
    功能：
    1. 识别文档类型
    2. 确定审查类型
    3. 分配优先级
    4. 生成任务计划
    """
    
    def __init__(self):
        """初始化任务分解器"""
        # 文档类型关键词映射
        self.document_keywords = {
            DocumentType.FINANCIAL_STATEMENT: [
                "资产负债表", "利润表", "现金流量表", "财务报表", "balance sheet",
                "income statement", "cash flow", "financial statement"
            ],
            DocumentType.TAX_RETURN: [
                "税务申报", "纳税申报表", "增值税", "企业所得税", "tax return",
                "tax declaration", "vat", "income tax"
            ],
            DocumentType.CONTRACT: [
                "合同", "协议", "contract", "agreement", "条款", "甲方", "乙方",
                "签署", "签订", "terms", "conditions"
            ],
            DocumentType.INVOICE: [
                "发票", "invoice", "开票", "税号", "发票号码", "invoice number",
                "billing", "税务发票"
            ],
            DocumentType.RECEIPT: [
                "收据", "receipt", "收款", "付款", "凭证", "voucher"
            ],
            DocumentType.BANK_STATEMENT: [
                "银行对账单", "bank statement", "账户余额", "交易记录",
                "转账", "存款", "取款", "balance", "transaction"
            ],
            DocumentType.LEGAL_DOCUMENT: [
                "法律文件", "legal document", "判决书", "裁定书", "起诉书",
                "律师函", "法院", "court", "legal notice"
            ]
        }
        
        # 审查类型映射
        self.audit_type_mapping = {
            DocumentType.FINANCIAL_STATEMENT: ["finance"],
            DocumentType.TAX_RETURN: ["tax", "finance"],
            DocumentType.CONTRACT: ["legal", "finance"],
            DocumentType.INVOICE: ["tax", "finance"],
            DocumentType.RECEIPT: ["finance"],
            DocumentType.BANK_STATEMENT: ["finance"],
            DocumentType.LEGAL_DOCUMENT: ["legal"]
        }
        
        # 优先级映射
        self.priority_mapping = {
            DocumentType.FINANCIAL_STATEMENT: AuditPriority.HIGH,
            DocumentType.TAX_RETURN: AuditPriority.HIGH,
            DocumentType.CONTRACT: AuditPriority.MEDIUM,
            DocumentType.INVOICE: AuditPriority.MEDIUM,
            DocumentType.RECEIPT: AuditPriority.LOW,
            DocumentType.BANK_STATEMENT: AuditPriority.MEDIUM,
            DocumentType.LEGAL_DOCUMENT: AuditPriority.HIGH,
            DocumentType.UNKNOWN: AuditPriority.LOW
        }
        
        logger.debug("Task decomposer initialized")
    
    def decompose(
        self,
        documents: List[Dict[str, Any]],
        requested_audit_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        分解审查任务
        
        Args:
            documents: 文档列表
            requested_audit_type: 请求的审查类型
            
        Returns:
            任务分解结果
        """
        print(f"📋 [任务分解器] 开始分解任务，文档数量: {len(documents)}")
        
        # 1. 识别文档类型
        document_analysis = []
        for doc in documents:
            doc_type = self._identify_document_type(doc)
            priority = self.priority_mapping.get(doc_type, AuditPriority.LOW)
            
            document_analysis.append({
                "document_id": doc.get("id"),
                "document_type": doc_type.value,
                "priority": priority.value,
                "content_length": len(doc.get("content", "")),
                "filename": doc.get("filename", "unknown")
            })
        
        # 2. 确定需要的审查类型
        required_audit_types = self._determine_audit_types(
            document_analysis, requested_audit_type
        )
        
        # 3. 生成任务计划
        task_plan = self._generate_task_plan(
            document_analysis, required_audit_types
        )
        
        # 4. 计算预估时间
        estimated_time = self._estimate_execution_time(document_analysis)
        
        result = {
            "document_analysis": document_analysis,
            "required_audit_types": required_audit_types,
            "task_plan": task_plan,
            "estimated_time_seconds": estimated_time,
            "total_documents": len(documents),
            "high_priority_documents": len([
                d for d in document_analysis 
                if d["priority"] == AuditPriority.HIGH.value
            ])
        }
        
        print("✅ [任务分解器] 任务分解完成")
        print(f"   - 需要审查类型: {', '.join(required_audit_types)}")
        print(f"   - 高优先级文档: {result['high_priority_documents']} 个")
        print(f"   - 预估时间: {estimated_time} 秒")
        
        return result
    
    def _identify_document_type(self, document: Dict[str, Any]) -> DocumentType:
        """
        识别文档类型
        
        Args:
            document: 文档信息
            
        Returns:
            文档类型
        """
        content = document.get("content", "").lower()
        filename = document.get("filename", "").lower()
        
        # 组合文本（内容 + 文件名）
        combined_text = f"{content} {filename}"
        
        # 计算每种类型的匹配分数
        type_scores = {}
        for doc_type, keywords in self.document_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    score += 1
            type_scores[doc_type] = score
        
        # 找到最高分的类型
        best_type = max(type_scores, key=type_scores.get)
        best_score = type_scores[best_type]
        
        # 如果分数太低，返回 UNKNOWN
        if best_score == 0:
            return DocumentType.UNKNOWN
        
        return best_type
    
    def _determine_audit_types(
        self,
        document_analysis: List[Dict[str, Any]],
        requested_audit_type: str
    ) -> List[str]:
        """
        确定需要的审查类型
        
        Args:
            document_analysis: 文档分析结果
            requested_audit_type: 请求的审查类型
            
        Returns:
            审查类型列表
        """
        if requested_audit_type == "comprehensive":
            # 综合审查：根据文档类型确定
            required_types = set()
            for doc in document_analysis:
                doc_type = DocumentType(doc["document_type"])
                audit_types = self.audit_type_mapping.get(doc_type, [])
                required_types.update(audit_types)
            return list(required_types)
        else:
            # 指定类型审查
            return [requested_audit_type]
    
    def _generate_task_plan(
        self,
        document_analysis: List[Dict[str, Any]],
        required_audit_types: List[str]
    ) -> Dict[str, Any]:
        """
        生成任务计划
        
        Args:
            document_analysis: 文档分析结果
            required_audit_types: 需要的审查类型
            
        Returns:
            任务计划
        """
        # 按优先级排序文档
        sorted_docs = sorted(
            document_analysis,
            key=lambda x: {
                AuditPriority.HIGH.value: 3,
                AuditPriority.MEDIUM.value: 2,
                AuditPriority.LOW.value: 1
            }.get(x["priority"], 0),
            reverse=True
        )
        
        # 为每个审查类型分配文档
        agent_assignments = {}
        for audit_type in required_audit_types:
            relevant_docs = []
            for doc in sorted_docs:
                doc_type = DocumentType(doc["document_type"])
                if audit_type in self.audit_type_mapping.get(doc_type, []):
                    relevant_docs.append(doc["document_id"])
            
            agent_assignments[f"{audit_type}_agent"] = {
                "documents": relevant_docs,
                "priority": self._calculate_agent_priority(relevant_docs, document_analysis),
                "estimated_time": self._estimate_agent_time(relevant_docs, document_analysis)
            }
        
        return {
            "execution_order": self._determine_execution_order(agent_assignments),
            "agent_assignments": agent_assignments,
            "parallel_execution": len(required_audit_types) > 1
        }
    
    def _calculate_agent_priority(
        self,
        document_ids: List[str],
        document_analysis: List[Dict[str, Any]]
    ) -> str:
        """计算 Agent 优先级"""
        doc_priorities = []
        for doc in document_analysis:
            if doc["document_id"] in document_ids:
                doc_priorities.append(doc["priority"])
        
        if not doc_priorities:
            return AuditPriority.LOW.value
        
        # 如果有高优先级文档，Agent 优先级为高
        if AuditPriority.HIGH.value in doc_priorities:
            return AuditPriority.HIGH.value
        elif AuditPriority.MEDIUM.value in doc_priorities:
            return AuditPriority.MEDIUM.value
        else:
            return AuditPriority.LOW.value
    
    def _estimate_agent_time(
        self,
        document_ids: List[str],
        document_analysis: List[Dict[str, Any]]
    ) -> int:
        """估算 Agent 执行时间（秒）"""
        total_time = 0
        for doc in document_analysis:
            if doc["document_id"] in document_ids:
                # 基于内容长度估算时间
                content_length = doc["content_length"]
                base_time = 30  # 基础时间 30 秒
                content_time = content_length // 1000 * 5  # 每 1000 字符 5 秒
                total_time += base_time + content_time
        
        return total_time
    
    def _determine_execution_order(
        self,
        agent_assignments: Dict[str, Any]
    ) -> List[str]:
        """确定执行顺序"""
        # 按优先级排序
        agents_with_priority = [
            (agent, info["priority"])
            for agent, info in agent_assignments.items()
        ]
        
        agents_with_priority.sort(
            key=lambda x: {
                AuditPriority.HIGH.value: 3,
                AuditPriority.MEDIUM.value: 2,
                AuditPriority.LOW.value: 1
            }.get(x[1], 0),
            reverse=True
        )
        
        return [agent for agent, _ in agents_with_priority]
    
    def _estimate_execution_time(
        self,
        document_analysis: List[Dict[str, Any]]
    ) -> int:
        """
        估算总执行时间
        
        Args:
            document_analysis: 文档分析结果
            
        Returns:
            预估时间（秒）
        """
        total_time = 0
        
        for doc in document_analysis:
            # 基础处理时间
            base_time = 30
            
            # 基于内容长度的时间
            content_length = doc["content_length"]
            content_time = content_length // 1000 * 5  # 每 1000 字符 5 秒
            
            # 基于优先级的时间调整
            priority_multiplier = {
                AuditPriority.HIGH.value: 1.5,
                AuditPriority.MEDIUM.value: 1.2,
                AuditPriority.LOW.value: 1.0
            }.get(doc["priority"], 1.0)
            
            doc_time = (base_time + content_time) * priority_multiplier
            total_time += doc_time
        
        # 并行执行可以减少总时间
        # 假设最多 3 个 Agent 并行
        parallel_factor = 0.6  # 并行效率 60%
        total_time = int(total_time * parallel_factor)
        
        return total_time
    
    def get_document_type_stats(
        self,
        document_analysis: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        获取文档类型统计
        
        Args:
            document_analysis: 文档分析结果
            
        Returns:
            文档类型统计
        """
        stats = {}
        for doc in document_analysis:
            doc_type = doc["document_type"]
            stats[doc_type] = stats.get(doc_type, 0) + 1
        
        return stats
