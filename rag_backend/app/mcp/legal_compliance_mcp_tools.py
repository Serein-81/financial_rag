"""
法律合规 MCP 工具集

提供 Agent 可调用的法律合规工具
包含合同条款提取、合规校验和实体风险追踪

工具类型：本地 STDIO（访问本地数据库和图数据库）
"""

import json
import logging
from typing import Dict, Any, List, Optional

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)


@local_tool(
    description="从合同审核报告中精确提取特定类型的法律条款原文，用于深度审查和风险评估"
)
async def extract_contract_clauses(
    tenant_id: str,
    report_id: str,
    clause_category: str = "all"
) -> Dict[str, Any]:
    """
    从合同审核报告中提取特定类型的法律条款原文

    利用结构化书签精确提取，避免"Lost in the Middle"现象。
    支持提取违约责任、不可抗力、管辖权、支付条款等关键条款。

    Args:
        tenant_id: 租户ID，必填，用于数据隔离
        report_id: 合同审核报告ID，必填
        clause_category: 条款类型，可选值：
            - "all": 所有条款
            - "breach_of_contract": 违约责任条款
            - "force_majeure": 不可抗力条款
            - "jurisdiction": 管辖权条款
            - "payment_terms": 支付条款
            - "termination": 终止条款
            - "confidentiality": 保密条款
            - "ip_ownership": 知识产权条款
            - "liability": 赔偿责任条款

    Returns:
        包含提取结果和元数据的字典

    Example:
        extract_contract_clauses(
            tenant_id="xxx",
            report_id="yyy",
            clause_category="breach_of_contract"
        )
    """
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import select, and_
        from app.models.contract_review import ContractClause

        clause_type_mapping = {
            "breach_of_contract": "breach",
            "force_majeure": "force_majeure",
            "jurisdiction": "jurisdiction",
            "payment_terms": "payment",
            "termination": "termination",
            "confidentiality": "confidentiality",
            "ip_ownership": "ip",
            "liability": "liability"
        }

        async with async_session_maker() as session:
            if clause_category == "all":
                stmt = select(ContractClause).where(
                    and_(
                        ContractClause.report_id == report_id
                    )
                )
            else:
                mapped_type = clause_type_mapping.get(clause_category, clause_category)
                stmt = select(ContractClause).where(
                    and_(
                        ContractClause.report_id == report_id,
                        ContractClause.clause_type == mapped_type
                    )
                )

            result = await session.execute(stmt)
            clauses = result.scalars().all()

            if not clauses:
                return {
                    "status": "warning",
                    "message": f"在该合同中未匹配到 {clause_category} 相关条款",
                    "clause_category": clause_category,
                    "report_id": report_id,
                    "clauses": [],
                    "count": 0,
                    "suggestion": "请检查合同是否包含此类条款，或尝试提取 'all' 查看所有已识别的条款"
                }

            clauses_data = []
            for clause in clauses:
                clauses_data.append({
                    "id": str(clause.id),
                    "clause_type": clause.clause_type,
                    "clause_title": clause.clause_title,
                    "clause_text": clause.clause_text,
                    "risk_level": clause.risk_level.value if clause.risk_level else "unknown",
                    "risk_description": clause.risk_description
                })

            return {
                "status": "success",
                "report_id": report_id,
                "clause_category": clause_category,
                "clauses": clauses_data,
                "count": len(clauses_data),
                "message": f"成功提取 {len(clauses_data)} 条 {clause_category} 相关条款"
            }

    except Exception as e:
        logger.error(f"提取合同条款失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "clause_category": clause_category,
            "report_id": report_id,
            "clauses": [],
            "count": 0
        }


