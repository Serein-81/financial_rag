"""
税务政策官方数据采集服务（合规版）

合规原则：
1. 仅采集官方主动公开的政策法规信息
2. 不采集任何纳税人个体数据
3. 遵守请求频率限制
4. 仅用于企业内部辅助决策

注意：由于官方网站的API保护机制，自动化采集可能受限。
建议方案：
1. 使用官方开放平台API（需注册）
2. 使用商业政策数据服务
3. 手动上传政策文件
"""

import logging
import re
import json
import asyncio
import httpx
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PolicySource(Enum):
    """政策来源枚举"""
    NATIONAL_TAX = "国家税务总局"
    GOVERNMENT_CN = "中国政府网"
    MINISTRY_FINANCE = "财政部"
    LOCAL_TAX = "地方税务局"
    SAMPLE_DATA = "示例政策数据"
    UNKNOWN = "未知来源"


@dataclass
class CrawledPolicy:
    """采集的政策数据"""
    policy_id: str
    title: str
    content: str
    source: str
    source_url: str
    issued_date: Optional[str] = None
    effective_date: Optional[str] = None
    document_number: Optional[str] = None
    tax_types: List[str] = None
    industries: List[str] = None
    regions: List[str] = None
    summary: Optional[str] = None
    created_at: str = None

    def __post_init__(self):
        if self.tax_types is None:
            self.tax_types = []
        if self.industries is None:
            self.industries = []
        if self.regions is None:
            self.regions = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class PolicyCrawlerService:
    """税务政策官方数据采集服务（合规版）"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limit = asyncio.Semaphore(2)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "TaxPolicyResearchBot/1.0 (Non-Commercial Research)",
                    "Accept": "application/json, text/html",
                },
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _generate_policy_id(self, title: str, issued_date: Optional[str] = None) -> str:
        raw = f"{title}_{issued_date}_{datetime.now().date()}"
        import hashlib
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    async def crawl_national_tax_policies(self, max_count: int = 20) -> List[CrawledPolicy]:
        """
        采集国家税务总局最新政策

        注意：此API可能有访问限制，建议使用官方开放平台
        """
        policies: List[CrawledPolicy] = []

        try:
            client = await self._get_client()
            url = "https://www.chinatax.gov.cn/api/service/taxPolicy/list"
            params = {"page": 1, "pageSize": max_count, "serviceType": "taxPolicy"}

            response = await client.get(url, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()

            items = data.get("list", []) or data.get("data", []) or []
            if not isinstance(items, list):
                items = []

            for item in items[:max_count]:
                policy = CrawledPolicy(
                    policy_id=self._generate_policy_id(item.get("title", ""), item.get("issuedDate")),
                    title=item.get("title", "未命名政策"),
                    content="",
                    source=PolicySource.NATIONAL_TAX.value,
                    source_url=item.get("url", ""),
                    issued_date=item.get("issuedDate"),
                    document_number=item.get("documentNumber"),
                    summary=item.get("summary", "")
                )
                policies.append(policy)

            logger.info(f"✅ 采集总局政策列表: {len(policies)} 条")

        except httpx.HTTPError as e:
            logger.warning(f"采集总局政策列表失败（网站可能有访问限制）: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"解析总局政策响应失败: {e}")

        return policies

    async def crawl_chinatax_full_policies(self, max_count: int = 10) -> List[CrawledPolicy]:
        """从中国政府网税费政策专栏采集"""
        policies: List[CrawledPolicy] = []

        try:
            client = await self._get_client()
            url = "https://www.gov.cn/zhengce/xxgk/list.htm"
            params = {"catalogCode": "zbzc_2475", "pageSize": max_count}

            response = await client.get(url, params=params, timeout=15.0)
            response.raise_for_status()
            html = response.text

            title_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]+)\s*</a>')
            date_pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

            for match in title_pattern.finditer(html):
                if len(policies) >= max_count:
                    break

                href = match.group(1)
                title = match.group(2).strip()
                date_match = date_pattern.search(html, match.end())

                if title and len(title) > 5:
                    policy = CrawledPolicy(
                        policy_id=self._generate_policy_id(title),
                        title=title,
                        content="",
                        source=PolicySource.GOVERNMENT_CN.value,
                        source_url=f"https://www.gov.cn{href}" if href.startswith("/") else href,
                        issued_date=date_match.group(0) if date_match else None,
                    )
                    policies.append(policy)

            logger.info(f"✅ 采集中国政府网政策: {len(policies)} 条")

        except httpx.HTTPError as e:
            logger.warning(f"采集中国政府网失败（网站可能有访问限制）: {e}")

        return policies

    async def crawl_finance_policies(self, max_count: int = 10) -> List[CrawledPolicy]:
        """从财政部官网采集财税政策"""
        policies: List[CrawledPolicy] = []

        try:
            client = await self._get_client()
            url = "https://www.mof.gov.cn/zhengwuxinxi/zhengcelist/index.htm"

            response = await client.get(url, timeout=15.0)
            response.raise_for_status()
            html = response.text

            title_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{10,50})\s*</a>')
            date_pattern = re.compile(r'(\d{4})/(\d{2})/(\d{2})')

            for match in title_pattern.finditer(html):
                if len(policies) >= max_count:
                    break

                href = match.group(1)
                title = match.group(2).strip()
                date_match = date_pattern.search(html, match.end())

                if title:
                    full_url = f"https://www.mof.gov.cn{href}" if href.startswith("/") else href
                    policy = CrawledPolicy(
                        policy_id=self._generate_policy_id(title),
                        title=title,
                        content="",
                        source=PolicySource.MINISTRY_FINANCE.value,
                        source_url=full_url,
                        issued_date=f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else None,
                    )
                    policies.append(policy)

            logger.info(f"✅ 采集财政部政策: {len(policies)} 条")

        except httpx.HTTPError as e:
            logger.warning(f"采集财政部失败（网站可能有访问限制）: {e}")

        return policies

    def get_sample_policies(self) -> List[CrawledPolicy]:
        """
        获取示例政策数据（用于演示）

        这些是公开的税务政策摘要，实际使用时建议通过官方渠道获取完整政策
        """
        sample_policies = [
            {
                "title": "关于完善企业所得税收优化小型微利企业认定条件的公告",
                "content": "为进一步支持小型微利企业发展，现就小型微利企业所得税收优惠政策进行优化调整...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "国家税务总局公告2023年第6号",
                "tax_types": ["企业所得税"],
                "summary": "优化小型微利企业认定条件，扩大优惠范围"
            },
            {
                "title": "关于实施增值税小规模纳税人减免税政策的公告",
                "content": "为进一步支持小规模纳税人发展，现就增值税小规模纳税人减免税政策进行公告...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第19号",
                "tax_types": ["增值税"],
                "summary": "小规模纳税人增值税减免政策延续"
            },
            {
                "title": "关于提高个人所得税专项附加扣除标准的通知",
                "content": "根据国务院决定，现就提高个人所得税专项附加扣除标准有关问题进行通知...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "国发〔2023〕13号",
                "tax_types": ["个人所得税"],
                "summary": "3岁以下婴幼儿照护纳入专项附加扣除，标准提高"
            },
            {
                "title": "关于进一步实施小微企业“六税两费”减免政策的公告",
                "content": "为进一步支持小微企业发展，对小微企业实施“六税两费”减免政策...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2022年第10号",
                "tax_types": ["资源税", "城市维护建设税", "房产税", "城镇土地使用税", "印花税", "耕地占用税", "教育费附加", "地方教育附加"],
                "summary": "小微企业“六税两费”减免政策延续实施"
            },
            {
                "title": "关于企业投入基础研究税收优惠政策的公告",
                "content": "为鼓励企业加大创新投入，现就企业投入基础研究有关税收优惠政策进行公告...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2022年第32号",
                "tax_types": ["企业所得税"],
                "summary": "企业投入基础研究可享受税收加计扣除优惠"
            }
        ]

        policies = []
        for i, p in enumerate(sample_policies):
            policy = CrawledPolicy(
                policy_id=self._generate_policy_id(p["title"]),
                title=p["title"],
                content=p["content"],
                source=PolicySource.SAMPLE_DATA.value,
                source_url=p["source_url"],
                issued_date=datetime.now().strftime("%Y-%m-%d"),
                document_number=p["document_number"],
                tax_types=p.get("tax_types", []),
                summary=p.get("summary", ""),
                industries=["全行业"],
                regions=["全国"]
            )
            policies.append(policy)

        return policies

    async def crawl_all_sources(self, max_per_source: int = 10, include_sample: bool = True) -> List[CrawledPolicy]:
        """
        从所有合规来源采集政策

        官方API可能存在访问限制，系统会自动回退到示例数据
        """
        all_policies: List[CrawledPolicy] = []
        online_sources_available = False

        try:
            tax_policies = await self.crawl_national_tax_policies(max_per_source)
            if tax_policies:
                all_policies.extend(tax_policies)
                online_sources_available = True
            await asyncio.sleep(1)

            gov_policies = await self.crawl_chinatax_full_policies(max_per_source)
            if gov_policies:
                all_policies.extend(gov_policies)
                online_sources_available = True
            await asyncio.sleep(1)

            finance_policies = await self.crawl_finance_policies(max_per_source)
            if finance_policies:
                all_policies.extend(finance_policies)
                online_sources_available = True

        except Exception as e:
            logger.warning(f"在线采集遇到问题: {e}")

        if include_sample and not online_sources_available:
            logger.info("📋 官方API暂时不可用，添加示例政策数据用于演示...")
            sample_policies = self.get_sample_policies()
            all_policies.extend(sample_policies)

        seen = set()
        unique_policies = []
        for p in all_policies:
            if p.title not in seen:
                seen.add(p.title)
                unique_policies.append(p)

        logger.info(f"✅ 采集完成: 共 {len(unique_policies)} 条政策（在线: {online_sources_available}）")
        return unique_policies


policy_crawler_service = PolicyCrawlerService()
