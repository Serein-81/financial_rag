"""
政策采集服务
从官方来源采集税务政策信息

合规说明：
1. 优先使用官方提供的 API 接口，而非暴力爬取
2. 严格遵守 robots.txt 协议
3. 遵守《网络数据安全管理条例》
4. 不得影响网站正常运行
5. 不得破解反爬技术措施
"""

import httpx
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
from enum import Enum

from .robots_checker import robots_checker
from .rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """数据源类型"""
    API = "api"
    RSS = "rss"
    SITEMAP = "sitemap"
    HTML = "html"


@dataclass
class PolicySource:
    """政策来源配置"""
    name: str
    base_url: str
    source_type: DataSourceType = DataSourceType.HTML
    search_url: Optional[str] = None
    list_url: Optional[str] = None
    api_endpoint: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True
    priority: int = 1
    legal_notice: Optional[str] = None
    requires_auth: bool = False


@dataclass
class CollectedPolicy:
    """采集到的政策"""
    source_name: str
    source_url: str
    title: str
    content: str
    published_date: Optional[datetime] = None
    policy_number: Optional[str] = None
    raw_data: Optional[Dict] = None
    collected_at: datetime = field(default_factory=datetime.now)
    data_source_type: DataSourceType = DataSourceType.HTML
    is_official_api: bool = False
    legal_notice: str = ""


@dataclass
class ComplianceReport:
    """合规检查报告"""
    source_name: str
    allowed: bool
    reason: str
    crawl_delay: float = 1.0
    restrictions: List[str] = field(default_factory=list)
    official_api_available: bool = False
    official_api_endpoint: Optional[str] = None


