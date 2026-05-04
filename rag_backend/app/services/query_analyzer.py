"""
查询解析器 (Query Analyzer v3)

职责：
1. 域路由：判断查询属于哪个领域 (legal/tax/finance/general)
2. 结构化条件提取：提取 year/quarter/region/tax_type
3. 最新意图检测：检测"最新""现行"等时序优先意图
4. 前置过滤条件生成：转为 metadata_filter 参数

设计：纯正则 + 关键词，零 LLM 依赖，<5ms。
"""

import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    查询解析器 (v3 增强)
    """

    # 域路由关键词
    DOMAIN_KEYWORDS = {
        "legal": [
            "合同", "协议", "违约", "赔偿", "诉讼", "起诉", "仲裁",
            "法务", "条款", "义务", "甲方", "乙方", "丙方",
            "违约金", "解除", "终止", "管辖", "效力",
        ],
        "tax": [
            "税务", "税法", "增值税", "所得税", "发票", "申报",
            "税率", "优惠", "减免", "抵扣", "退税", "纳税",
            "税种", "小规模", "一般纳税人",
        ],
        "finance": [
            "财报", "利润", "营收", "成本", "费用", "资产",
            "负债", "财务", "审计", "报表", "预算", "收入",
            "支出", "资产负债表", "利润表", "现金流量表",
        ],
    }

    # 年份正则
    YEAR_REGEX = re.compile(r"(\d{4})\s*年")

    # 季度映射
    QUARTER_MAP = {
        "第一季度": "Q1", "第1季度": "Q1", "一季度": "Q1",
        "第二季度": "Q2", "第2季度": "Q2", "二季度": "Q2",
        "第三季度": "Q3", "第3季度": "Q3", "三季度": "Q3",
        "第四季度": "Q4", "第4季度": "Q4", "四季度": "Q4",
        "Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "Q4": "Q4",
    }

    # 税种列表
    TAX_TYPES = [
        "增值税", "企业所得税", "个人所得税", "消费税",
        "关税", "印花税", "房产税", "土地使用税",
        "契税", "城市维护建设税", "车辆购置税",
        "资源税", "土地增值税",
    ]

    # 最新意图关键词
    LATEST_INTENT_KEYWORDS = [
        "最新", "最近", "当前", "现行", "现有", "目前",
        "新版本", "新版", "有效", "现有效",
        "新规", "新政", "新政策", "新法",
    ]

    # 财务指标关键词（与 financial_chunker 同步）
    FINANCE_METRICS = [
        "营业收入", "营业成本", "营业利润", "利润总额", "净利润",
        "研发费用", "销售费用", "管理费用", "财务费用",
        "总资产", "总负债", "净资产", "货币资金", "应收账款",
        "经营活动现金流", "每股收益", "净资产收益率",
        "营收", "净利", "毛利",
    ]

    # 地域列表
    REGIONS = [
        "全国", "北京市", "上海市", "广东省", "浙江省", "江苏省",
        "深圳市", "广州市", "天津市", "重庆市", "四川省", "湖北省",
        "湖南省", "福建省", "山东省", "河北省", "河南省",
        "安徽省", "陕西省", "辽宁省",
    ]

    def analyze(self, query: str) -> Dict:
        """
        解析用户查询。

        Args:
            query: 用户问题原文

        Returns:
            {
                "domain": "tax" | "legal" | "finance" | None,
                "filters": {"year": "2023", "tax_type": "企业所得税", ...},
                "has_temporal_constraint": bool,
                "wants_latest": bool,
                "temporal_mode": "latest" | "specific" | "none",
                "entities": {},
            }
        """
        if not query or not query.strip():
            return {
                "domain": None, "filters": {},
                "has_temporal_constraint": False,
                "wants_latest": False, "temporal_mode": "none",
                "entities": {},
            }

        domain = self._route_domain(query)
        filters = self._extract_filters(query)
        has_time = bool(filters.get("year") or filters.get("quarter"))
        wants_latest = self._detect_latest_intent(query)

        if has_time:
            temporal_mode = "specific"
        elif wants_latest:
            temporal_mode = "latest"
        else:
            temporal_mode = "none"

        result = {
            "domain": domain,
            "filters": filters,
            "has_temporal_constraint": has_time,
            "wants_latest": wants_latest,
            "temporal_mode": temporal_mode,
            "entities": {},
        }

        logger.debug(f"[QueryAnalyzer] query={query[:30]}... -> {result}")
        return result

    def _route_domain(self, query: str) -> Optional[str]:
        """域路由：通过关键词判断查询领域"""
        scores = {"legal": 0, "tax": 0, "finance": 0}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    scores[domain] += 1
        max_score = max(scores.values()) if scores else 0
        if max_score == 0:
            return None
        return max(scores, key=scores.get)

    def _extract_filters(self, query: str) -> Dict[str, str]:
        """提取结构化过滤条件"""
        filters = {}

        year_match = self.YEAR_REGEX.search(query)
        if year_match:
            filters["year"] = year_match.group(1)

        for q_text, q_val in self.QUARTER_MAP.items():
            if q_text in query:
                filters["quarter"] = q_val
                break

        for tax_type in self.TAX_TYPES:
            if tax_type in query:
                filters["tax_type"] = tax_type
                break

        for region in self.REGIONS:
            if region in query:
                filters["region"] = region
                break

        # 财务指标
        for metric in self.FINANCE_METRICS:
            if metric in query:
                filters["metric"] = metric
                break

        return filters

    def _detect_latest_intent(self, query: str) -> bool:
        """检测查询中是否包含'最新''现行'等时效优先意图"""
        query_clean = re.sub(r"[的的是了]", "", query)
        for kw in self.LATEST_INTENT_KEYWORDS:
            if kw in query_clean:
                return True
        return False

    def build_metadata_filter(self, query_meta: Dict) -> Optional[Dict[str, str]]:
        """将解析结果转为 metadata_filter 参数"""
        filters = query_meta.get("filters", {})
        if not filters:
            return None
        metadata_filter = {}
        for key in ["year", "quarter", "tax_type", "region"]:
            if key in filters:
                metadata_filter[key] = filters[key]
        return metadata_filter if metadata_filter else None

    def build_temporal_filter(self, query_meta: Dict) -> Optional[Dict[str, str]]:
        """构建时效过滤条件（tax 领域专用）"""
        year = query_meta.get("filters", {}).get("year")
        if not year:
            return None
        try:
            y = int(year)
            return {
                "effective_date": f"{y}-12-31",
                "expiry_date": f"{y}-01-01",
            }
        except ValueError:
            return None


query_analyzer = QueryAnalyzer()