@local_tool(
    description="利用知识图谱进行股权穿透和风险关联分析，追踪目标企业的实际控制人和关联交易方"
)
async def trace_entity_risk_network(
    tenant_id: str,
    entity_name: str,
    penetration_depth: int = 3
) -> Dict[str, Any]:
    """
    利用图谱数据库进行股权穿透和风险追踪

    追踪目标企业背后隐藏的关联交易方、实际控制人，
    以及整个关系网中的涉诉、违规记录。

    Args:
        tenant_id: 租户ID，必填
        entity_name: 目标企业全称，必填
        penetration_depth: 穿透层级深度，默认3层

    Returns:
        包含关系网络和风险事件的字典

    Example:
        trace_entity_risk_network(
            tenant_id="xxx",
            entity_name="阿里巴巴（中国）有限公司",
            penetration_depth=3
        )
    """
    try:
        from app.knowledge_graph.neo4j_manager import Neo4jManager

        neo4j_mgr = Neo4jManager()

        if not neo4j_mgr.driver:
            return {
                "status": "error",
                "error": "Neo4j 图数据库未连接或未启用",
                "entity_name": entity_name,
                "message": "请检查 Neo4j 配置是否正确"
            }

        relationships = []
        risk_events = []

        try:
            with neo4j_mgr.driver.session() as session:
                cypher_query = """
                    MATCH (target:Entity {name: $entity_name, tenant_id: $tenant_id})
                    CALL {
                        WITH target
                        MATCH path = (target)-[r:RELATED*1..%d]-(related)
                        WHERE related.tenant_id IS NULL OR related.tenant_id = $tenant_id
                        RETURN path, nodes(path) as path_nodes, relationships(path) as rels
                        LIMIT 50
                    }
                    WITH target, path_nodes, rels
                    UNWIND path_nodes AS node
                    WITH target, node, rels
                    WHERE node <> target
                    WITH collect(DISTINCT {
                        name: node.name,
                        type: node.type,
                        properties: node.properties,
                        distance: size([x IN rels WHERE x <> target]) - 1
                    }) AS related_entities
                    RETURN related_entities
                """ % penetration_depth

                result = session.run(
                    cypher_query,
                    entity_name=entity_name,
                    tenant_id=tenant_id
                )
                records = result.data()

                if records:
                    for record in records:
                        related_entities = record.get("related_entities", [])
                        for entity in related_entities:
                            relationships.append({
                                "entity_name": entity.get("name"),
                                "entity_type": entity.get("type"),
                                "distance": entity.get("distance", 1)
                            })

        except Exception as graph_error:
            logger.warning(f"图查询失败，尝试备用查询: {graph_error}")

            try:
                with neo4j_mgr.driver.session() as session:
                    backup_query = """
                        MATCH (e:Entity {name: $entity_name})
                        WHERE e.tenant_id IS NULL OR e.tenant_id = $tenant_id
                        MATCH (e)-[r:RELATED]-(related)
                        WHERE related.tenant_id IS NULL OR related.tenant_id = $tenant_id
                        RETURN related.name AS name, 
                               related.type AS type,
                               related.properties AS properties,
                               1 AS distance
                        LIMIT 20
                    """
                    result = session.run(
                        backup_query,
                        entity_name=entity_name,
                        tenant_id=tenant_id
                    )
                    records = result.data()

                    for record in records:
                        relationships.append({
                            "entity_name": record.get("name"),
                            "entity_type": record.get("type"),
                            "distance": record.get("distance", 1)
                        })
            except Exception as backup_error:
                logger.error(f"备用图查询也失败: {backup_error}")

        unique_entities = {}
        for rel in relationships:
            name = rel["entity_name"]
            if name and name not in unique_entities:
                unique_entities[name] = rel

        unique_relationships = list(unique_entities.values())

        if not unique_relationships:
            return {
                "status": "warning",
                "message": f"在知识图谱中未找到 {entity_name} 的关联实体",
                "entity_name": entity_name,
                "penetration_depth": penetration_depth,
                "related_entities": [],
                "risk_events": [],
                "suggestion": "请确认企业实体已正确导入知识图谱，或尝试提供更完整的企业名称"
            }

        return {
            "status": "success",
            "entity_name": entity_name,
            "penetration_depth": penetration_depth,
            "related_entities": unique_relationships,
            "risk_events": risk_events,
            "total_related": len(unique_relationships),
            "message": f"成功追踪 {entity_name} 的 {len(unique_relationships)} 个关联实体"
        }

    except Exception as e:
        logger.error(f"追踪实体风险网络失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "entity_name": entity_name,
            "penetration_depth": penetration_depth,
            "related_entities": [],
            "risk_events": []
        }


