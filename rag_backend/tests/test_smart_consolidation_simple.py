"""
测试智能记忆巩固功能（简化版）
直接测试核心逻辑，不依赖数据库和其他服务
"""
from typing import Dict, List
from datetime import datetime


class SimpleMemoryManager:
    """简化版记忆管理器，用于测试智能巩固逻辑"""
    
    def __init__(self):
        # 话题频率统计
        self.topic_frequency: Dict[str, int] = {}
        self.topic_first_seen: Dict[str, datetime] = {}
        
        # 用户意图关键词库
        self.intent_keywords = [
            "记住", "记下", "别忘了", "提醒我", "一定要记住",
            "重要", "关键", "务必", "千万", "注意"
        ]
        
        # 重要话题关键词库
        self.important_topic_keywords = {
            "health": ["过敏", "疾病", "糖尿病", "高血压", "心脏病", "癌症", 
                      "手术", "住院", "药物", "治疗", "诊断", "症状"],
            "finance": ["密码", "账号", "银行卡", "信用卡", "支付", "转账", 
                       "贷款", "投资", "理财"],
            "personal": ["生日", "纪念日", "地址", "电话", "身份证", "护照"],
            "preference": ["喜欢", "讨厌", "偏好", "习惯", "爱好"],
            "work": ["项目", "任务", "截止日期", "会议", "客户", "合同"]
        }
        
        # 统计信息
        self.consolidated_count = 0
        self.total_messages = 0
    
    def evaluate_importance(self, content: str, role: str, base_importance: float) -> float:
        """智能评估记忆重要性"""
        importance = base_importance
        content_lower = content.lower()
        boost_reasons = []
        
        # 方案一：用户意图关键词检测
        has_intent = any(keyword in content_lower for keyword in self.intent_keywords)
        if has_intent:
            importance = max(importance, 0.9)
            boost_reasons.append("用户明确意图")
            print("  🎯 检测到用户意图关键词")
        
        # 方案一：重要话题关键词检测
        detected_categories = []
        for category, keywords in self.important_topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                detected_categories.append(category)
                importance = max(importance, 0.85)
        
        if detected_categories:
            boost_reasons.append(f"重要话题({','.join(detected_categories)})")
            print(f"  🏷️ 检测到重要话题: {', '.join(detected_categories)}")
        
        # 方案二：话题频率统计
        keywords = self._extract_keywords(content)
        print(f"  🔍 提取的关键词: {keywords}")  # 调试输出
        
        high_freq_topics = []
        
        for keyword in keywords:
            # 更新频率统计
            if keyword not in self.topic_frequency:
                self.topic_frequency[keyword] = 0
                self.topic_first_seen[keyword] = datetime.now()
            
            self.topic_frequency[keyword] += 1
            
            # 检查是否为高频话题
            if self.topic_frequency[keyword] >= 3:
                high_freq_topics.append(keyword)
                importance = max(importance, 0.88)
        
        if high_freq_topics:
            boost_reasons.append(f"高频话题({','.join(high_freq_topics[:2])})")
            print(f"  🔥 检测到高频话题: {', '.join(high_freq_topics[:3])}")
            print(f"     频率统计: {', '.join([f'{t}({self.topic_frequency[t]}次)' for t in high_freq_topics[:3]])}")
        
        # 输出评估结果
        if boost_reasons:
            print(f"  📈 重要性评估: {base_importance:.2f} → {importance:.2f}")
            print(f"     原因: {', '.join(boost_reasons)}")
        
        return min(1.0, importance)
    
    def _extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """提取内容关键词（改进版）"""
        # 停用词列表
        stopwords = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "里", "就是", "可以", "这个", "什么", "吗", "呢", "啊",
            "还是", "得", "越来越", "厉害", "需要", "最近", "有点", "走路"
        }
        
        import re
        
        # 方法1：提取单个中文词（2-4个字）
        chinese_words_2 = re.findall(r'[\u4e00-\u9fa5]{2}', content)  # 2字词
        chinese_words_3 = re.findall(r'[\u4e00-\u9fa5]{3}', content)  # 3字词
        chinese_words_4 = re.findall(r'[\u4e00-\u9fa5]{4}', content)  # 4字词
        
        # 方法2：提取英文词
        english_words = re.findall(r'[a-zA-Z]+', content.lower())
        
        # 合并所有词
        all_words = chinese_words_4 + chinese_words_3 + chinese_words_2 + english_words
        
        # 过滤
        keywords = []
        seen = set()
        for word in all_words:
            if word in stopwords or word in seen or word.isdigit():
                continue
            if len(word) >= 2:
                keywords.append(word)
                seen.add(word)
        
        # 限制数量
        return keywords[:max_keywords]
    
    def add_message(self, content: str, role: str = "user", base_importance: float = 0.5):
        """添加消息并评估"""
        self.total_messages += 1
        print(f"\n{'='*60}")
        print(f"📝 消息 #{self.total_messages}: {content[:50]}...")
        print(f"{'='*60}")
        
        # 评估重要性
        importance = self.evaluate_importance(content, role, base_importance)
        
        # 判断是否巩固
        if importance >= 0.8:
            self.consolidated_count += 1
            print(f"  ⭐ 已巩固到语义记忆 (importance={importance:.2f})")
        else:
            print(f"  ⏭️ 未达到巩固阈值 (importance={importance:.2f} < 0.8)")
            print(f"     [基础重要性: {base_importance:.2f}]")
        
        return importance
    
    def get_stats(self):
        """获取统计信息"""
        sorted_topics = sorted(
            self.topic_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "total_messages": self.total_messages,
            "consolidated_count": self.consolidated_count,
            "consolidation_rate": f"{self.consolidated_count/self.total_messages*100:.1f}%" if self.total_messages > 0 else "0%",
            "total_topics": len(self.topic_frequency),
            "high_frequency_topics": [topic for topic, freq in sorted_topics if freq >= 3],
            "top_topics": sorted_topics[:10]
        }


