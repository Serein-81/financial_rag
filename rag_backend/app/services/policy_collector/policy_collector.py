"""
政策采集服务
从官方来源采集税务政策信息
"""

import httpx
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass
import json

from .robots_checker import robots_checker
from .rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


@dataclass
class PolicySource:
    """政策来源配置"""
    name: str
    base_url: str
    search_url: Optional[str] = None
    list_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True
    priority: int = 1


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
    collected_at: datetime = None
    
    def __post_init__(self):
        if self.collected_at is None:
            self.collected_at = datetime.now()


class PolicyCollector:
    """
    政策采集器
    
    从官方来源采集税务政策信息
    支持：
    1. robots.txt 合规检查
    2. 速率限制
    3. 多种官方来源
    4. 错误重试
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
    
    def _init_sources(self) -> List[PolicySource]:
        """
        初始化官方来源配置
        
        Returns:
            List[PolicySource]: 来源列表
        """
        return [
            PolicySource(
                name="国家税务总局",
                base_url="https://www.chinatax.gov.cn",
                search_url="https://www.chinatax.gov.cn/chinatax/n810341/n810755/",
                list_url="https://www.chinatax.gov.cn/chinatax/n810341/n810755/index.html",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                },
                priority=1
            ),
            PolicySource(
                name="财政部",
                base_url="http://www.mof.gov.cn",
                search_url="http://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/",
                list_url="http://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/index.htm",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                },
                priority=2
            ),
            PolicySource(
                name="国务院",
                base_url="http://www.gov.cn",
                search_url="http://www.gov.cn/zhengce/xxgk/inde.htm",
                headers={
                    "User-Agent": "PolicyCollector/1.0 (Enterprise Tax System)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                },
                priority=3
            ),
        ]
    
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
        
        collected = []
        
        try:
            if source.list_url:
                policies = await self._collect_list_page(source)
                collected.extend(policies)
                
                if keywords:
                    policies = await self._collect_with_keywords(source, keywords)
                    collected.extend(policies)
            
            logger.info(f"✅ [{source.name}] 采集完成，共 {len(collected)} 条政策")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ [{source.name}] 采集数据失败: {e}", exc_info=True)
        except (OSError, IOError) as e:
            logger.error(f"❌ [{source.name}] 采集IO失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ [{source.name}] 采集失败: {e}", exc_info=True)
        
        return collected
    
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
                        content=""
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
        
        for source in sorted_sources:
            policies = await self.collect_from_source(source, keywords)
            all_policies.extend(policies)
            
            await asyncio.sleep(3)
        
        logger.info(f"📊 总共采集 {len(all_policies)} 条政策")
        
        return all_policies


policy_collector = PolicyCollector()