@local_tool(
    description="将业务动作与法规库进行交叉比对，验证合规性并返回适用的法律条款原文"
)
async def verify_compliance_rule(
    tenant_id: str,
    action_summary: str,
    domain: str = "general"
) -> Dict[str, Any]:
    """
    合规性交叉比对引擎

    将业务动作与法规库进行比对，返回适用的法条原文。
    用于判断某个业务动作是否触碰法律红线。

    Args:
        tenant_id: 租户ID，必填
        action_summary: 业务动作摘要，必填
            示例：'收集欧洲用户的浏览记录'、'向个人发送营销短信'、'跨境传输用户数据'
        domain: 合规领域，可选值：
            - "gdpr": 通用数据保护条例（欧盟）
            - "privacy": 个人信息保护
            - "labor_law": 劳动法
            - "tax_evasion": 税务合规
            - "consumer_protection": 消费者权益保护
            - "anti_unfair_competition": 反不正当竞争
            - "general": 综合法规

    Returns:
        包含适用法规和合规建议的字典

    Example:
        verify_compliance_rule(
            tenant_id="xxx",
            action_summary="收集用户的位置信息和浏览历史",
            domain="privacy"
        )
    """
    try:
        from app.services.unified_retriever import UnifiedRetriever

        domain_keywords = {
            "gdpr": ["个人数据", "数据主体", "数据处理", "同意", "数据保护", "隐私", "欧盟"],
            "privacy": ["个人信息", "敏感信息", "收集", "使用", "共享", "存储", "保护义务"],
            "labor_law": ["劳动合同", "工作时间", "休息休假", "劳动报酬", "社会保险", "劳动保护"],
            "tax_evasion": ["增值税", "企业所得税", "个人所得税", "税务申报", "发票管理", "逃税"],
            "consumer_protection": ["消费者权益", "知情权", "选择权", "安全保障", "虚假宣传"],
            "anti_unfair_competition": ["商业贿赂", "虚假宣传", "商业秘密", "不正当竞争"],
            "general": ["法律", "法规", "合规", "规定", "要求", "禁止", "应当"]
        }

        query_parts = [action_summary]
        if domain in domain_keywords:
            query_parts.extend(domain_keywords[domain])
            query = " ".join(query_parts)
        else:
            query = action_summary

        filters = {"tenant_id": tenant_id}

        try:
            retriever = UnifiedRetriever()
            results = await retriever.retrieve(
                query=query,
                filters=filters,
                top_k=5
            )

            if results:
                regulations = []
                for result in results:
                    regulations.append({
                        "content": result.content[:1000] if len(result.content) > 1000 else result.content,
                        "score": result.score,
                        "source": result.metadata.get("source", "unknown")
                    })

                return {
                    "status": "success",
                    "action_summary": action_summary,
                    "domain": domain,
                    "regulations": regulations,
                    "total_matches": len(regulations),
                    "message": f"找到 {len(regulations)} 条相关法规条款",
                    "compliance_status": "review_required",
                    "note": "请结合业务场景和适用法规进行综合判断"
                }
            else:
                fallback_regulations = _get_fallback_regulations(domain)

                return {
                    "status": "warning",
                    "action_summary": action_summary,
                    "domain": domain,
                    "regulations": fallback_regulations,
                    "total_matches": len(fallback_regulations),
                    "message": "知识库中未找到精确匹配，使用通用法规参考",
                    "compliance_status": "manual_review_required",
                    "note": "建议咨询专业法务人员或对接专业法规数据库"
                }

        except Exception as retrieval_error:
            logger.warning(f"检索服务异常，使用内置法规库: {retrieval_error}")

            fallback_regulations = _get_fallback_regulations(domain)

            return {
                "status": "success",
                "action_summary": action_summary,
                "domain": domain,
                "regulations": fallback_regulations,
                "total_matches": len(fallback_regulations),
                "message": "使用内置法规参考库",
                "compliance_status": "manual_review_required",
                "note": "建议接入专业法规数据库以提升准确性"
            }

    except Exception as e:
        logger.error(f"合规性校验失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "action_summary": action_summary,
            "domain": domain,
            "regulations": [],
            "total_matches": 0,
            "compliance_status": "error"
        }