def test_smart_consolidation():
    """测试智能巩固功能"""
    
    print("=" * 80)
    print("🧪 测试智能记忆巩固功能")
    print("=" * 80)
    
    manager = SimpleMemoryManager()
    
    print("\n" + "=" * 80)
    print("📝 测试场景 1：用户意图关键词检测")
    print("=" * 80)
    
    manager.add_message("记住我对花生过敏，这个很重要！", base_importance=0.6)
    manager.add_message("别忘了提醒我明天下午3点开会", base_importance=0.6)
    
    print("\n" + "=" * 80)
    print("📝 测试场景 2：重要话题关键词检测")
    print("=" * 80)
    
    manager.add_message("我最近确诊了糖尿病，需要注意饮食", base_importance=0.6)
    manager.add_message("我的银行卡密码是123456", base_importance=0.6)
    
    print("\n" + "=" * 80)
    print("📝 测试场景 3：高频话题检测")
    print("=" * 80)
    
    manager.add_message("我的膝盖有点疼", base_importance=0.6)
    manager.add_message("膝盖还是疼，走路都困难", base_importance=0.6)
    manager.add_message("膝盖疼得越来越厉害了", base_importance=0.6)
    
    print("\n" + "=" * 80)
    print("📝 测试场景 4：普通对话（不触发巩固）")
    print("=" * 80)
    
    manager.add_message("今天天气真好", base_importance=0.3)
    manager.add_message("你好吗", base_importance=0.3)
    
    print("\n" + "=" * 80)
    print("📊 测试结果统计")
    print("=" * 80)
    
    stats = manager.get_stats()
    
    print(f"\n总消息数: {stats['total_messages']}")
    print(f"巩固数量: {stats['consolidated_count']}")
    print(f"巩固率: {stats['consolidation_rate']}")
    print(f"总话题数: {stats['total_topics']}")
    print(f"高频话题: {', '.join(stats['high_frequency_topics']) if stats['high_frequency_topics'] else '无'}")
    
    print("\nTop 10 话题:")
    for topic, freq in stats['top_topics']:
        print(f"  - {topic}: {freq}次")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)
    
    print("\n📝 预期结果验证:")
    expected_consolidated = 5  # 前5条应该被巩固
    actual_consolidated = stats['consolidated_count']
    
    if actual_consolidated == expected_consolidated:
        print(f"✅ 通过：巩固数量正确 ({actual_consolidated}/{expected_consolidated})")
    else:
        print(f"❌ 失败：巩固数量不正确 ({actual_consolidated}/{expected_consolidated})")
    
    print("\n详细预期:")
    print("1. ✅ '记住我对花生过敏' → 应该被巩固（用户意图）")
    print("2. ✅ '别忘了提醒我' → 应该被巩固（用户意图）")
    print("3. ✅ '确诊了糖尿病' → 应该被巩固（健康话题）")
    print("4. ✅ '银行卡密码' → 应该被巩固（财务话题）")
    print("5. ✅ '膝盖疼'（第3次）→ 应该被巩固（高频话题）")
    print("6. ❌ '今天天气真好' → 不应该被巩固（普通对话）")
    print("7. ❌ '你好吗' → 不应该被巩固（普通对话）")


if __name__ == "__main__":
    test_smart_consolidation()
