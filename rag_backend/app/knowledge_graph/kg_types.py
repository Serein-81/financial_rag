"""
知识图谱领域类型定义

集中管理实体类型和关系类型的枚举与描述，
供 entity_extractor 和 relation_extractor 的 LLM 提示词使用。
"""

from typing import Dict, List


# ============ 实体类型定义 ============

class EntityType:
    """实体类型常量（按业务域分组）"""

    # ── 主体 ──
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    DEPARTMENT = "DEPARTMENT"

    # ── 财务 ──
    FINANCIAL_METRIC = "FINANCIAL_METRIC"    # 财务指标：营收、利润、成本等
    FINANCIAL_REPORT = "FINANCIAL_REPORT"    # 财务报表：资产负债表、利润表
    ACCOUNT = "ACCOUNT"                      # 账户
    BUDGET = "BUDGET"                        # 预算

    # ── 税务 ──
    TAX_TYPE = "TAX_TYPE"                    # 税种：增值税、企业所得税
    TAX_POLICY = "TAX_POLICY"                # 税收政策
    TAX_RATE = "TAX_RATE"                    # 税率
    TAX_EXEMPTION = "TAX_EXEMPTION"          # 税收减免/优惠

    # ── 法务 ──
    CONTRACT = "CONTRACT"                    # 合同
    LEGAL_CASE = "LEGAL_CASE"                # 案件
    REGULATION = "REGULATION"                # 法规/条例
    CLAUSE = "CLAUSE"                        # 条款

    # ── 通用 ──
    PRODUCT = "PRODUCT"                      # 产品
    SERVICE = "SERVICE"                      # 服务
    LOCATION = "LOCATION"                    # 地点
    DATE_PERIOD = "DATE_PERIOD"              # 日期/期间
    EVENT = "EVENT"                          # 事件
    TECHNOLOGY = "TECHNOLOGY"                # 技术/专利


# 实体类型 → 中文描述
ENTITY_TYPE_DESCRIPTIONS: Dict[str, str] = {
    EntityType.COMPANY: "公司、企业、组织名称（如'阿里巴巴'、'腾讯'）",
    EntityType.PERSON: "人员、联系人、自然人（如'张三'、'李四'）",
    EntityType.DEPARTMENT: "部门、团队（如'财务部'、'研发中心'）",

    EntityType.FINANCIAL_METRIC: "财务指标、数据（如'营收'、'净利润'、'资产负债率'）",
    EntityType.FINANCIAL_REPORT: "财务报表、报告（如'2024年报'、'利润表'）",
    EntityType.ACCOUNT: "账户、账簿（如'基本账户'、'应收账款'）",
    EntityType.BUDGET: "预算、计划（如'年度预算'、'项目预算'）",

    EntityType.TAX_TYPE: "税种名称（如'增值税'、'企业所得税'、'印花税'）",
    EntityType.TAX_POLICY: "税收政策、法规文件（如'小微企业税收优惠'）",
    EntityType.TAX_RATE: "税率或税率档位（如'13%'、'25%'）",
    EntityType.TAX_EXEMPTION: "税收减免、优惠、抵扣（如'研发加计扣除'）",

    EntityType.CONTRACT: "合同、协议、契约（如'采购合同'、'NDA'）",
    EntityType.LEGAL_CASE: "法律案件、纠纷、诉讼",
    EntityType.REGULATION: "法律法规、条例、规章",
    EntityType.CLAUSE: "合同或法规中的具体条款",

    EntityType.PRODUCT: "产品（如'手机'、'云服务'）",
    EntityType.SERVICE: "服务（如'咨询服务'、'审计服务'）",
    EntityType.LOCATION: "地点、地区（如'北京'、'杭州'、'海外'）",
    EntityType.DATE_PERIOD: "日期、期间、时间点（如'2024年'、'第一季度'）",
    EntityType.EVENT: "事件、活动（如'年度会议'、'并购'）",
    EntityType.TECHNOLOGY: "技术、专利、标准（如'5G'、'人工智能'）",
}


# ============ 关系类型定义 ============