class PolicyCollector:
    """
    政策采集器
    
    从官方来源采集税务政策信息
    
    合规优先级（由高到低）：
    1. 官方开放 API 接口（最稳定、最合法）
    2. 标准数据格式（RSS、Sitemap）
    3. 符合 robots.txt 的网页抓取
    4. 需要申请的数据源
    
    支持：
    1. 自动检测官方 API
    2. robots.txt 合规检查
    3. 多层速率限制
    4. 法律免责声明
    5. 合规日志记录
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.sources = self._init_sources()
        
        self._http_client: Optional[httpx.AsyncClient] = None
        
        self._compliance_log: List[ComplianceReport] = []
    
    def _init_sources(self) -> List[PolicySource]:
        """
        初始化官方来源配置
        
        优先级说明：
        1. 国家法律法规数据库 - 最权威的法律法规库
        2. 国家税务总局 - 税务政策官方来源
        3. 中国政府网 - 国务院政策文件库
        4. 财政部 - 财政政策官方来源
        """
        return [
            PolicySource(
                name="国家法律法规数据库",
                base_url="https://flfg.pan.gov.cn",
                source_type=DataSourceType.API,
                search_url="https://flfg.pan.gov.cn/index",
                api_endpoint="https://flfg.pan.gov.cn/api/policy/search",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System; Contact: support@example.com)",
                    "Accept": "application/json, text/html",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "X-Request-Source": "PolicyCollector"
                },
                priority=1,
                legal_notice="数据来自全国人大常委会办公厅维护的国家法律法规数据库"
            ),
            PolicySource(
                name="中国政府网政策库",
                base_url="https://www.gov.cn/zhengce",
                source_type=DataSourceType.HTML,
                list_url="https://www.gov.cn/zhengce/xxgk/inde.htm",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System; Contact: support@example.com)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9"
                },
                priority=2,
                legal_notice="数据来自中央人民政府门户网站"
            ),
            PolicySource(
                name="国家税务总局",
                base_url="https://www.chinatax.gov.cn",
                source_type=DataSourceType.HTML,
                search_url="https://www.chinatax.gov.cn/chinatax/n810341/n810755/",
                list_url="https://www.chinatax.gov.cn/chinatax/n810341/n810755/index.html",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System; Contact: support@example.com)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                },
                priority=3,
                legal_notice="数据来自国家税务总局官方网站"
            ),
            PolicySource(
                name="财政部",
                base_url="http://www.mof.gov.cn",
                source_type=DataSourceType.HTML,
                search_url="http://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/",
                list_url="http://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/index.htm",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System; Contact: support@example.com)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                },
                priority=4,
                legal_notice="数据来自财政部官方网站"
            ),
            PolicySource(
                name="国务院",
                base_url="http://www.gov.cn",
                source_type=DataSourceType.HTML,
                search_url="http://www.gov.cn/zhengce/xxgk/inde.htm",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System; Contact: support@example.com)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                },
                priority=5,
                legal_notice="数据来自中央人民政府网站"
            ),
        ]
    
    async def check_compliance(self, source: PolicySource) -> ComplianceReport:
        """
        检查数据源的合规性
        
        Args:
            source: 来源配置
            
        Returns:
            ComplianceReport: 合规检查报告
        """
        logger.info(f"🔍 [{source.name}] 开始合规检查...")
        
        report = ComplianceReport(
            source_name=source.name,
            allowed=False,
            reason="待检查"
        )
        
        robots_url = f"{source.base_url}/robots.txt"
        
        try:
            allowed, restrictions, crawl_delay = await robots_checker.check_compliance(
                source.base_url, 
                source.name
            )
            
            report.allowed = allowed
            report.restrictions = restrictions
            report.crawl_delay = crawl_delay
            
            if not allowed:
                report.reason = f"robots.txt 禁止: {', '.join(restrictions)}"
                logger.warning(f"🚫 [{source.name}] {report.reason}")
            else:
                report.reason = f"允许爬取（延迟: {crawl_delay}秒）"
                logger.info(f"✅ [{source.name}] {report.reason}")
            
        except Exception as e:
            report.allowed = False
            report.reason = f"检查失败: {str(e)}"
            logger.error(f"❌ [{source.name}] 合规检查失败: {e}")
        
        if source.api_endpoint:
            report.official_api_available = True
            report.official_api_endpoint = source.api_endpoint
            logger.info(f"🔌 [{source.name}] 检测到官方 API: {source.api_endpoint}")
        
        self._compliance_log.append(report)
        
        return report
    
    async def detect_api_endpoint(self, source: PolicySource) -> Optional[str]:
        """
        检测官方 API 接口
        
        Args:
            source: 来源配置
            
        Returns:
            Optional[str]: API 端点地址
        """
        api_patterns = [
            "/api/",
            "/v1/",
            "/v2/",
            "/openapi",
            "/swagger",
            "/developer",
            "/opendata"
        ]
        
        for pattern in api_patterns:
            test_url = urljoin(source.base_url, pattern)
            
            try:
                client = await self._get_client()
                response = await client.get(
                    test_url,
                    headers=source.headers,
                    timeout=5.0
                )
                
                if response.status_code in [200, 401, 403]:
                    logger.info(f"🔌 [{source.name}] 发现 API 端点: {test_url}")
                    return test_url
                    
            except Exception:
                continue
        
        return None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                follow_redirects=True
            )
        return self._http_client
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def collect_from_source(
        self,
        source: PolicySource,
        keywords: Optional[List[str]] = None
    ) -> List[CollectedPolicy]:
        """
        从指定来源采集政策
        
        Args:
            source: 来源配置
            keywords: 关键词列表
            
        Returns:
            List[CollectedPolicy]: 采集到的政策列表
        """
        if not source.enabled:
            logger.info(f"⏭️ [{source.name}] 来源已禁用")
            return []
        
        logger.info(f"📥 [{source.name}] 开始采集政策...")
        
        compliance_report = await self.check_compliance(source)
        
        if not compliance_report.allowed:
            logger.warning(
                f"🚫 [{source.name}] 合规检查未通过: {compliance_report.reason}"
            )
            return []
        
        if compliance_report.official_api_available:
            logger.info(
                f"🔌 [{source.name}] 使用官方 API: {compliance_report.official_api_endpoint}"
            )
        
        collected = []
        
        try:
            if source.api_endpoint and compliance_report.official_api_available:
                policies = await self._collect_via_api(source, keywords)
                collected.extend(policies)
            elif source.list_url:
                policies = await self._collect_list_page(source)
                collected.extend(policies)
                
                if keywords:
                    policies = await self._collect_with_keywords(source, keywords)
                    collected.extend(policies)
            
            for policy in collected:
                policy.legal_notice = source.legal_notice or ""
                policy.data_source_type = source.source_type
                policy.is_official_api = compliance_report.official_api_available
            
            logger.info(f"✅ [{source.name}] 采集完成，共 {len(collected)} 条政策")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ [{source.name}] 采集数据失败: {e}", exc_info=True)
        except (OSError, IOError) as e:
            logger.error(f"❌ [{source.name}] 采集IO失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ [{source.name}] 采集失败: {e}", exc_info=True)
        
        return collected
    
    async def _collect_via_api(
        self,
        source: PolicySource,
        keywords: Optional[List[str]] = None
    ) -> List[CollectedPolicy]:
        """
        通过官方 API 采集政策
        
        Args:
            source: 来源配置
            keywords: 关键词列表
            
        Returns:
            List[CollectedPolicy]: 政策列表
        """
        policies = []
        
        parsed = urlparse(source.base_url)
        domain = parsed.netloc
        
        await rate_limiter.acquire(domain)
        
        client = await self._get_client()
        
        try:
            params = {}
            if keywords:
                params["keyword"] = ",".join(keywords)
            
            response = await client.get(
                source.api_endpoint,
                headers=source.headers,
                params=params,
                timeout=self.timeout
            )
            
            rate_limiter.record_response_status(domain, response.status_code)
            
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    policies = self._parse_api_response(json_data, source)
                except ValueError:
                    logger.warning(f"⚠️ [{source.name}] API 返回非 JSON 格式")
                    policies = self._parse_list_page(response.text, source)
            else:
                logger.warning(
                    f"⚠️ [{source.name}] API 返回状态码: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"❌ [{source.name}] API 采集失败: {e}")
        
        return policies
    
    def _parse_api_response(
        self,
        json_data: Dict,
        source: PolicySource
    ) -> List[CollectedPolicy]:
        """
        解析 API 响应数据
        
        Args:
            json_data: API 返回的 JSON 数据
            source: 来源配置
            
        Returns:
            List[CollectedPolicy]: 政策列表
        """
        policies = []
        
        try:
            items = json_data.get("data", []) or json_data.get("results", []) or json_data
            
            for item in items:
                policy = CollectedPolicy(
                    source_name=source.name,
                    source_url=item.get("url", item.get("link", "")),
                    title=item.get("title", item.get("name", "")),
                    content=item.get("content", item.get("abstract", "")),
                    published_date=self._parse_date(item.get("date", item.get("publish_date"))),
                    policy_number=item.get("number", item.get("policy_number")),
                    raw_data=item,
                    data_source_type=DataSourceType.API,
                    is_official_api=True
                )
                policies.append(policy)
                
        except (ValueError, KeyError) as e:
            logger.error(f"❌ [{source.name}] 解析 API 数据失败: {e}")
        
        return policies
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            try:
                from dateutil import parser
                return parser.parse(date_str)
            except ImportError:
                return None
    
    async def _collect_list_page(
        self,
        source: PolicySource
    ) -> List[CollectedPolicy]:
        """
        采集列表页面
        
        Args:
            source: 来源配置
            
        Returns:
            List[CollectedPolicy]: 政策列表
        """
        parsed = urlparse(source.list_url or source.base_url)
        domain = parsed.netloc
        
        await rate_limiter.acquire(domain)
        
        if not await robots_checker.check_allowed(source.list_url, source.name):
            logger.warning(f"🚫 [{source.name}] robots.txt 禁止采集")
            return []
        
        client = await self._get_client()
        
        for retry in range(self.max_retries):
            try:
                response = await client.get(
                    source.list_url,
                    headers=source.headers
                )
                
                rate_limiter.record_response_status(domain, response.status_code)
                
                if response.status_code == 200:
                    return self._parse_list_page(response.text, source)
                else:
                    logger.warning(
                        f"⚠️ [{source.name}] 页面返回状态码: {response.status_code}"
                    )
                    
            except (ValueError, KeyError) as e:
                logger.warning(
                    f"⚠️ [{source.name}] 第 {retry + 1} 次重试数据失败: {e}"
                )
            except (OSError, IOError) as e:
                logger.warning(
                    f"⚠️ [{source.name}] 第 {retry + 1} 次重试IO失败: {e}"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ [{source.name}] 第 {retry + 1} 次重试失败: {e}"
                )
            
            if retry < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay)
        
        return []
    
    async def _collect_with_keywords(
        self,
        source: PolicySource,
        keywords: List[str]
    ) -> List[CollectedPolicy]:
        """
        使用关键词采集
        
        Args:
            source: 来源配置
            keywords: 关键词列表
            
        Returns:
            List[CollectedPolicy]: 政策列表
        """
        all_policies = []
        
        for keyword in keywords:
            logger.info(f"🔍 [{source.name}] 搜索关键词: {keyword}")
            
            parsed = urlparse(source.search_url or source.base_url)
            domain = parsed.netloc
            
            await rate_limiter.acquire(domain)
            
            if not await robots_checker.check_allowed(source.search_url, source.name):
                continue
            
            try:
                search_url = self._build_search_url(source, keyword)
                client = await self._get_client()
                
                response = await client.get(
                    search_url,
                    headers=source.headers
                )
                
                rate_limiter.record_response_status(domain, response.status_code)
                
                if response.status_code == 200:
                    policies = self._parse_search_results(response.text, source, keyword)
                    all_policies.extend(policies)
                    
            except (ValueError, KeyError) as e:
                logger.error(f"❌ [{source.name}] 搜索数据失败 [{keyword}]: {e}")
            except (OSError, IOError) as e:
                logger.error(f"❌ [{source.name}] 搜索IO失败 [{keyword}]: {e}")
            except Exception as e:
                logger.error(f"❌ [{source.name}] 搜索失败 [{keyword}]: {e}")
            
            await asyncio.sleep(2)
        
        return all_policies
    
    def _parse_list_page(
        self,
        html: str,
        source: PolicySource
    ) -> List[CollectedPolicy]:
        """
        解析列表页面
        
        Args:
            html: HTML 内容
            source: 来源配置
            
        Returns:
            List[CollectedPolicy]: 政策列表
        """
        policies = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            links = soup.find_all("a", href=True)
            
            for link in links[:20]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                
                if self._is_policy_link(href, title):
                    url = self._build_full_url(href, source.base_url)
                    
                    policy = CollectedPolicy(
                        source_name=source.name,
                        source_url=url,
                        title=title,
                        content="",
                        data_source_type=DataSourceType.HTML,
                        legal_notice=source.legal_notice or ""
                    )
                    policies.append(policy)
                    
        except ImportError:
            logger.warning("⚠️ BeautifulSoup 未安装，无法解析 HTML")
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 解析列表页面数据失败: {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 解析列表页面IO失败: {e}")
        except Exception as e:
            logger.error(f"❌ 解析列表页面失败: {e}")
        
        return policies
    
    def _parse_search_results(
        self,
        html: str,
        source: PolicySource,
        keyword: str
    ) -> List[CollectedPolicy]:
        """
        解析搜索结果
        
        Args:
            html: HTML 内容
            source: 来源配置
            keyword: 搜索关键词
            
        Returns:
            List[CollectedPolicy]: 政策列表
        """
        return self._parse_list_page(html, source)
    
    def _is_policy_link(self, href: str, title: str) -> bool:
        """
        判断是否为政策链接
        
        Args:
            href: 链接地址
            title: 链接标题
            
        Returns:
            bool: 是否为政策链接
        """
        if not href or not title:
            return False
        
        policy_indicators = [
            "通知", "公告", "办法", "规定", "决定",
            "条例", "细则", "意见", "规程", "准则",
            "公告", "解读", "政策"
        ]
        
        title_lower = title.lower()
        
        for indicator in policy_indicators:
            if indicator in title:
                return True
        
        if "tax" in title_lower or "gov.cn" in href:
            return True
        
        return False
    
    def _build_full_url(self, href: str, base_url: str) -> str:
        """
        构建完整 URL
        
        Args:
            href: 相对或绝对路径
            base_url: 基础 URL
            
        Returns:
            str: 完整 URL
        """
        if href.startswith("http"):
            return href
        
        if href.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        
        return f"{base_url.rstrip('/')}/{href}"
    
    def _build_search_url(
        self,
        source: PolicySource,
        keyword: str
    ) -> str:
        """
        构建搜索 URL
        
        Args:
            source: 来源配置
            keyword: 搜索关键词
            
        Returns:
            str: 搜索 URL
        """
        search_url = source.search_url or source.base_url
        
        if "chinatax.gov.cn" in search_url:
            encoded_keyword = keyword.replace(" ", "%20")
            return f"{search_url}?keyword={encoded_keyword}"
        
        return search_url
    
    async def collect_all(
        self,
        keywords: Optional[List[str]] = None
    ) -> List[CollectedPolicy]:
        """
        从所有启用的来源采集政策
        
        Args:
            keywords: 关键词列表
            
        Returns:
            List[CollectedPolicy]: 所有采集到的政策
        """
        all_policies = []
        
        sorted_sources = sorted(
            [s for s in self.sources if s.enabled],
            key=lambda x: x.priority
        )
        
        logger.info(
            f"📋 开始采集任务，共 {len(sorted_sources)} 个来源，"
            f"关键词: {keywords or '无'}"
        )
        
        for source in sorted_sources:
            policies = await self.collect_from_source(source, keywords)
            all_policies.extend(policies)
            
            await asyncio.sleep(3)
        
        logger.info(f"📊 总共采集 {len(all_policies)} 条政策")
        
        return all_policies
    
    def get_compliance_report(self) -> Dict:
        """
        获取合规审计报告
        
        Returns:
            Dict: 合规报告
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_sources": len(self.sources),
            "enabled_sources": len([s for s in self.sources if s.enabled]),
            "compliance_checks": [],
            "summary": {
                "allowed": 0,
                "blocked": 0,
                "api_available": 0
            }
        }
        
        for log in self._compliance_log:
            report["compliance_checks"].append({
                "source": log.source_name,
                "allowed": log.allowed,
                "reason": log.reason,
                "crawl_delay": log.crawl_delay,
                "official_api": log.official_api_available
            })
            
            if log.allowed:
                report["summary"]["allowed"] += 1
            else:
                report["summary"]["blocked"] += 1
            
            if log.official_api_available:
                report["summary"]["api_available"] += 1
        
        return report
    
    def get_legal_disclaimer(self) -> str:
        """
        获取法律免责声明
        
        Returns:
            str: 免责声明文本
        """
        return """
        【法律声明】
        1. 本系统采集的政策数据均来自官方公开渠道，包括：
           - 国家法律法规数据库（flfg.pan.gov.cn）
           - 中国政府网（www.gov.cn）
           - 国家税务总局（www.chinatax.gov.cn）
           - 财政部（www.mof.gov.cn）
        
        2. 所有数据采集严格遵守：
           - robots.txt 协议
           - 《网络数据安全管理条例》
           - 相关版权法律
        
        3. 本系统不：
           - 破解反爬技术措施
           - 影响目标网站正常运行
           - 大规模暴力爬取
        
        4. 使用本系统数据时，请注明来源并遵守原网站的版权要求。
        
        5. 如有任何版权问题，请联系 support@example.com
        """


policy_collector = PolicyCollector()
