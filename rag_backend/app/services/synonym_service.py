"""
同义词扩展服务

提供查询同义词扩展功能，增强检索召回率
支持中文和英文同义词词典
"""
import json
import os
import logging
from typing import List, Set, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SynonymService:
    """
    同义词服务
    
    功能：
    1. 加载同义词词典
    2. 查询词的所有同义词
    3. 扩展查询（生成包含同义词的查询变体）
    4. 支持中文和英文
    
    使用方式：
    ```python
    synonym_service = SynonymService()
    
    # 获取单个词的同义词
    synonyms = synonym_service.get_synonyms("电脑")
    # ['计算机', '计算机器', 'PC', '笔记本']
    
    # 扩展查询
    expanded = synonym_service.expand_query("买电脑")
    # ['买电脑', '买计算机', '买PC', '买笔记本']
    ```
    """
    
    def __init__(self, dict_path: str = None):
        """
        初始化同义词服务
        
        Args:
            dict_path: 同义词词典路径，默认使用项目内的 synonym.json
        """
        if dict_path is None:
            dict_path = Path(__file__).parent.parent.parent / "synonym.json"
        
        self.dict_path = dict_path
        self.synonym_dict: Dict[str, List[str]] = {}
        self.reverse_dict: Dict[str, List[str]] = {}
        self._load_dictionary()
    
    def _load_dictionary(self):
        """加载同义词词典"""
        try:
            if os.path.exists(self.dict_path):
                with open(self.dict_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.synonym_dict = data.get("synonyms", {})
                
                self.reverse_dict = {}
                for word, synonyms in self.synonym_dict.items():
                    for syn in synonyms:
                        if syn not in self.reverse_dict:
                            self.reverse_dict[syn] = []
                        self.reverse_dict[syn].append(word)
                
                logger.info(f"✅ 同义词词典加载成功: {len(self.synonym_dict)} 个词条")
            else:
                logger.warning(f"⚠️ 同义词词典不存在: {self.dict_path}，使用内置词典")
                self._load_builtin_dictionary()
        except Exception as e:
            logger.error(f"❌ 同义词词典加载失败: {e}")
            self._load_builtin_dictionary()
    
    def _load_builtin_dictionary(self):
        """加载内置词典（基础版本）"""
        self.synonym_dict = {
            "电脑": ["计算机", "PC", "笔记本", "计算机器"],
            "计算机": ["电脑", "PC", "笔记本"],
            "手机": ["移动电话", "智能手机", "电话"],
            "网络": ["互联网", "宽带", "WiFi", "wifi"],
            "存储": ["储存", "硬盘", "磁盘", "内存"],
            "文件": ["文档", "资料", "档案"],
            "搜索": ["查找", "检索", "查询"],
            "删除": ["移除", "清除", "删掉"],
            "修改": ["编辑", "更改", "更新"],
            "创建": ["新建", "新增", "添加"],
            "登录": ["登入", "注册", "sign in"],
            "注册": ["登记", "sign up", "signin"],
            "密码": ["口令", "passcode", "password"],
            "账号": ["账户", "用户名", "account"],
            "用户": ["使用者", "client", "customer"],
            "订单": ["交易", "purchase", "order"],
            "支付": ["付款", "缴费", "pay"],
            "退款": ["退货", "返还", "refund"],
            "发票": ["收据", "账单", "invoice"],
            "地址": ["位置", "地点", "address"],
            "时间": ["时刻", "时候", "time"],
            "价格": ["费用", "价钱", "cost", "price"],
            "质量": ["品质", "质量", "quality"],
            "服务": ["服务", "客服", "service"],
            "问题": ["疑问", "issue", "problem"],
            "帮助": ["协助", "support", "help"],
            "开始": ["启动", "开启", "start"],
            "停止": ["暂停", "结束", "stop"],
            "连接": ["联结", "接入", "connect"],
            "断开": ["解除", "退出", "disconnect"]
        }
        
        self.reverse_dict = {}
        for word, synonyms in self.synonym_dict.items():
            for syn in synonyms:
                if syn not in self.reverse_dict:
                    self.reverse_dict[syn] = []
                self.reverse_dict[syn].append(word)
        
        logger.info(f"📦 使用内置词典: {len(self.synonym_dict)} 个词条")
    
    def get_synonyms(self, word: str, include_reverse: bool = True) -> List[str]:
        """
        获取词的所有同义词
        
        Args:
            word: 输入词
            include_reverse: 是否包含反向同义词（如果 A 的同义词包含 B，则 B 的同义词也包含 A）
            
        Returns:
            同义词列表
        """
        word = word.strip().lower()
        synonyms = set()
        
        if word in self.synonym_dict:
            synonyms.update(self.synonym_dict[word])
        
        if include_reverse and word in self.reverse_dict:
            synonyms.update(self.reverse_dict[word])
        
        return list(synonyms)
    
    def expand_query(self, query: str, max_synonyms_per_word: int = 3) -> List[str]:
        """
        扩展查询，生成包含同义词的查询变体
        
        Args:
            query: 原始查询
            max_synonyms_per_word: 每个词最多保留的同义词数量（避免组合爆炸）
            
        Returns:
            扩展后的查询列表（包含原始查询）
            
        示例：
        >>> service = SynonymService()
        >>> service.expand_query("买电脑")
        ['买电脑', '买计算机', '买PC', '买笔记本']
        """
        import re
        
        words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', query.lower())
        
        if not words:
            return [query]
        
        expanded_words = [[query]]
        
        for word in words:
            if len(word) < 2:
                continue
            
            synonyms = self.get_synonyms(word)
            if synonyms:
                synonyms = synonyms[:max_synonyms_per_word]
                new_expanded = []
                for base in expanded_words[-1]:
                    for syn in synonyms:
                        new_expanded.append(base.replace(word, syn))
                expanded_words.append(new_expanded)
        
        all_queries = []
        for expanded in expanded_words:
            all_queries.extend(expanded)
        
        return list(set(all_queries))[:10]
    
    def add_synonym(self, word: str, synonyms: List[str]):
        """
        添加同义词（运行时添加，不持久化）
        
        Args:
            word: 词
            synonyms: 同义词列表
        """
        word = word.strip().lower()
        
        if word not in self.synonym_dict:
            self.synonym_dict[word] = []
        
        for syn in synonyms:
            syn = syn.strip().lower()
            if syn not in self.synonym_dict[word]:
                self.synonym_dict[word].append(syn)
            
            if syn not in self.reverse_dict:
                self.reverse_dict[syn] = []
            if word not in self.reverse_dict[syn]:
                self.reverse_dict[syn].append(word)
    
    def reload(self):
        """重新加载词典"""
        self._load_dictionary()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取词典统计信息"""
        return {
            "total_words": len(self.synonym_dict),
            "total_relations": sum(len(v) for v in self.synonym_dict.values()),
            "dict_path": str(self.dict_path),
            "loaded": os.path.exists(self.dict_path)
        }


synonym_service = SynonymService()
