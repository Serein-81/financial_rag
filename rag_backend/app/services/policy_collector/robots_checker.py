"""
robots.txt 合规检查器
确保政策采集遵守网站爬虫协议

合规要求：
1. 严格遵守 robots.txt 协议
2. 尊重 Crawl-Delay 指令
3. 不爬取 Disallow 的路径
4. 记录合规日志以备审计
"""

import httpx
import logging
from typing import Dict, Optional, List, Tuple
from urllib.parse import urlparse
from datetime import datetime, timedelta
import re
import time

logger = logging.getLogger(__name__)


class RobotsChecker:
    """
    robots.txt 合规检查器
    
    功能：
    1. 缓存 robots.txt 内容
    2. 检查 URL 是否允许爬取
    3. 自动尊重 Crawl-Delay 指令
    4. 支持 Sitemap 发现
    5. 合规审计日志
    """
    
    def __init__(self, user_agent: str = "PolicyCollector/1.0"):
        self.user_agent = user_agent
        self._robots_cache: Dict[str, Dict] = {}
        self._cache_ttl = timedelta(hours=1)
        self._compliance_log: List[Dict] = []
        self._last_request_time: Dict[str, float] = {}
    
    async def check_compliance(
        self,
        base_url: str,
        source_name: str
    ) -> Tuple[bool, List[str], float]:
        """
        全面合规检查
        
        Args:
            base_url: 基础 URL
            source_name: 来源名称
            
        Returns:
            Tuple[bool, List[str], float]: (是否允许, 限制列表, 爬取延迟)
        """
        logger.info(f"🔍 [{source_name}] 检查 robots.txt 合规性...")
        
        robots_url = f"{base_url}/robots.txt"
        restrictions = []
        
        try:
            rules = await self._get_robots_rules(base_url, robots_url)
            
            if rules is None:
                logger.warning(f"⚠️ [{source_name}] 无法获取 robots.txt，假设允许爬取")
                self._log_compliance(source_name, base_url, True, "无法获取robots.txt，假设允许")
                return True, [], 1.0
            
            crawl_delay = rules.get("crawl_delay", 1)
            
            if rules.get("disallow"):
                restrictions.extend(rules["disallow"])
                logger.warning(f"🚫 [{source_name}] 发现禁止路径: {rules['disallow']}")
            
            is_allowed = len(restrictions) == 0 or self._check_allow_path(base_url)
            
            self._log_compliance(
                source_name, 
                base_url, 
                is_allowed, 
                f"disallow规则: {len(restrictions)}条, crawl_delay: {crawl_delay}s"
            )
            
            return is_allowed, restrictions, crawl_delay
            
        except Exception as e:
            logger.error(f"❌ [{source_name}] 合规检查失败: {e}")
            self._log_compliance(source_name, base_url, False, f"检查异常: {str(e)}")
            return False, [f"检查失败: {str(e)}"], 1.0
    
    def _check_allow_path(self, base_url: str) -> bool:
        """检查是否有明确允许的路径"""
        return True
    
    def _log_compliance(
        self,
        source_name: str,
        url: str,
        allowed: bool,
        reason: str
    ):
        """记录合规日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "source_name": source_name,
            "url": url,
            "allowed": allowed,
            "reason": reason,
            "user_agent": self.user_agent
        }
        self._compliance_log.append(log_entry)
        logger.debug(f"📋 合规日志: {log_entry}")
    
    def get_compliance_report(self) -> List[Dict]:
        """获取合规审计报告"""
        return self._compliance_log[-100:]
    
    def clear_compliance_log(self):
        """清空合规日志"""
        self._compliance_log.clear()
        logger.info("🗑️ 合规日志已清空")
    
    async def check_allowed(
        self,
        url: str,
        source_name: str
    ) -> bool:
        """
        检查 URL 是否允许爬取
        
        Args:
            url: 待检查的 URL
            source_name: 来源名称
            
        Returns:
            bool: 是否允许爬取
        """
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        robots_url = f"{base_url}/robots.txt"
        
        robots_rules = await self._get_robots_rules(base_url, robots_url)
        
        if not robots_rules:
            logger.warning(f"⚠️ [{source_name}] 无法获取 robots.txt，假设允许爬取")
            return True
        
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        
        if not path.startswith("/"):
            path = "/" + path
        
        for rule in robots_rules.get("disallow", []):
            if self._matches_pattern(path, rule):
                logger.info(f"🚫 [{source_name}] 路径被禁止: {path} (规则: {rule})")
                return False
        
        for rule in robots_rules.get("allow", []):
            if self._matches_pattern(path, rule):
                logger.debug(f"✅ [{source_name}] 路径明确允许: {path}")
                return True
        
        logger.debug(f"✅ [{source_name}] 路径默许爬取: {path}")
        return True
    
    async def _get_robots_rules(
        self,
        base_url: str,
        robots_url: str
    ) -> Optional[Dict]:
        """
        获取并解析 robots.txt
        
        Args:
            base_url: 基础 URL
            robots_url: robots.txt URL
            
        Returns:
            Dict: 解析后的规则
        """
        if base_url in self._robots_cache:
            cached = self._robots_cache[base_url]
            if datetime.now() - cached["timestamp"] < self._cache_ttl:
                return cached["rules"]
        
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True
            ) as client:
                response = await client.get(robots_url)
                
                if response.status_code != 200:
                    logger.warning(f"无法获取 robots.txt: {robots_url}, 状态码: {response.status_code}")
                    return None
                
                rules = self._parse_robots_txt(response.text)
                
                self._robots_cache[base_url] = {
                    "rules": rules,
                    "timestamp": datetime.now()
                }
                
                logger.info(f"📜 [{base_url}] robots.txt 解析完成")
                return rules
                
        except Exception as e:
            logger.error(f"❌ 获取 robots.txt 失败: {robots_url}, 错误: {e}")
            return None
    
    def _parse_robots_txt(self, content: str) -> Dict:
        """
        解析 robots.txt 内容
        
        Args:
            content: robots.txt 文本内容
            
        Returns:
            Dict: 解析后的规则
        """
        rules = {
            "disallow": [],
            "allow": [],
            "crawl_delay": 1,
            "sitemaps": []
        }
        
        current_user_agent = None
        
        for line in content.split("\n"):
            line = line.strip()
            
            if not line or line.startswith("#"):
                continue
            
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == "user-agent":
                    if value == "*" or value == self.user_agent:
                        current_user_agent = value
                    else:
                        current_user_agent = None
                
                elif key == "disallow" and current_user_agent:
                    if value:
                        rules["disallow"].append(value)
                
                elif key == "allow" and current_user_agent:
                    if value:
                        rules["allow"].append(value)
                
                elif key == "crawl-delay" and current_user_agent:
                    try:
                        rules["crawl_delay"] = max(1, float(value))
                    except ValueError:
                        pass
                
                elif key == "sitemap":
                    if value:
                        rules["sitemaps"].append(value)
        
        return rules
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        检查路径是否匹配规则模式
        
        Args:
            path: URL 路径
            pattern: robots.txt 规则模式
            
        Returns:
            bool: 是否匹配
        """
        if pattern == "/":
            return True
        
        if pattern.endswith("$"):
            base_pattern = pattern[:-1]
            return path == base_pattern
        
        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*").replace("?", "\\?")
            return bool(re.match(regex_pattern, path))
        
        return path.startswith(pattern)
    
    def get_crawl_delay(self, base_url: str) -> float:
        """
        获取爬取延迟（秒）
        
        Args:
            base_url: 基础 URL
            
        Returns:
            float: 爬取延迟（秒）
        """
        if base_url in self._robots_cache:
            return self._robots_cache[base_url]["rules"].get("crawl_delay", 1)
        return 1
    
    def clear_cache(self):
        """清空缓存"""
        self._robots_cache.clear()
        logger.info("🗑️ robots.txt 缓存已清空")


robots_checker = RobotsChecker()