class RelationType:
    """关系类型常量"""

    # ── 公司/人事 ──
    WORKS_AT = "WORKS_AT"                    # 工作于（人→公司）
    MANAGED_BY = "MANAGED_BY"                # 由...管理（人→人）
    BELONGS_TO = "BELONGS_TO"                # 属于（部门→公司）
    PARTNER_WITH = "PARTNER_WITH"            # 合作关系（公司→公司）
    COMPETES_WITH = "COMPETES_WITH"          # 竞争关系
    SUBSIDIARY_OF = "SUBSIDIARY_OF"          # 子公司（公司→母公司）
    SUPPLIER_OF = "SUPPLIER_OF"              # 供应商
    CUSTOMER_OF = "CUSTOMER_OF"              # 客户
    INVESTED_IN = "INVESTED_IN"              # 投资
    OWNS = "OWNS"                            # 持有（股权/资产）

    # ── 财务 ──
    HAS_METRIC = "HAS_METRIC"                # 有财务指标（公司→指标）
    REPORTED_IN = "REPORTED_IN"               # 体现在报表中
    AUDITED_BY = "AUDITED_BY"                # 由...审计

    # ── 税务 ──
    SUBJECT_TO = "SUBJECT_TO"                # 适用税种（公司→税种）
    HAS_RATE = "HAS_RATE"                    # 税率为（税种→税率）
    ELIGIBLE_FOR = "ELIGIBLE_FOR"            # 符合优惠条件
    CLAIMED = "CLAIMED"                      # 已申报

    # ── 法务 ──
    SIGNED = "SIGNED"                        # 签署（公司→合同）
    GOVERNS = "GOVERNS"                      # 管辖/适用（法规→公司/合同）
    VIOLATES = "VIOLATES"                    # 违反
    CONTAINS_CLAUSE = "CONTAINS_CLAUSE"      # 包含条款
    EFFECTIVE_PERIOD = "EFFECTIVE_PERIOD"    # 有效期

    # ── 通用 ──
    LOCATED_AT = "LOCATED_AT"                # 位于
    PRODUCES = "PRODUCES"                    # 生产/提供（公司→产品）
    USES = "USES"                            # 使用（公司→技术）
    RELATED_TO = "RELATED_TO"                # 相关（通用兜底）


# 关系类型 → 中文描述（含三元组示例）
RELATION_TYPE_DESCRIPTIONS: Dict[str, str] = {
    RelationType.WORKS_AT: "工作于：人 → 公司（如'张三 工作于 阿里巴巴'）",
    RelationType.MANAGED_BY: "由...管理：人 → 人（如'李四 由 王五管理'）",
    RelationType.BELONGS_TO: "属于：部门/团队 → 公司",
    RelationType.PARTNER_WITH: "合作关系：公司 ↔ 公司（如'阿里巴巴 合作 腾讯'）",
    RelationType.COMPETES_WITH: "竞争关系：公司 ↔ 公司",
    RelationType.SUBSIDIARY_OF: "子公司 → 母公司（如'菜鸟 是 阿里巴巴的子公司'）",
    RelationType.SUPPLIER_OF: "供应商关系：公司 → 公司",
    RelationType.CUSTOMER_OF: "客户关系：公司 → 公司",
    RelationType.INVESTED_IN: "投资关系：公司 → 公司",
    RelationType.OWNS: "持有/拥有：公司 → 资产/股权",

    RelationType.HAS_METRIC: "有财务指标：公司 → 财务指标（如'阿里巴巴 2023年营收 8687亿元'）",
    RelationType.REPORTED_IN: "体现在报表中：指标 → 报表",
    RelationType.AUDITED_BY: "由...审计：公司 → 审计方",

    RelationType.SUBJECT_TO: "适用税种：公司 → 税种（如'阿里巴巴 适用 企业所得税 25%'）",
    RelationType.HAS_RATE: "税率为：税种 → 税率",
    RelationType.ELIGIBLE_FOR: "符合优惠条件：公司 → 税收优惠",
    RelationType.CLAIMED: "已申报：公司 → 税种/优惠",

    RelationType.SIGNED: "签署合同：公司 → 合同（如'阿里巴巴 签署 采购协议'）",
    RelationType.GOVERNS: "管辖/适用：法规 → 公司/合同",
    RelationType.VIOLATES: "违反：公司/行为 → 法规",
    RelationType.CONTAINS_CLAUSE: "包含条款：合同 → 条款",
    RelationType.EFFECTIVE_PERIOD: "有效期：合同 → 日期",

    RelationType.LOCATED_AT: "位于：公司/人 → 地点（如'阿里巴巴 位于 杭州'）",
    RelationType.PRODUCES: "生产/提供：公司 → 产品/服务",
    RelationType.USES: "使用：公司 → 技术（如'华为 使用 5G技术'）",
    RelationType.RELATED_TO: "相关（通用兜底，仅在无合适类型时使用）",
}


def get_entity_type_prompt_block() -> str:
    """生成实体类型说明的提示词块"""
    lines = ["实体类型说明（必须严格使用以下类型，不要编造新类型）："]
    for etype in sorted(ENTITY_TYPE_DESCRIPTIONS.keys()):
        desc = ENTITY_TYPE_DESCRIPTIONS[etype]
        lines.append(f"  - {etype}: {desc}")
    return "\n".join(lines)


def get_relation_type_prompt_block() -> str:
    """生成关系类型说明的提示词块"""
    lines = ["关系类型说明（必须严格使用以下类型，不要编造新类型）："]
    for rtype in sorted(RELATION_TYPE_DESCRIPTIONS.keys()):
        desc = RELATION_TYPE_DESCRIPTIONS[rtype]
        lines.append(f"  - {rtype}: {desc}")
    return "\n".join(lines)
