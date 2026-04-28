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
from urllib.parse import urlparse
from app.core.config import settings
from app.services.policy_collector.robots_checker import robots_checker
from app.services.policy_collector.rate_limiter import rate_limiter

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
                    "User-Agent": settings.POLICY_COLLECTOR_USER_AGENT,
                    "Accept": "application/json, text/html",
                },
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def _robots_allows(self, url: str, source_name: str) -> bool:
        """
        严格 robots.txt 检查。

        默认要求目标站点能获取 robots.txt；无法获取时不进行在线采集。
        """
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_url}/robots.txt"

        rules = await robots_checker._get_robots_rules(base_url, robots_url)
        if rules is None:
            if settings.POLICY_REQUIRE_ROBOTS_TXT:
                logger.warning(f"🚫 [{source_name}] 无法确认 robots.txt，跳过在线采集: {url}")
                return False
            logger.warning(f"⚠️ [{source_name}] 无法获取 robots.txt，按配置允许继续: {url}")

        allowed = await robots_checker.check_allowed(url, source_name)
        if not allowed:
            logger.warning(f"🚫 [{source_name}] robots.txt 不允许采集: {url}")
            return False

        crawl_delay = robots_checker.get_crawl_delay(base_url)
        rate_limiter.set_robots_crawl_delay(parsed.netloc, crawl_delay)
        return True

    async def _safe_get(
        self,
        url: str,
        source_name: str,
        *,
        params: Optional[dict] = None,
        timeout: float = 15.0
    ) -> Optional[httpx.Response]:
        """
        合规 GET：robots 检查 -> 域名限速 -> 请求 -> 状态记录。

        不绕过 403、验证码或反爬限制；非 2xx 响应交给调用方记录并放弃。
        """
        if not settings.POLICY_ONLINE_CRAWL_ENABLED:
            logger.info(f"🛡️ [{source_name}] 在线采集未启用，跳过: {url}")
            return None

        if not await self._robots_allows(url, source_name):
            return None

        parsed = urlparse(url)
        domain = parsed.netloc
        allowed_by_rate = await rate_limiter.acquire(domain)
        if not allowed_by_rate:
            logger.warning(f"⏳ [{source_name}] 速率限制未放行，跳过本次请求: {domain}")
            return None

        client = await self._get_client()
        response = await client.get(url, params=params, timeout=timeout)
        rate_limiter.record_response_status(domain, response.status_code)
        return response

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
            url = "https://www.chinatax.gov.cn/api/service/taxPolicy/list"
            params = {"page": 1, "pageSize": max_count, "serviceType": "taxPolicy"}

            response = await self._safe_get(url, PolicySource.NATIONAL_TAX.value, params=params, timeout=15.0)
            if response is None:
                return policies
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
            url = "https://www.gov.cn/zhengce/xxgk/list.htm"
            params = {"catalogCode": "zbzc_2475", "pageSize": max_count}

            response = await self._safe_get(url, PolicySource.GOVERNMENT_CN.value, params=params, timeout=15.0)
            if response is None:
                return policies
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
            url = "https://www.mof.gov.cn/zhengwuxinxi/zhengcelist/index.htm"

            response = await self._safe_get(url, PolicySource.MINISTRY_FINANCE.value, timeout=15.0)
            if response is None:
                return policies
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
                "summary": "企业投入基础研究可享受税收加计扣除优惠",
                "industries": ["科技服务业", "制造业", "软件和信息技术服务业"]
            },
            {
                "title": "关于先进制造业企业增值税加计抵减政策的公告",
                "content": "为促进先进制造业高质量发展，符合条件的先进制造业企业可按规定享受增值税加计抵减政策...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第43号",
                "tax_types": ["增值税"],
                "summary": "先进制造业企业按规定享受增值税加计抵减",
                "industries": ["制造业", "高端装备", "电子信息"]
            },
            {
                "title": "关于研发费用税前加计扣除政策有关问题的公告",
                "content": "企业开展研发活动中实际发生的研发费用，未形成无形资产计入当期损益的，可按规定在税前加计扣除...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第7号",
                "tax_types": ["企业所得税"],
                "summary": "明确研发费用税前加计扣除适用口径和管理要求",
                "industries": ["全行业", "科技服务业", "制造业"]
            },
            {
                "title": "关于继续实施物流企业大宗商品仓储设施用地城镇土地使用税优惠政策的公告",
                "content": "为支持物流业健康发展，对符合条件的物流企业大宗商品仓储设施用地，按规定减征城镇土地使用税...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第5号",
                "tax_types": ["城镇土地使用税"],
                "summary": "物流企业大宗商品仓储设施用地继续享受土地使用税优惠",
                "industries": ["交通运输、仓储和邮政业", "批发和零售业"]
            },
            {
                "title": "关于延续新能源汽车车辆购置税减免政策的公告",
                "content": "为支持新能源汽车产业发展，延续和优化新能源汽车车辆购置税减免政策，明确分阶段减免安排...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局 工业和信息化部公告2023年第10号",
                "tax_types": ["车辆购置税"],
                "summary": "新能源汽车车辆购置税减免政策延续实施",
                "industries": ["汽车制造业", "新能源产业", "交通运输业"]
            },
            {
                "title": "关于支持居民换购住房有关个人所得税政策的公告",
                "content": "对符合条件的出售自有住房并在规定期限内重新购买住房的纳税人，按规定退还已缴纳的个人所得税...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局 住房城乡建设部公告2023年第28号",
                "tax_types": ["个人所得税"],
                "summary": "居民换购住房可按条件享受个人所得税退税",
                "industries": ["房地产业", "居民服务业"]
            },
            {
                "title": "关于继续实施公共租赁住房税收优惠政策的公告",
                "content": "为继续支持公共租赁住房建设和运营，对公共租赁住房建设、经营涉及的有关税费按规定给予优惠...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第33号",
                "tax_types": ["房产税", "城镇土地使用税", "印花税", "契税", "增值税"],
                "summary": "公共租赁住房建设运营相关税收优惠延续",
                "industries": ["房地产业", "租赁和商务服务业"]
            },
            {
                "title": "关于支持货物期货市场对外开放有关增值税政策的公告",
                "content": "为支持货物期货市场对外开放，对境外机构投资境内特定品种货物期货取得的收入，按规定适用增值税政策...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第21号",
                "tax_types": ["增值税"],
                "summary": "明确货物期货市场对外开放相关增值税处理",
                "industries": ["金融业", "批发和零售业"]
            },
            {
                "title": "关于延续实施创业投资企业和天使投资个人有关税收政策的公告",
                "content": "创业投资企业和天使投资个人投资初创科技型企业，符合条件的可按投资额一定比例抵扣应纳税所得额...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第17号",
                "tax_types": ["企业所得税", "个人所得税"],
                "summary": "创业投资和天使投资支持初创科技型企业的税收优惠延续",
                "industries": ["金融业", "科技服务业", "软件和信息技术服务业"]
            },
            {
                "title": "关于支持小型微利企业和个体工商户发展所得税优惠政策的公告",
                "content": "对符合条件的小型微利企业和个体工商户，按规定减免所得税，进一步降低经营主体税费负担...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第12号",
                "tax_types": ["企业所得税", "个人所得税"],
                "summary": "小型微利企业和个体工商户所得税优惠延续优化",
                "industries": ["全行业", "批发和零售业", "住宿和餐饮业"]
            },
            {
                "title": "关于生产和装配伤残人员专门用品企业免征企业所得税的公告",
                "content": "符合条件的生产和装配伤残人员专门用品企业，可按规定免征企业所得税...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局 民政部公告2023年第57号",
                "tax_types": ["企业所得税"],
                "summary": "伤残人员专门用品生产装配企业继续享受所得税优惠",
                "industries": ["制造业", "社会工作"]
            },
            {
                "title": "关于继续实施农产品批发市场农贸市场房产税城镇土地使用税优惠政策的公告",
                "content": "为支持农产品流通体系建设，对符合条件的农产品批发市场、农贸市场使用的房产和土地给予税收优惠...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第50号",
                "tax_types": ["房产税", "城镇土地使用税"],
                "summary": "农产品批发市场和农贸市场相关房产土地税收优惠延续",
                "industries": ["农、林、牧、渔业", "批发和零售业"]
            },
            {
                "title": "关于支持文化企业发展若干税收政策的公告",
                "content": "为促进文化产业发展，对符合条件的文化企业和出版发行等业务按规定给予税收支持...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第71号",
                "tax_types": ["增值税", "企业所得税"],
                "summary": "文化企业发展相关增值税和企业所得税优惠政策延续",
                "industries": ["文化、体育和娱乐业", "新闻和出版业"]
            },
            {
                "title": "关于边销茶增值税政策的公告",
                "content": "为保障边销茶供应，对符合条件的边销茶生产销售环节按规定适用增值税优惠政策...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第59号",
                "tax_types": ["增值税"],
                "summary": "边销茶相关增值税优惠政策延续",
                "industries": ["农、林、牧、渔业", "制造业", "批发和零售业"],
                "regions": ["内蒙古", "西藏", "青海", "新疆", "全国"]
            },
            {
                "title": "关于继续实施科技企业孵化器大学科技园和众创空间税收政策的公告",
                "content": "对国家级、省级科技企业孵化器、大学科技园和备案众创空间，符合条件的收入和房产土地可享受税收优惠...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局 科技部 教育部公告2023年第42号",
                "tax_types": ["增值税", "房产税", "城镇土地使用税"],
                "summary": "科技企业孵化器、大学科技园和众创空间税收优惠延续",
                "industries": ["科技服务业", "教育", "租赁和商务服务业"]
            },
            {
                "title": "关于继续实施金融机构农户贷款利息收入免征增值税政策的公告",
                "content": "为支持普惠金融发展，金融机构向农户发放小额贷款取得的利息收入，符合条件的免征增值税...",
                "source_url": "https://www.chinatax.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第67号",
                "tax_types": ["增值税"],
                "summary": "金融机构农户小额贷款利息收入增值税优惠延续",
                "industries": ["金融业", "农、林、牧、渔业"],
                "regions": ["全国", "县域地区", "农村地区"]
            },
            {
                "title": "关于继续实施支持农村金融发展企业所得税政策的公告",
                "content": "对金融机构农户小额贷款利息收入以及保险公司种植业、养殖业保险业务收入，按规定计算企业所得税优惠...",
                "source_url": "https://www.mof.gov.cn/",
                "document_number": "财政部 税务总局公告2023年第55号",
                "tax_types": ["企业所得税"],
                "summary": "农村金融相关企业所得税优惠政策延续",
                "industries": ["金融业", "农、林、牧、渔业"],
                "regions": ["全国", "农村地区"]
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
                industries=p.get("industries", ["全行业"]),
                regions=p.get("regions", ["全国"])
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

        if not settings.POLICY_ONLINE_CRAWL_ENABLED:
            logger.info("🛡️ 政策在线采集未启用，跳过公网政策站点访问")
        else:
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