def _get_fallback_regulations(domain: str) -> List[Dict[str, Any]]:
    """获取内置的备用法规库"""
    fallback_rules = {
        "gdpr": [
            {
                "article": "GDPR 第6条",
                "content": "数据处理的合法性基础：需要满足以下条件之一 - (a) 数据主体同意；(b) 履行合同；(c) 法律义务；(d) 保护重要利益；(e) 公共任务；(f) 合法利益",
                "compliance_requirements": ["获取有效同意", "明确处理目的", "提供隐私声明"]
            },
            {
                "article": "GDPR 第17条",
                "content": "被遗忘权：数据主体有权要求数据控制者删除与其相关的个人数据",
                "compliance_requirements": ["建立数据删除机制", "评估删除请求的合法性"]
            }
        ],
        "privacy": [
            {
                "article": "《个人信息保护法》第13条",
                "content": "处理个人信息应当取得个人的同意，特定情形下可无需取得同意",
                "compliance_requirements": ["获取明确同意", "制定隐私政策", "建立投诉渠道"]
            },
            {
                "article": "《个人信息保护法》第51条",
                "content": "个人信息处理者应当采取必要的安全保护措施",
                "compliance_requirements": ["建立安全管理制度", "采取技术措施", "定期安全评估"]
            }
        ],
        "labor_law": [
            {
                "article": "《劳动法》第36条",
                "content": "国家实行劳动者每日工作时间不超过八小时、平均每周工作时间不超过四十四小时的工时制度",
                "compliance_requirements": ["不超过法定工作时间", "支付加班费", "保障休息权利"]
            },
            {
                "article": "《社会保险法》第4条",
                "content": "中华人民共和国境内的用人单位和个人，依法缴纳社会保险费",
                "compliance_requirements": ["及时足额缴纳社保", "代扣代缴员工个人部分"]
            }
        ],
        "tax_evasion": [
            {
                "article": "《税收征收管理法》第52条",
                "content": "因纳税人、扣缴义务人计算错误等失误，未缴或者少缴税款的，税务机关可以追征",
                "compliance_requirements": ["准确计算税款", "按时申报缴纳", "保存会计记录"]
            }
        ],
        "consumer_protection": [
            {
                "article": "《消费者权益保护法》第8条",
                "content": "消费者享有知悉其购买、使用的商品或者接受的服务的真实情况的权利",
                "compliance_requirements": ["提供真实信息", "明码标价", "不进行虚假宣传"]
            }
        ],
        "anti_unfair_competition": [
            {
                "article": "《反不正当竞争法》第8条",
                "content": "经营者不得对其商品的性能、功能、质量、销售状况、用户评价等作虚假或者引人误解的商业宣传",
                "compliance_requirements": ["如实宣传", "不进行虚假广告", "遵守商业道德"]
            }
        ],
        "general": [
            {
                "article": "《民法典》第153条",
                "content": "违反法律、行政法规的强制性规定的民事法律行为无效",
                "compliance_requirements": ["遵守法律法规", "不违反强制性规定"]
            }
        ]
    }

    return fallback_rules.get(domain, fallback_rules["general"])


def create_legal_compliance_tools() -> List:
    """创建法律合规工具列表"""
    return [
        extract_contract_clauses,
        trace_entity_risk_network,
        verify_compliance_rule
    ]
